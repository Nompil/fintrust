"""Fixed post-migration service logins and grants; no financial data or caller SQL."""
import hashlib
from psycopg2 import sql
from . import common, config
from .extension_catalog import _catalog_for_version

PERMISSIONS = {
 'infrastructure/rds/permissions.sql': '97dcb480ffb15ea16d5099eae69ddde328ab25313fb6ec76c897a2f9776b5770',
 'infrastructure/rds/release1_permissions.sql': 'f3d344a22b641e9943d42598fe321269051b036c046d2e74bf99175f7d0ca52d'}
HISTORY = (
 '0ff06ca8c43596ac9b8651f4bd851bfb0487343f4c9eccb198849e3e59772bd6',
 '5b2c04440eea244bfce150347dfa1953dd2a7e7ddb6af7e3a66e187d1c912f02',
 '5813a1d24b44c00d8f53629519a306e82b32e02a00d2ed34868d04037dc7f181',
 'ecf0badd166fa89c6143cbf2c75b6501a8b56fd3ae7385f496542bd51e2a55f6',
 '8f1697374e1853bd1ce48c6f0c502deb9c51f431aac9d5430312d3f79129fcfe',
 '9049d766b5613cdd74f814c278c3d5867349d99f08ef98b50c158d2d95b5c2a4')
GROUPS = ('fintrust_ingest','fintrust_scoring','fintrust_alert','fintrust_api','fintrust_report',
          'fintrust_workflow_api','fintrust_workflows_owner')
LOGINS = {'fintrust_scoring_dev': ('fintrust_scoring',),
          'fintrust_api_dev': ('fintrust_api','fintrust_workflow_api'),
          'fintrust_report_dev': ('fintrust_report',)}
OWNERS = ('fintrust_transactions_owner','fintrust_workflow_owner')


def permissions(path):
    text=(config.ROOT/path).read_text(encoding='utf-8').replace('\r\n','\n')
    if hashlib.sha256(text.encode()).hexdigest()!=PERMISSIONS[path]:
        raise common.Refused('runtime_permission_source_mismatch')
    return '\n'.join(line for line in text.splitlines() if line.strip() not in {'BEGIN;','COMMIT;'})


def provision(conn, op):
    if op!='provision_runtime': raise common.Refused('operation_not_allowed')
    bodies=[permissions(path) for path in PERMISSIONS]
    with conn.cursor() as cur:
        common.setup(cur,read_only=False);common.session_check(cur,config.MASTER)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-runtime-provision:public'))")
        cur.execute('SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=ANY(%s)',(list(OWNERS),))
        owners=cur.fetchall()
        if {row[0] for row in owners}!=set(OWNERS) or any(any(row[1:]) for row in owners):
            raise common.Refused('runtime_persistent_owner_mismatch')
        # Cleanup deliberately removed administrator SELECT/SET paths. Re-open
        # only these two known owner paths inside this transaction, then revoke.
        for owner in OWNERS:
            cur.execute(sql.SQL('GRANT {} TO fintrust_admin WITH SET TRUE, INHERIT TRUE, ADMIN FALSE').format(sql.Identifier(owner)))
        cur.execute('SELECT version,source_sha256,catalog_sha256 FROM public.schema_migrations ORDER BY version')
        history=cur.fetchall()
        if [(row[0],row[1]) for row in history]!=list(enumerate(HISTORY,1)):
            raise common.Refused('runtime_requires_verified_migration_history')
        signature=_catalog_for_version(cur,'public',6)
        if history[-1][2]!=signature: raise common.Refused('runtime_requires_current_catalog')
        cur.execute('SELECT rolname FROM pg_roles WHERE rolname=ANY(%s)',(list(GROUPS)+list(LOGINS),))
        if cur.fetchall(): raise common.Refused('existing_runtime_role_requires_review')
        cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('fintrust_migrate_dev','fintrust_index_builder')")
        if cur.fetchall(): raise common.Refused('maintenance_cleanup_required')
        # Use each persistent owner's rights only for this fixed ACL operation.
        cur.execute('CREATE ROLE fintrust_workflows_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        cur.execute('GRANT fintrust_workflows_owner TO fintrust_admin WITH SET TRUE, INHERIT TRUE, ADMIN FALSE')
        cur.execute('GRANT USAGE,CREATE ON SCHEMA public TO fintrust_workflows_owner')
        for body in bodies:cur.execute(body)
        # PostgreSQL's FK check takes FOR KEY SHARE as the referenced-table
        # owner. Bootstrap revoked the owner's DML ACLs for migration isolation.
        # Restore only its key-lock column after the maintenance login is gone;
        # application logins receive no owner membership or transaction UPDATE.
        cur.execute('GRANT UPDATE(tx_id) ON public.transactions TO fintrust_transactions_owner')
        # Migration 003's immutable audit table did not exist in the original 002 grants.
        cur.execute('GRANT SELECT ON public.transaction_lifecycle_events TO fintrust_workflow_api')
        cur.execute('GRANT SELECT,INSERT ON public.transaction_lifecycle_events TO fintrust_scoring')
        cur.execute('GRANT USAGE ON SEQUENCE public.transaction_lifecycle_events_event_id_seq TO fintrust_scoring')
        cur.execute('GRANT EXECUTE ON FUNCTION public.validate_lifecycle_event() TO fintrust_scoring')
        for login,groups in LOGINS.items():
            cur.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10').format(sql.Identifier(login)))
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE fintrust TO {}').format(sql.Identifier(login)))
            for group in ('rds_iam',)+groups:
                cur.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(group),sql.Identifier(login)))
        cur.execute('REVOKE CREATE ON SCHEMA public FROM fintrust_workflows_owner')
        for owner in OWNERS+('fintrust_workflows_owner',):
            cur.execute(sql.SQL('GRANT {} TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE').format(sql.Identifier(owner)))
        for login in LOGINS:
            cur.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolconnlimit FROM pg_roles WHERE rolname=%s",(login,))
            if cur.fetchone()!=(True,True,False,False,False,False,False,10):
                raise common.Refused('runtime_login_postcheck_failed')
            cur.execute("SELECT pg_has_role(%s,'rds_iam','MEMBER'),has_schema_privilege(%s,'public','CREATE')",(login,login))
            if cur.fetchone()!=(True,False):raise common.Refused('runtime_authority_postcheck_failed')
            cur.execute('SELECT pg_get_userbyid(roleid) FROM pg_auth_members WHERE member=%s::regrole',(login,))
            if {r[0] for r in cur.fetchall()}!=set(('rds_iam',)+LOGINS[login]):
                raise common.Refused('runtime_membership_postcheck_failed')
        for table in ('transactions','risk_events','risk_review_history'):
            for action in ('INSERT','UPDATE','DELETE'):
                cur.execute('SELECT has_table_privilege(%s,%s,%s)',('fintrust_api_dev','public.'+table,action))
                if cur.fetchone()!=(False,):raise common.Refused('api_financial_write_not_denied')
        for action in ('UPDATE','DELETE'):
            cur.execute("SELECT has_table_privilege('fintrust_scoring_dev','public.transactions',%s)",(action,))
            if cur.fetchone()!=(False,):raise common.Refused('scoring_financial_mutation_not_denied')
        if _catalog_for_version(cur,'public',6)!=signature:raise common.Refused('runtime_grants_changed_migration_catalog')
    return {'runtime_logins':list(LOGINS),'iam_membership_verified':True,
            'migration_catalog_preserved':True,'api_financial_writes_denied':True,
            'scoring_financial_update_delete_denied':True,'financial_data_written':False},True

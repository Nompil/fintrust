"""Disposable GitHub CI PostgreSQL 16 privilege rehearsal; never RDS."""
import json
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import parse_dsn
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from migration_runner import common

def expect_denied(cur, statement, error_type=psycopg2.errors.InsufficientPrivilege):
    """Real PostgreSQL denial with transaction recovery, never exception suppression."""
    cur.execute("SAVEPOINT denied_operation")
    try:
        cur.execute(statement)
    except error_type:
        cur.execute("ROLLBACK TO SAVEPOINT denied_operation")
    else:
        raise AssertionError("Unexpected privilege escalation")
    finally:
        cur.execute("RELEASE SAVEPOINT denied_operation")


def memberships(cur):
    cur.execute("SELECT pg_get_userbyid(grantor), pg_get_userbyid(roleid), pg_get_userbyid(member), admin_option, inherit_option, set_option FROM pg_auth_members ORDER BY 1,2,3")
    return cur.fetchall()


def run():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("CI")!="true":raise RuntimeError("Dedicated disposable CI service required")
    dsn=os.environ["FINTRUST_TEST_DATABASE_URL"];v=parse_dsn(dsn)
    if v.get("host") not in {"localhost","127.0.0.1","::1"} or v.get("dbname")!="fintrust_test" or v.get("user")!="postgres":raise RuntimeError("Disposable target mismatch")
    admin=psycopg2.connect(dsn);admin.autocommit=True
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT current_setting('server_version_num')::int, rolsuper FROM pg_roles WHERE rolname=current_user")
            version,superuser=cur.fetchone();assert 160000<=version<170000 and superuser
            cur.execute("SELECT count(*) FROM pg_database WHERE datname='fintrust'");assert cur.fetchone()[0]==0
            cur.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('fintrust_admin','fintrust_migrate_dev','fintrust_transactions_owner','fintrust_index_builder','rds_iam')");assert cur.fetchone()[0]==0
            cur.execute("CREATE ROLE fintrust_admin LOGIN NOINHERIT CREATEROLE")
            cur.execute("CREATE ROLE rds_iam NOLOGIN")
            cur.execute("GRANT rds_iam TO fintrust_admin WITH ADMIN TRUE, INHERIT FALSE, SET FALSE")
            cur.execute("CREATE ROLE fintrust_runtime_probe NOLOGIN")
            cur.execute("CREATE DATABASE fintrust OWNER fintrust_admin")
        v['dbname']='fintrust';conn=psycopg2.connect(**v)
        try:
            with conn.cursor() as cur:
                cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
                source=(ROOT/'sql/schema.sql').read_text().split('-- Additive identity hardening.')[0].replace('CREATE EXTENSION IF NOT EXISTS pgcrypto;','')
                cur.execute(source);cur.execute((ROOT/'sql/seed.sql').read_text())
                cur.execute("GRANT SELECT ON public.accounts TO fintrust_runtime_probe")
                cur.execute("SELECT relacl::text FROM pg_class WHERE oid='public.accounts'::regclass")
                runtime_acl_before=cur.fetchone()[0]
                runtime_memberships_before=memberships(cur)
                # Reproduce the original first failing self-grant with exact roles.
                cur.execute("SAVEPOINT original_failure")
                cur.execute("CREATE ROLE fintrust_transactions_owner NOLOGIN NOINHERIT")
                expect_denied(cur, "GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN TRUE", psycopg2.errors.InvalidGrantOperation)
                cur.execute("ROLLBACK TO SAVEPOINT original_failure")
                cur.execute("RELEASE SAVEPOINT original_failure")
                cur.execute((ROOT/'sql/bootstrap/temporary_identity.sql').read_text())
                cur.execute((ROOT/'sql/bootstrap/fixed_identity_indexes.sql').read_text())
            conn.commit()
            with conn.cursor() as cur:
                bootstrap_memberships=memberships(cur)
                cur.execute("SELECT has_function_privilege('fintrust_runtime_probe','public.fintrust_create_identity_indexes()','EXECUTE'), pg_has_role('fintrust_migrate_dev','fintrust_index_builder','MEMBER'), pg_has_role('fintrust_migrate_dev','fintrust_index_builder','SET')")
                assert cur.fetchone()==(False,False,False)
                cur.execute("SELECT prosecdef, proconfig, pg_get_userbyid(proowner), pronargs FROM pg_proc WHERE oid='public.fintrust_create_identity_indexes()'::regprocedure")
                assert cur.fetchone()==(True,['search_path=pg_catalog, pg_temp'],'fintrust_index_builder',0)
                cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SET SESSION AUTHORIZATION fintrust_runtime_probe")
                expect_denied(cur, "SELECT public.fintrust_create_identity_indexes()")
                cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
                cur.execute("SELECT count(*) FROM pg_auth_members WHERE member='fintrust_migrate_dev'::regrole AND admin_option")
                assert cur.fetchone()[0]==0
                cur.execute("SELECT count(*) FROM pg_auth_members WHERE roleid='fintrust_transactions_owner'::regrole AND member='fintrust_admin'::regrole AND grantor='fintrust_admin'::regrole AND admin_option")
                assert cur.fetchone()[0]==0
            with conn.cursor() as cur:
                cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
                cur.execute("SELECT pg_has_role(current_user,'rds_iam','MEMBER'), pg_has_role(current_user,'fintrust_transactions_owner','SET'), rolcreaterole, rolsuper, rolinherit FROM pg_roles WHERE rolname=current_user")
                assert cur.fetchone()==(True,True,False,False,False)
                cur.execute("SELECT rolcreatedb, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user")
                assert cur.fetchone()==(False,False,False)
                expect_denied(cur, "GRANT fintrust_transactions_owner TO fintrust_runtime_probe")
                expect_denied(cur, "ALTER TABLE public.transactions ADD COLUMN denied_without_set integer")
                expect_denied(cur, "CREATE TABLE public.denied_login_table(id integer)")
                cur.execute("SELECT has_schema_privilege(current_user,'public','CREATE')");assert cur.fetchone()[0] is False
                expect_denied(cur, "SET ROLE fintrust_index_builder")
                expect_denied(cur, "SELECT public.fintrust_create_identity_indexes('CREATE TABLE public.bad(id int)')", psycopg2.errors.UndefinedFunction)
                expect_denied(cur, "CREATE VIEW public.bad_view AS SELECT 1")
                expect_denied(cur, "CREATE FUNCTION public.bad_function() RETURNS int LANGUAGE sql AS 'SELECT 1'")
                cur.execute("SET ROLE fintrust_transactions_owner")
                expect_denied(cur, "ALTER TABLE public.accounts ADD COLUMN denied_unrelated integer")
                expect_denied(cur, "CREATE TABLE public.denied_owner_table(id integer)")
                expect_denied(cur, "GRANT fintrust_transactions_owner TO fintrust_runtime_probe")
                cur.execute("SAVEPOINT ddl_rollback")
                cur.execute("ALTER TABLE public.transactions ADD COLUMN rollback_probe integer")
                try:
                    cur.execute("SELECT 1/0")
                except psycopg2.errors.DivisionByZero:
                    cur.execute("ROLLBACK TO SAVEPOINT ddl_rollback")
                else:
                    raise AssertionError("SQL failure did not occur")
                cur.execute("RELEASE SAVEPOINT ddl_rollback")
                cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='transactions' AND column_name='rollback_probe'")
                assert cur.fetchone()[0]==0
                columns, indexes = common.migration_parts()
                # Prove ADD COLUMN succeeds but direct CREATE INDEX lacks schema rights.
                cur.execute("SAVEPOINT missing_schema_permission")
                cur.execute(columns)
                expect_denied(cur, "CREATE INDEX arbitrary_migration_index ON public.transactions(amount)")
                expect_denied(cur, indexes)
                cur.execute("ROLLBACK TO SAVEPOINT missing_schema_permission")
                cur.execute("RELEASE SAVEPOINT missing_schema_permission")
                # Exact runtime locking works without adding DML permissions.
                common.lock_transactions(cur)
                cur.execute("SELECT count(*) FROM pg_locks WHERE pid=pg_backend_pid() AND relation='public.transactions'::regclass AND mode='AccessExclusiveLock' AND granted")
                assert cur.fetchone()[0]==1
                cur.execute("SELECT has_table_privilege(current_user,'public.transactions','UPDATE'), has_table_privilege(current_user,'public.transactions','DELETE'), has_table_privilege(current_user,'public.transactions','TRUNCATE')")
                assert cur.fetchone()==(False,False,False)
                # Two approved indexes are the only definer DDL. Temp-name shadows
                # and hostile caller search_path cannot redirect the qualified target.
                cur.execute("RESET ROLE")
                cur.execute("CREATE TEMP TABLE transactions (wrong_column int)")
                cur.execute("SET search_path=pg_temp,public")
                cur.execute("SET ROLE fintrust_transactions_owner")
                # Function self-removal and column/index DDL roll back together.
                cur.execute("SAVEPOINT complete_rollback")
                cur.execute("SET LOCAL search_path=pg_catalog,public,pg_temp")
                cur.execute(columns)
                cur.execute("RESET ROLE")
                cur.execute("SELECT public.fintrust_create_identity_indexes()")
                cur.execute("SELECT to_regprocedure('public.fintrust_create_identity_indexes()') IS NULL")
                assert cur.fetchone()[0]
                try:
                    cur.execute("SELECT 1/0")
                except psycopg2.errors.DivisionByZero:
                    cur.execute("ROLLBACK TO SAVEPOINT complete_rollback")
                cur.execute("RELEASE SAVEPOINT complete_rollback")
                cur.execute("SELECT to_regprocedure('public.fintrust_create_identity_indexes()') IS NOT NULL, to_regclass('public.idx_tx_source_identity') IS NULL")
                assert cur.fetchone()==(True,True)
                cur.execute("SELECT count(*) FROM pg_attribute WHERE attrelid='public.transactions'::regclass AND attname='source_system'")
                assert cur.fetchone()[0]==0
                # A same-name wrong index must fail closed. Fixture setup alone uses
                # the disposable service administrator, not the production helper.
                cur.execute("RESET ROLE");cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SAVEPOINT conflicting_index")
                cur.execute("CREATE INDEX idx_tx_source_identity ON public.transactions(amount)")
                cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
                cur.execute("SET ROLE fintrust_transactions_owner")
                cur.execute("SET LOCAL search_path=pg_catalog,public,pg_temp")
                cur.execute(columns);cur.execute("RESET ROLE")
                expect_denied(cur, "SELECT public.fintrust_create_identity_indexes()", psycopg2.errors.RaiseException)
                cur.execute("ROLLBACK TO SAVEPOINT conflicting_index")
                cur.execute("RELEASE SAVEPOINT conflicting_index")
                # Also reject a changed indexed column type before privileged DDL.
                cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
                cur.execute("SET ROLE fintrust_transactions_owner")
                cur.execute("SAVEPOINT conflicting_type")
                cur.execute("SET LOCAL search_path=pg_catalog,public,pg_temp")
                cur.execute(columns)
                cur.execute("ALTER TABLE public.transactions ALTER source_system TYPE varchar(101)")
                cur.execute("RESET ROLE")
                expect_denied(cur, "SELECT public.fintrust_create_identity_indexes()", psycopg2.errors.RaiseException)
                cur.execute("ROLLBACK TO SAVEPOINT conflicting_type")
                cur.execute("RELEASE SAVEPOINT conflicting_type")
                # Seed one *correct* existing index as fixture administrator, then
                # confirm the helper accepts it and creates only the missing one.
                cur.execute("RESET ROLE");cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SET LOCAL search_path=pg_catalog,public,pg_temp")
                cur.execute(columns)
                cur.execute("CREATE UNIQUE INDEX idx_tx_source_identity ON public.transactions(source_system, account_id, source_transaction_id) WHERE source_transaction_id IS NOT NULL")
                cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
                cur.execute("SELECT public.fintrust_create_identity_indexes()")
                cur.execute("SELECT to_regprocedure('public.fintrust_create_identity_indexes()') IS NULL")
                assert cur.fetchone()[0]
                expect_denied(cur, "SELECT public.fintrust_create_identity_indexes()", psycopg2.errors.UndefinedFunction)
                cur.execute("SET ROLE fintrust_transactions_owner")
                # The runner rerun first assesses exact definitions and does no DDL.
                c,d,a=common.inspect(cur)
                assert a['state']=='correct' and d['row_counts']['transactions']==200
                cur.execute("SELECT count(*) FROM pg_index WHERE indrelid='public.transactions'::regclass AND indexrelid IN ('public.idx_tx_source_identity'::regclass,'public.idx_tx_duplicate_charge'::regclass) AND indpred IS NOT NULL")
                assert cur.fetchone()[0]==2
                cur.execute("SELECT indisunique FROM pg_index WHERE indexrelid='public.idx_tx_source_identity'::regclass")
                assert cur.fetchone()[0] is True
                cur.execute("SELECT count(*) FROM public.transactions");assert cur.fetchone()[0]==200
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("SET ROLE fintrust_transactions_owner")
                c,d,a=common.inspect(cur)
                assert a['state']=='correct' and d['row_counts']['transactions']==200
            conn.rollback()
            with conn.cursor() as cur:
                # Remove only the hostile temp-table test fixture as its owner.
                # Production cleanup must still refuse unexpected owned objects.
                cur.execute("RESET ROLE")
                cur.execute("DROP TABLE pg_temp.transactions")
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("RESET ROLE");cur.execute("RESET SESSION AUTHORIZATION");cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
                cur.execute((ROOT/'sql/bootstrap/remove_temporary_identity.sql').read_text())
                cur.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('fintrust_migrate_dev','fintrust_index_builder')");assert cur.fetchone()[0]==0
                cur.execute("SELECT to_regprocedure('public.fintrust_create_identity_indexes()') IS NULL")
                assert cur.fetchone()[0]
                cur.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.transactions'::regclass");assert cur.fetchone()[0]=='fintrust_transactions_owner'
                cur.execute("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='fintrust_migrate_dev')")
                assert cur.fetchone()[0]==0
                cur.execute("SELECT pg_has_role(current_user,'fintrust_transactions_owner','SET')")
                assert cur.fetchone()[0] is False
                cur.execute("SELECT rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls FROM pg_roles WHERE rolname='fintrust_transactions_owner'")
                assert cur.fetchone()==(False,False,False,False,False,False)
                cur.execute("SELECT relacl::text FROM pg_class WHERE oid='public.accounts'::regclass")
                assert cur.fetchone()[0]==runtime_acl_before
                after=memberships(cur)
                assert [r for r in after if r[2]=='fintrust_runtime_probe']==[r for r in runtime_memberships_before if r[2]=='fintrust_runtime_probe']
                cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SELECT count(*) FROM public.transactions");assert cur.fetchone()[0]==200
            conn.commit()
        finally:conn.close()
        return {"postgresql_major":16,"postgresql_version_num":version,
                "helper_security_and_cleanup_verified":True,"helper_full_transaction_rollback_verified":True,
                "helper_existing_correct_index_verified":True,"helper_conflicting_index_rejected":True,
                "helper_conflicting_column_type_rejected":True,"helper_no_public_execute_verified":True,
                "helper_no_role_membership_verified":True,"helper_dropped_after_success":True,
                "schema_create_requirement_reproduced":True,"owner_preserving_lock_verified":True,
                "original_admin_self_grant_reproduced":True,"bootstrap_memberships":bootstrap_memberships,
                "migration_admin_delegation_denied":True,"unrelated_ddl_denied":True,
                "set_role_required":True,"ddl_rollback_verified":True,"partial_indexes_verified":True,
                "runtime_permissions_unchanged":True,"temporary_login_removed":True,
                "administrator_set_access_removed":True,"bootstrap_migrate_rerun_cleanup_passed":True,"legacy_rows_preserved":200,
                "aws_rds_iam_auth_tested":False,"note":"Local placeholder rds_iam role tests membership/SQL only; real RDS IAM/TLS remains live preflight."}
    finally:
        # This dedicated CI service is disposable. Do not run cleanup against any other server.
        admin.close()

if __name__=='__main__':
    result=run();out=ROOT/'build/migration-runner/pg16-role-rehearsal.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

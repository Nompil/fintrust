"""Disposable GitHub CI PostgreSQL 16 privilege rehearsal; never RDS."""
import json
import os
from pathlib import Path
import psycopg2
from psycopg2.extensions import parse_dsn
ROOT=Path(__file__).resolve().parents[1]

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
            cur.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('fintrust_admin','fintrust_migrate_dev','fintrust_transactions_owner','rds_iam')");assert cur.fetchone()[0]==0
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
            conn.commit()
            with conn.cursor() as cur:
                bootstrap_memberships=memberships(cur)
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
                source=(ROOT/'sql/migrations/001_transaction_identity.sql').read_text()
                source=source.removeprefix('BEGIN;\n').removesuffix('COMMIT;\n')
                cur.execute(source);cur.execute(source)
                cur.execute("SELECT count(*) FROM pg_index WHERE indrelid='public.transactions'::regclass AND indexrelid IN ('public.idx_tx_source_identity'::regclass,'public.idx_tx_duplicate_charge'::regclass) AND indpred IS NOT NULL")
                assert cur.fetchone()[0]==2
                cur.execute("SELECT indisunique FROM pg_index WHERE indexrelid='public.idx_tx_source_identity'::regclass")
                assert cur.fetchone()[0] is True
                cur.execute("SELECT count(*) FROM public.transactions");assert cur.fetchone()[0]==200
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("RESET ROLE");cur.execute("RESET SESSION AUTHORIZATION");cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
                cur.execute((ROOT/'sql/bootstrap/remove_temporary_identity.sql').read_text())
                cur.execute("SELECT count(*) FROM pg_roles WHERE rolname='fintrust_migrate_dev'");assert cur.fetchone()[0]==0
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

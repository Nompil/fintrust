"""Disposable GitHub CI PostgreSQL 16 privilege rehearsal; never RDS."""
import json
import os
from pathlib import Path
import psycopg2
from psycopg2.extensions import parse_dsn
ROOT=Path(__file__).resolve().parents[1]

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
            cur.execute("CREATE DATABASE fintrust OWNER fintrust_admin")
        v['dbname']='fintrust';conn=psycopg2.connect(**v)
        try:
            with conn.cursor() as cur:
                cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
                source=(ROOT/'sql/schema.sql').read_text().split('-- Additive identity hardening.')[0].replace('CREATE EXTENSION IF NOT EXISTS pgcrypto;','')
                cur.execute(source);cur.execute((ROOT/'sql/seed.sql').read_text())
                cur.execute((ROOT/'sql/bootstrap/temporary_identity.sql').read_text())
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
                cur.execute("SELECT pg_has_role(current_user,'rds_iam','MEMBER'), pg_has_role(current_user,'fintrust_transactions_owner','SET'), rolcreaterole, rolsuper, rolinherit FROM pg_roles WHERE rolname=current_user")
                assert cur.fetchone()==(True,True,False,False,False)
                cur.execute("SELECT has_schema_privilege(current_user,'public','CREATE')");assert cur.fetchone()[0] is False
                cur.execute("SET ROLE fintrust_transactions_owner")
                source=(ROOT/'sql/migrations/001_transaction_identity.sql').read_text()
                source=source.removeprefix('BEGIN;\n').removesuffix('COMMIT;\n')
                cur.execute(source);cur.execute(source)
                cur.execute("SELECT count(*) FROM public.transactions");assert cur.fetchone()[0]==200
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("RESET ROLE");cur.execute("RESET SESSION AUTHORIZATION");cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
                cur.execute((ROOT/'sql/bootstrap/remove_temporary_identity.sql').read_text())
                cur.execute("SELECT count(*) FROM pg_roles WHERE rolname='fintrust_migrate_dev'");assert cur.fetchone()[0]==0
                cur.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.transactions'::regclass");assert cur.fetchone()[0]=='fintrust_transactions_owner'
                cur.execute("RESET SESSION AUTHORIZATION")
                cur.execute("SELECT count(*) FROM public.transactions");assert cur.fetchone()[0]==200
            conn.commit()
        finally:conn.close()
        return {"postgresql_major":16,"bootstrap_migrate_rerun_cleanup_passed":True,"legacy_rows_preserved":200,
                "aws_rds_iam_auth_tested":False,"note":"Local placeholder rds_iam role tests membership/SQL only; real RDS IAM/TLS remains live preflight."}
    finally:
        # This dedicated CI service is disposable. Do not run cleanup against any other server.
        admin.close()

if __name__=='__main__':
    result=run();out=ROOT/'build/migration-runner/pg16-role-rehearsal.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

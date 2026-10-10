"""Separate disposable PG16-only rehearsal of 002 after the existing 001 gate."""
import os,sys,json
from pathlib import Path
import psycopg2
from psycopg2.extensions import parse_dsn
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from migration_runner import common,workflows
from tools.check_migration_roles_pg16 import expect_denied

def run():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("CI")!="true":raise RuntimeError("Disposable CI only")
    target=parse_dsn(os.environ["FINTRUST_TEST_DATABASE_URL"])
    assert target['dbname']=='fintrust_test' and target['host'] in {'localhost','127.0.0.1','::1'} and target['user']=='postgres'
    target['dbname']='fintrust';conn=psycopg2.connect(**target)
    # TLS/real RDS IAM remains a live gate, not a local service claim.
    session_guard=common.session_check;common.session_check=lambda cur,user:None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('server_version_num')::int");assert 160000<=cur.fetchone()[0]<170000
            cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
            cur.execute("CREATE ROLE fintrust_migrate_dev LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
            cur.execute("GRANT rds_iam TO fintrust_migrate_dev")
            cur.execute("GRANT CONNECT ON DATABASE fintrust TO fintrust_migrate_dev")
            cur.execute("GRANT USAGE ON SCHEMA public TO fintrust_migrate_dev")
            for table,key in [('customers','customer_id'),('accounts','account_id'),('risk_events','risk_event_id'),('alerts','alert_id'),('processed_transactions','tx_id')]:
                cur.execute(f"GRANT SELECT({key}) ON public.{table} TO fintrust_migrate_dev")
            cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
            cur.execute("SET ROLE fintrust_transactions_owner")
            cur.execute("GRANT SELECT ON public.transactions TO fintrust_migrate_dev")
            cur.execute("RESET ROLE")
            cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
        conn.commit()
        result,write=workflows.bootstrap(conn,'bootstrap002');assert write and not result['migration_executed'];conn.commit()
        with conn.cursor() as cur:
            cur.execute("RESET SESSION AUTHORIZATION");cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
            expect_denied(cur,"SET ROLE fintrust_workflow_owner")
            expect_denied(cur,"CREATE TABLE public.unapproved(id integer)")
            expect_denied(cur,"INSERT INTO public.transactions(tx_id) VALUES(gen_random_uuid())")
            expect_denied(cur,"SELECT public.fintrust_create_release1_workflows('SELECT 1')",psycopg2.errors.UndefinedFunction)
        conn.commit()
        # Forced postcheck failure must restore DDL and helper in one rollback.
        actual_verify=workflows.verify
        def refused(cur):raise common.Refused('forced_postcheck_failure')
        workflows.verify=refused
        try:workflows.operate(conn,'migrate002')
        except common.Refused:conn.rollback()
        else:raise AssertionError('Postcheck was not enforced')
        finally:workflows.verify=actual_verify
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.ingestion_batches') IS NULL,to_regprocedure('public.fintrust_create_release1_workflows()') IS NOT NULL");assert cur.fetchone()==(True,True)
        conn.rollback()
        # Existing partial object refuses, without auto-repair.
        with conn.cursor() as cur:
            cur.execute("RESET SESSION AUTHORIZATION");cur.execute("CREATE TABLE public.ingestion_batches(unapproved integer)");cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
        conn.commit()
        try:workflows.operate(conn,'migrate002')
        except common.Refused:conn.rollback()
        else:raise AssertionError('Partial state not refused')
        with conn.cursor() as cur:
            cur.execute("RESET SESSION AUTHORIZATION");cur.execute("DROP TABLE public.ingestion_batches");cur.execute("SET SESSION AUTHORIZATION fintrust_migrate_dev")
        conn.commit()
        outcome,write=workflows.operate(conn,'migrate002');assert write and outcome['status']=='APPLIED';conn.commit()
        again,write=workflows.operate(conn,'migrate002');assert not write and again['status']=='ALREADY_APPLIED';conn.rollback()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.transactions");assert cur.fetchone()[0]==200
            cur.execute("SELECT to_regprocedure('public.fintrust_create_release1_workflows()') IS NULL");assert cur.fetchone()[0]
            cur.execute("RESET SESSION AUTHORIZATION");cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
        conn.commit()
        outcome,write=workflows.cleanup(conn,'cleanup002');assert write;conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT has_schema_privilege('fintrust_workflow_owner','public','CREATE')");assert cur.fetchone()[0] is False
            cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE");cur.execute("SET ROLE fintrust_transactions_owner");cur.execute("REVOKE SELECT ON public.transactions FROM fintrust_migrate_dev");cur.execute("RESET ROLE")
            cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
            for table,key in [('customers','customer_id'),('accounts','account_id'),('risk_events','risk_event_id'),('alerts','alert_id'),('processed_transactions','tx_id')]:cur.execute(f"REVOKE SELECT({key}) ON public.{table} FROM fintrust_migrate_dev")
            cur.execute("REVOKE USAGE ON SCHEMA public FROM fintrust_migrate_dev");cur.execute("REVOKE CONNECT ON DATABASE fintrust FROM fintrust_migrate_dev");cur.execute("REVOKE rds_iam FROM fintrust_migrate_dev");cur.execute("DROP ROLE fintrust_migrate_dev")
        conn.commit()
        return {'status':'PASSED','001_then_002':True,'002_rerun_noop':True,'partial_refused':True,'forced_postcheck_rollback':True,'helper_removed':True,'login_no_schema_create_or_owner_membership':True,'arbitrary_sql_refused':True,'financial_rows_preserved':200,'cleanup':True,'aws_access':False,'real_rds_iam_tls_tested':False}
    finally:common.session_check=session_guard;conn.close()

if __name__=='__main__':
    result=run();path=ROOT/'build/migration-runner/pg16-workflows-rehearsal.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

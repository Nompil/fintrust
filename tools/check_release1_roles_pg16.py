"""Disposable PG16 service-role gate. No AWS or live database access.
Explicit execution required in the approved CI/test environment; never skip this gate.
"""
import os
import sys
import json
import uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
from fintrust import migrations

def main():
    dsn=os.environ["FINTRUST_TEST_DATABASE_URL"];target=parse_dsn(dsn)
    if target.get("host") not in {"localhost","127.0.0.1","::1"} or target.get("dbname") not in {"fintrust_test","fintrust_local_test"}:
        raise ValueError("Disposable loopback test database required")
    conn=psycopg2.connect(dsn);name="release1_privilege_"+uuid.uuid4().hex
    probes=[]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('server_version_num')::int,rolsuper FROM pg_roles WHERE rolname=current_user")
            version,admin=cur.fetchone()
            if not 160000<=version<170000 or not admin:raise ValueError("PostgreSQL 16 disposable administrator required")
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
            cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(name)))
            cur.execute((ROOT/"sql/schema.sql").read_text().split("-- Additive identity hardening.")[0].replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;",""))
            cur.execute((ROOT/"sql/seed.sql").read_text())
        conn.commit();migrations.apply_local(conn,1,schema=name);migrations.apply_local(conn,2,schema=name)
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(name)))
            for file in ("permissions.sql","release1_permissions.sql"):
                text=(ROOT/"infrastructure/rds"/file).read_text().replace("public",name)
                cur.execute("\n".join(line for line in text.splitlines() if line.strip() not in {"BEGIN;","COMMIT;"}))
        # All role creation/grants/ownership changes above remain rollback-only.
        class Scoped:
            def cursor(self,*a,**kw):return conn.cursor(*a,**kw)
            def commit(self):pass
            def rollback(self):raise AssertionError("Unexpected worker rollback during privilege proof")
            def close(self):pass
            def __enter__(self):return self
            def __exit__(self,*a):return False
        from fintrust import score,release_workflow as worker,dynamo,workflow_api,auth
        score.get_connection=lambda:Scoped();worker.get_connection=lambda:Scoped()
        dynamo.publish_score=lambda *a,**kw:None
        from fintrust.release_ingest import envelopes
        account="20000000-0000-4000-8000-000000000001"
        body=("account_id,amount,currency,country,tx_date,tx_type,source_system,source_transaction_id\n"
              +account+",200000.01,ZAR,US,2024-02-29T12:00:00Z,debit,synthetic-pg16,PRIVILEGE-001\n").encode()
        item=envelopes("synthetic-input","raw/privilege.csv",body,version="synthetic-v1")[0]
        with conn.cursor() as cur:cur.execute("SET LOCAL ROLE fintrust_scoring")
        result=worker.process_envelope(item);assert result["status"]=="ACCEPTED";probes.append("scoring_role_real_worker_commit_hook_and_review")
        with conn.cursor() as cur:cur.execute("RESET ROLE; SET LOCAL ROLE fintrust_workflow_api")
        response=workflow_api.update_review(result["risk_event_id"],{"request_id":str(uuid.uuid4()),"expected_version":1,"status":"UNDER_REVIEW","notes":"PG16 service-role proof","resolution_code":None},auth.Principal("ci-analyst","Risk/Compliance Analyst",(account,)))
        assert response["version"]==2;probes.append("api_role_review_trigger_appends_history_without_direct_insert")
        with conn.cursor() as cur:
            for table,privilege in [("transactions","INSERT"),("transactions","UPDATE"),("transactions","DELETE"),("risk_events","INSERT"),("risk_review_history","INSERT"),("risk_review_history","UPDATE"),("risk_review_history","DELETE")]:
                cur.execute("SELECT has_table_privilege(current_user,%s,%s)",(name+"."+table,privilege));assert cur.fetchone()==(False,)
                probes.append("api_denied_"+table+"_"+privilege.lower())
            cur.execute("SELECT has_schema_privilege(current_user,%s,'CREATE')",(name,));assert cur.fetchone()==(False,)
            cur.execute("SELECT count(*) FROM risk_review_history WHERE risk_event_id=%s",(result["risk_event_id"],));assert cur.fetchone()==(2,)
            cur.execute("RESET ROLE")
            cur.execute("SELECT count(*) FROM transactions");assert cur.fetchone()==(201,)
        conn.rollback()
        # Rollback removes privilege-test financial writes and any new global roles/grants.
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT count(*) FROM {}.transactions").format(sql.Identifier(name)));assert cur.fetchone()==(200,)
        evidence={"status":"PASSED","postgresql_version_num":version,"probes":probes,"rows_preserved":200,"aws_access":False,"schema_cleanup":"completed","privilege_changes":"rolled back"}
    finally:
        conn.rollback()
        with conn.cursor() as cur:cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(name)))
        conn.commit();conn.close()
    output=ROOT/"docs/EVIDENCE/12-e2e/release1-closure/postgres16-roles.json";output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8");print(json.dumps(evidence,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())

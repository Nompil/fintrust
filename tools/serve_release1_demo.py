"""Loopback-only synthetic Release1 workspace. No AWS or live-RDS access.
Uses the dedicated fintrust_local_test database, an isolated labelled schema,
and in-process S3/DynamoDB mocks. Does not claim cloud/least-privilege proof.
"""
import argparse
import csv
from getpass import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import threading
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
SCHEMA="fintrust_release1_candidate"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role",choices=["Admin","Analyst","Auditor","Maintainer"],default="Admin")
    parser.add_argument("--port",type=int,default=5001)
    parser.add_argument("--seed-scenarios",action="store_true",help="Add labelled constructed scenarios; not the external CSV A/B")
    args=parser.parse_args()
    if not 1024<=args.port<=65535:raise ValueError("Use a nonprivileged loopback port")
    from tools.local import local_settings,TEST_DATABASE,ROLE
    from psycopg2.extensions import make_dsn
    import psycopg2
    from psycopg2 import sql
    from fintrust.migrations import apply_local
    values=local_settings()
    dsn=make_dsn(host=values["DB_HOST"],port=values.get("DB_PORT","5432"),dbname=TEST_DATABASE,user=ROLE,password=values["DB_PASSWORD"],connect_timeout=5)
    def connect():
        conn=psycopg2.connect(dsn)
        with conn.cursor() as cur:cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(SCHEMA)))
        conn.commit();return conn
    conn=psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_get_userbyid(nspowner),obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname=%s",(SCHEMA,));existing=cur.fetchone()
                if existing and existing!=(ROLE,"FinTrust isolated synthetic Release1 candidate"):
                    raise ValueError("Existing schema is unrelated and was left unchanged")
                if not existing:
                    cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(SCHEMA)))
                    cur.execute(sql.SQL("COMMENT ON SCHEMA {} IS 'FinTrust isolated synthetic Release1 candidate'").format(sql.Identifier(SCHEMA)))
                    cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(SCHEMA)))
                    cur.execute((ROOT/"sql/schema.sql").read_text().split("-- Additive identity hardening.")[0].replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;",""))
                    cur.execute((ROOT/"sql/seed.sql").read_text())
        apply_local(conn,1,schema=SCHEMA);apply_local(conn,2,schema=SCHEMA)
    finally:conn.close()
    token=getpass("Local demo access token (>=32 random characters; hidden, never stored plaintext): ")
    if not 32<=len(token)<=256:raise ValueError("Token length must be 32..256")
    role={"Admin":"Admin","Analyst":"Risk/Compliance Analyst","Auditor":"Read-only/Auditor","Maintainer":"Maintainer"}[args.role]
    file=ROOT/".env.release1-auth.json"
    registry=json.loads(file.read_text()) if file.exists() else {"principals":[]}
    subject="local-"+args.role.lower();digest=hashlib.sha256(token.encode()).hexdigest();token=None
    registry["principals"]=[p for p in registry["principals"] if p["subject"]!=subject]
    if any(p["token_sha256"]==digest for p in registry["principals"]):raise ValueError("Use a different token for each local role")
    registry["principals"].append({"subject":subject,"role":role,"accounts":["20000000-0000-4000-8000-00000000000"+str(i) for i in range(1,6)],"token_sha256":digest})
    file.write_text(json.dumps(registry,indent=2)+"\n",encoding="utf-8")
    os.environ.update(FINTRUST_AUTH_FILE=str(file),FINTRUST_LOCAL_DEMO="0",FINTRUST_RELEASE1="1",FINTRUST_RELEASE1_UPLOAD="1",INPUT_BUCKET="release1-input",FINTRUST_ACCOUNT_ID="966467878406",DYNAMODB_TABLE="release1-scores",QUARANTINE_BUCKET="release1-demo-safe",AWS_ACCESS_KEY_ID="testing",AWS_SECRET_ACCESS_KEY="testing",AWS_SESSION_TOKEN="testing",AWS_DEFAULT_REGION="af-south-1",AWS_EC2_METADATA_DISABLED="true",AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true")
    from moto import mock_aws
    from botocore.httpsession import URLLib3Session
    import boto3
    import subprocess
    os.environ["FINTRUST_RELEASE_COMMIT"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    stop=threading.Event()
    with mock_aws(),patch.object(URLLib3Session,"send",side_effect=RuntimeError("Unmocked AWS request blocked by local demo")):
        from fintrust import api,db,ingest,score,dynamo,release_workflow as worker
        for module in (api,db,ingest,score,worker):module.get_connection=connect
        s3=boto3.client("s3",region_name="af-south-1");s3.create_bucket(Bucket="release1-demo-safe",CreateBucketConfiguration={"LocationConstraint":"af-south-1"})
        s3.put_bucket_versioning(Bucket="release1-demo-safe",VersioningConfiguration={"Status":"Enabled"})
        s3.create_bucket(Bucket="release1-input",CreateBucketConfiguration={"LocationConstraint":"af-south-1"});s3.put_bucket_versioning(Bucket="release1-input",VersioningConfiguration={"Status":"Enabled"})
        score.s3=s3;ingest.s3=s3
        dynamo.dynamodb=boto3.resource("dynamodb",region_name="af-south-1")
        dynamo.dynamodb.create_table(TableName="release1-scores",BillingMode="PAY_PER_REQUEST",AttributeDefinitions=[{"AttributeName":x,"AttributeType":"S"} for x in ("account_id","score_date")],KeySchema=[{"AttributeName":"account_id","KeyType":"HASH"},{"AttributeName":"score_date","KeyType":"RANGE"}])
        if args.seed_scenarios:
            from fintrust.release_ingest import envelopes
            import uuid
            from datetime import datetime,timezone
            now=datetime.now(timezone.utc).isoformat();tag=uuid.uuid4().hex
            rows=[{"account_id":"20000000-0000-4000-8000-000000000001","amount":amount,"currency":"ZAR","country":country,"tx_date":now,"tx_type":"debit","source_system":"constructed-local-demo","source_transaction_id":tag+str(i)} for i,(amount,country) in enumerate([("10","ZA"),("200000.01","US"),("bad","ZA")])]
            text=io.StringIO(newline="");writer=csv.DictWriter(text,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            for item in envelopes("constructed-input","raw/constructed-"+tag+".csv",text.getvalue().encode(),version="local-mock-v1"):worker.process_envelope(item)
        def drain():
            while not stop.wait(2):
                try:
                    worker.drain_corrections(limit=10)
                    worker.drain_projections(limit=10)
                except Exception as error:print("Correction worker failed:",type(error).__name__,"(pending work retained)")
        thread=threading.Thread(target=drain,daemon=True);thread.start()
        try:
            print(f"LOCAL ONLY: synthetic dedicated PostgreSQL + temporary AWS mocks. http://127.0.0.1:{args.port}/release1")
            print("Mock S3 evidence is in memory and ends with this session. This is not a live release or privilege proof.")
            api.app.run(host="127.0.0.1",port=args.port,debug=False,use_reloader=False)
        finally:stop.set();thread.join(timeout=15)
    return 0

if __name__=="__main__":raise SystemExit(main())

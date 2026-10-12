"""Strict intake -> real isolated PostgreSQL -> mocked projection -> authenticated UI API.
No live AWS transport. Dedicated test database required; missing DB is a failure.
"""
import csv
import io
import json
import hashlib
import uuid
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import pytest
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
from moto import mock_aws
import boto3
from fintrust import api,score,release_ingest as intake,release_workflow as worker,workflow_api as service,migrations,auth
from tests.test_release1_workflows import row,RECEIVED,ACCOUNT
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def release_db(monkeypatch):
    dsn=os.environ.get("FINTRUST_TEST_DATABASE_URL")
    assert dsn,"Dedicated local PostgreSQL is required; this release gate must not silently skip"
    target=parse_dsn(dsn);assert target.get("host") in {"localhost","127.0.0.1","::1"} and target["dbname"] in {"fintrust_test","fintrust_local_test"}
    name="release1_"+uuid.uuid4().hex
    conn=psycopg2.connect(dsn)
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
            cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(name)))
            base=(ROOT/"sql/schema.sql").read_text().split("-- Additive identity hardening.")[0].replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;","")
            cur.execute(base);cur.execute((ROOT/"sql/seed.sql").read_text())
    migrations.apply_local(conn,1,schema=name);migrations.apply_local(conn,2,schema=name);migrations.apply_local(conn,3,schema=name)
    def connect():
        c=psycopg2.connect(dsn)
        with c.cursor() as cur:cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(name)))
        c.commit();return c
    for module in (worker,score):monkeypatch.setattr(module,"get_connection",connect)
    def query(statement,args=()):
        c=connect()
        try:
            with c:
                with c.cursor() as cur:
                    cur.execute(statement,args);return cur.fetchall() if cur.description else []
        finally:c.close()
    monkeypatch.setenv("QUARANTINE_BUCKET","release1-safe");monkeypatch.setenv("DYNAMODB_TABLE","risk_scores")
    from fintrust import dynamo
    with mock_aws():
        s3=boto3.client("s3",region_name="af-south-1")
        s3.create_bucket(Bucket="release1-safe",CreateBucketConfiguration={"LocationConstraint":"af-south-1"})
        s3.put_bucket_versioning(Bucket="release1-safe",VersioningConfiguration={"Status":"Enabled"})
        monkeypatch.setattr(score,"s3",s3)
        resource=boto3.resource("dynamodb",region_name="af-south-1")
        resource.create_table(TableName="risk_scores",BillingMode="PAY_PER_REQUEST",AttributeDefinitions=[{"AttributeName":x,"AttributeType":"S"} for x in ("account_id","score_date")],KeySchema=[{"AttributeName":"account_id","KeyType":"HASH"},{"AttributeName":"score_date","KeyType":"RANGE"}])
        monkeypatch.setattr(dynamo,"dynamodb",resource)
        try:yield conn,name,connect,query,s3
        finally:
            conn.rollback()
            with conn.cursor() as cur:cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
            conn.commit();conn.close()

def file_bytes(rows):
    output=io.StringIO(newline="");writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);return output.getvalue().encode()

def feed(rows,filename="raw/release.csv"):
    items=intake.envelopes("synthetic-input",filename,file_bytes(rows),version="v1")
    for item in items:item["batch"]["ingested_at"]=RECEIVED.isoformat()
    return items

def run(items):return [worker.process_envelope(item) for item in items]

@pytest.mark.parametrize("payload,code",[(b"","EMPTY_FILE"),(b"account_id;amount\nx;1","MISSING_HEADERS"),(b"Account_id,amount","MISSING_HEADERS"),(b"account_id,account_id","DUPLICATE_HEADERS"),(file_bytes([row()]).splitlines()[0]+b"\n","HEADER_ONLY_FILE"),(b"x"*1048577,"FILE_TOO_LARGE")],ids=["empty","delimiter","header-case","duplicate-header","header-only","oversized-file"])
def test_file_rejection_has_no_financial_work(payload,code):
    items=intake.envelopes("bucket","raw/a.csv",payload)
    assert len(items)==1 and items[0]["kind"]=="FILE_FAILURE" and items[0]["error_code"]==code

def test_csv_shape_quotes_bom_reorder_and_late_malformed():
    payload=file_bytes([row(merchant="Shop, Cape Town")]);assert intake.parse_file(b"\xef\xbb\xbf"+payload)[0][1]["merchant"]=="Shop, Cape Town"
    reversed_row=dict(reversed(list(row().items())));assert intake.parse_file(file_bytes([reversed_row]))[0][1]==row()
    shifted=payload+payload.splitlines()[1]+b",extra\n";assert intake.parse_file(shifted)[-1][2]=="MALFORMED_ROW"
    with pytest.raises(intake.FileRejected,match="MALFORMED_CSV"):intake.parse_file(payload+b'"unterminated')
    with pytest.raises(intake.FileRejected,match="UNSUPPORTED_HEADERS"):intake.parse_file(file_bytes([row(email="private")]))

def test_mixed_rows_reconcile_and_replay_preserves_every_occurrence(release_db):
    _,_,_,q,_=release_db
    items=feed([row(),row(),row(source_transaction_id="REF-001",amount="11"),row(source_transaction_id="BAD",amount="0",country="ZZ",currency="XXX"),row(source_transaction_id="GOOD",amount="200000.01",country="US")])
    result=run(items)
    assert [x["status"] for x in result[:-1]]==["ACCEPTED","DUPLICATE","QUARANTINED","QUARANTINED","ACCEPTED"]
    assert result[2]["validation_errors"][0]["reason_code"]=="DUPLICATE_IDENTITY_CONFLICT"
    assert len(result[3]["validation_errors"])==3
    assert q("SELECT status,accepted,quarantined,duplicate,pending,counts_consistent FROM batch_reconciliation")==[("COMPLETED",2,2,1,0,True)]
    assert q("SELECT count(*) FROM risk_reviews")==[(1,)]
    run(items);assert q("SELECT count(*) FROM transactions")==[(202,)]
    cross=feed([row()],"raw/companion.csv");cross[0]["batch"]["batch_id"]=str(uuid.uuid4());cross[1]["batch"]=cross[0]["batch"]
    # Different file bytes are normally different batches; explicit distinct occurrence tests identity reuse.
    assert run(cross)[0]["status"]=="DUPLICATE"

def test_partial_batch_and_dynamo_failure_after_sql_retries(release_db,monkeypatch):
    _,_,_,q,_=release_db;items=feed([row(),row(source_transaction_id="SECOND",amount="12")])
    from fintrust import dynamo
    original=dynamo.publish_score
    monkeypatch.setattr(dynamo,"publish_score",lambda *a:(_ for _ in ()).throw(RuntimeError("Injected Dynamo failure")))
    with pytest.raises(RuntimeError):worker.process_envelope(items[0])
    assert q("SELECT accepted,pending,status FROM batch_reconciliation")==[(1,1,"PROCESSING")]
    assert q("SELECT state FROM projection_outbox")==[("PENDING",)]
    monkeypatch.setattr(dynamo,"publish_score",original);run(items)
    assert q("SELECT count(*) FROM transactions")==[(202,)]
    assert q("SELECT accepted,pending,status FROM batch_reconciliation")==[(2,0,"COMPLETED")]
    worker.rebuild_projection(q("SELECT tx_id::text FROM processed_transactions LIMIT 1")[0][0])

def test_unknown_inactive_and_invalid_rows_are_quarantine_not_dlq(release_db):
    _,_,_,q,_=release_db
    q("UPDATE accounts SET status='closed' WHERE account_id=%s",(ACCOUNT,))
    result=run(feed([row(),row(source_transaction_id="U",account_id=str(uuid.uuid4())),row(source_transaction_id="T",tx_date="2026-10-09T10:05:00.000001Z")]))
    assert [x["validation_errors"][0]["reason_code"] for x in result[:-1]]==["INACTIVE_ACCOUNT","UNKNOWN_ACCOUNT","FUTURE_TIMESTAMP"]
    assert q("SELECT count(*) FROM transactions")==[(200,)]

@pytest.mark.parametrize("attempt",range(3))
def test_concurrent_identical_delivery_and_changed_occurrence(release_db,attempt):
    _,_,_,q,_=release_db;item=feed([row()])[0]
    with ThreadPoolExecutor(2) as executor:results=list(executor.map(worker.process_envelope,[item,item]))
    assert {x["status"] for x in results}=={"ACCEPTED"}
    assert q("SELECT count(*) FROM transactions")==[(201,)]
    altered={**item,"row":row(amount="11")}
    with pytest.raises(ValueError,match="content changed"):worker.process_envelope(altered)

def test_migration_order_rerun_and_catalog_drift(release_db):
    conn,name,_,q,_=release_db
    assert migrations.apply_local(conn,1,schema=name)=="ALREADY_APPLIED"
    assert migrations.apply_local(conn,2,schema=name)=="ALREADY_APPLIED"
    q("ALTER TABLE risk_reviews ADD COLUMN unreviewed TEXT")
    with pytest.raises(migrations.SchemaDrift):migrations.apply_local(conn,2,schema=name)
    assert q("SELECT count(*) FROM transactions")==[(200,)]

@pytest.fixture
def authenticated_client(tmp_path,monkeypatch):
    tokens={"Admin":"a"*64,"Risk/Compliance Analyst":"b"*64,"Read-only/Auditor":"c"*64}
    file=tmp_path/"auth.json"
    file.write_text(json.dumps({"principals":[{"subject":role,"role":role,"accounts":[ACCOUNT],"token_sha256":hashlib.sha256(token.encode()).hexdigest()} for role,token in tokens.items()]}))
    monkeypatch.setenv("FINTRUST_AUTH_FILE",str(file))
    return api.app.test_client(),lambda role:{"Authorization":"Bearer "+tokens[role]}

def test_api_authentication_roles_and_no_header_escalation(authenticated_client):
    client,headers=authenticated_client
    assert client.get("/v1/session").status_code==401
    assert client.get("/v1/session",headers={"X-Role":"Admin"}).status_code==401
    assert client.get("/v1/session",headers=headers("Read-only/Auditor")).json["data"]["role"]=="Read-only/Auditor"
    assert client.post("/v1/reviews/1/transition",json={},headers=headers("Read-only/Auditor")).status_code==403
    assert client.get("/v1/transactions?account_id="+str(uuid.uuid4()),headers=headers("Admin")).status_code==403
    assert client.post("/v1/reviews/1/transition",data="bad",content_type="application/json",headers=headers("Risk/Compliance Analyst")).status_code==400

def test_review_api_stale_idempotent_audit_and_ledger_immutable(release_db,authenticated_client):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    run(feed([row(amount="200000.01",country="US")]))
    event=q("SELECT risk_event_id FROM risk_reviews")[0][0]
    body={"request_id":str(uuid.uuid4()),"expected_version":1,"status":"UNDER_REVIEW","notes":"Investigating","resolution_code":None}
    path=f"/v1/reviews/{event}/transition"
    response=client.post(path,json=body,headers=headers("Risk/Compliance Analyst"));assert response.status_code==200,response.json
    assert client.post(path,json=body,headers=headers("Risk/Compliance Analyst")).json["data"]["replayed"]
    assert client.post(path,json={**body,"request_id":str(uuid.uuid4())},headers=headers("Risk/Compliance Analyst")).status_code==409
    assert client.post(path,json={**body,"amount":"1"},headers=headers("Risk/Compliance Analyst")).status_code==400
    cleared={**body,"request_id":str(uuid.uuid4()),"expected_version":2,"status":"CLEARED","notes":"Verified activity","resolution_code":"VALID_ACTIVITY"}
    assert client.post(path,json=cleared,headers=headers("Risk/Compliance Analyst")).status_code==200
    assert q("SELECT count(*) FROM risk_review_history")==[(3,)]
    assert q("SELECT amount::text FROM transactions WHERE source_transaction_id='REF-001'")==[("200000.01",)]
    assert client.get("/v1/workflows/audit",headers=headers("Risk/Compliance Analyst")).status_code==403
    assert client.get("/v1/workflows/reviews?limit=100000",headers=headers("Admin")).status_code==400
    assert client.get("/v1/workflows/reviews?status=OPEN' OR TRUE",headers=headers("Admin")).status_code==400

def test_correction_api_revalidates_deduplicates_and_preserves_original(release_db,authenticated_client):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    run(feed([row(amount="bad")]))
    case=q("SELECT quarantine_id::text FROM quarantine_cases")[0][0]
    body={"request_id":str(uuid.uuid4()),"action":"RESUBMIT","notes":"Corrected numeric amount","candidate":row()}
    path=f"/v1/quarantine/{case}/corrections"
    response=client.post(path,json=body,headers=headers("Risk/Compliance Analyst"));assert response.status_code==202,response.json
    assert client.post(path,json=body,headers=headers("Risk/Compliance Analyst")).status_code==202
    assert worker.drain_corrections()=={"completed":1}
    assert q("SELECT workflow_status FROM quarantine_workflow WHERE quarantine_id=%s",(case,))==[("RESOLVED",)]
    assert q("SELECT disposition FROM ingestion_records WHERE batch_id=(SELECT batch_id FROM quarantine_cases WHERE quarantine_id=%s)",(case,))==[("QUARANTINED",)]
    assert q("SELECT count(*) FROM transactions")==[(201,)]
    assert client.post(path,json={**body,"request_id":str(uuid.uuid4())},headers=headers("Risk/Compliance Analyst")).status_code==409


@pytest.mark.parametrize("seconds,expected",[(300,True),(300.000001,False)])
def test_velocity_closed_five_minute_time_boundary(release_db,seconds,expected):
    rows=[row(source_transaction_id="V"+str(i),merchant="",tx_date=(RECEIVED+timedelta(seconds=i*60)).isoformat()) for i in range(5)]
    rows.append(row(source_transaction_id="V5",merchant="",tx_date=(RECEIVED+timedelta(seconds=seconds)).isoformat()))
    items=feed(rows)
    for item in items:item["batch"]["ingested_at"]=(RECEIVED+timedelta(minutes=10)).isoformat()
    results=run(items)
    assert ("HIGH_VELOCITY" in {x["rule"] for x in results[-2]["triggered_rules"]}) is expected
    assert "HIGH_VELOCITY" not in {x["rule"] for x in results[-3]["triggered_rules"]}


def test_correction_still_invalid_and_cross_file_duplicate(release_db,authenticated_client):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    run(feed([row(source_transaction_id="ORIGINAL",amount="bad")]))
    case=q("SELECT quarantine_id::text FROM quarantine_cases")[0][0];path=f"/v1/quarantine/{case}/corrections"
    invalid={"request_id":str(uuid.uuid4()),"action":"RESUBMIT","notes":"Still invalid candidate","candidate":row(source_transaction_id="ORIGINAL",amount="0")}
    assert client.post(path,json=invalid,headers=headers("Risk/Compliance Analyst")).status_code==202
    worker.drain_corrections()
    assert q("SELECT workflow_status FROM quarantine_workflow WHERE quarantine_id=%s",(case,))==[("OPEN",)]
    assert q("SELECT count(*) FROM transactions")==[(200,)]
    run(feed([row(source_transaction_id="ORIGINAL")],"raw/another.csv"))
    fixed={**invalid,"request_id":str(uuid.uuid4()),"candidate":row(source_transaction_id="ORIGINAL")}
    assert client.post(path,json=fixed,headers=headers("Risk/Compliance Analyst")).status_code==202
    worker.drain_corrections()
    assert q("SELECT workflow_status FROM quarantine_workflow WHERE quarantine_id=%s",(case,))==[("RESOLVED",)]
    assert q("SELECT disposition FROM ingestion_records i JOIN quarantine_corrections c ON i.batch_id=c.reprocess_batch_id ORDER BY c.correction_version")==[("QUARANTINED",),("DUPLICATE",)]
    assert q("SELECT count(*) FROM transactions")==[(201,)]


def test_correction_failure_outbox_retries_and_no_sensitive_fields(release_db,authenticated_client,monkeypatch):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    run(feed([row(amount="bad")]))
    case=q("SELECT quarantine_id::text FROM quarantine_cases")[0][0];path=f"/v1/quarantine/{case}/corrections"
    body={"request_id":str(uuid.uuid4()),"action":"RESUBMIT","notes":"Corrected candidate","candidate":row(email="secret@example.com")}
    assert client.post(path,json=body,headers=headers("Risk/Compliance Analyst")).status_code==400
    body["candidate"]=row();assert client.post(path,json=body,headers=headers("Risk/Compliance Analyst")).status_code==202
    from fintrust import dynamo
    original=dynamo.publish_score
    monkeypatch.setattr(dynamo,"publish_score",lambda *a:(_ for _ in ()).throw(RuntimeError("Injected projection outage")))
    with pytest.raises(RuntimeError):worker.drain_corrections()
    assert q("SELECT state,attempts FROM correction_outbox")==[("PENDING",1)]
    assert q("SELECT count(*) FROM transactions")==[(201,)]
    monkeypatch.setattr(dynamo,"publish_score",original);worker.drain_corrections()
    assert q("SELECT state,attempts FROM correction_outbox")==[("COMPLETED",2)]
    assert q("SELECT count(*) FROM transactions")==[(201,)]


@pytest.mark.parametrize("changed",[{"request_id":None},{"request_id":123},{"status":[]},{"resolution_code":{}},{"expected_version":True},{"expected_version":-1}])
def test_malformed_review_json_is_400(release_db,authenticated_client,changed):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    run(feed([row(amount="200000.01",country="US")]))
    event=q("SELECT risk_event_id FROM risk_reviews")[0][0]
    body={"request_id":str(uuid.uuid4()),"expected_version":1,"status":"UNDER_REVIEW","notes":"Investigating","resolution_code":None,**changed}
    assert client.post(f"/v1/reviews/{event}/transition",json=body,headers=headers("Risk/Compliance Analyst")).status_code==400


def test_object_scope_detail_report_and_metrics(release_db,authenticated_client):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    own=q("SELECT tx_id::text FROM transactions WHERE account_id=%s LIMIT 1",(ACCOUNT,))[0][0]
    other=q("SELECT tx_id::text FROM transactions WHERE account_id<>%s LIMIT 1",(ACCOUNT,))[0][0]
    assert client.get("/v1/transactions/"+own,headers=headers("Read-only/Auditor")).status_code==200
    assert client.get("/v1/transactions/"+other,headers=headers("Admin")).status_code==404
    report=client.get("/v1/reports",headers=headers("Read-only/Auditor"));assert report.status_code==200
    assert {x["account_id"] for x in report.json["data"]}=={ACCOUNT}
    assert client.get("/v1/metrics",headers=headers("Risk/Compliance Analyst")).status_code==403
    assert client.get("/v1/metrics",headers=headers("Admin")).status_code==200
    assert client.get("/v1/workflows/reviews?limit=10&limit=20",headers=headers("Admin")).status_code==400


def test_rds_scoring_and_kms_failure_never_acknowledged(release_db,monkeypatch):
    _,_,_,q,_=release_db;item=feed([row()])[0]
    original=score.persist_score
    monkeypatch.setattr(score,"persist_score",lambda *a,**kw:(_ for _ in ()).throw(psycopg2.OperationalError("Injected RDS outage")))
    with pytest.raises(psycopg2.OperationalError):worker.process_envelope(item)
    assert q("SELECT count(*) FROM transactions")==[(200,)]
    assert q("SELECT pending FROM batch_reconciliation")==[(1,)]
    monkeypatch.setattr(score,"persist_score",original)
    monkeypatch.setenv("RISK_MEDIUM","20")
    with pytest.raises(ValueError,match="frozen"):worker.process_envelope(item)
    assert q("SELECT count(*) FROM transactions")==[(200,)]
    monkeypatch.delenv("RISK_MEDIUM")
    invalid=feed([row(amount="bad")])[0]
    monkeypatch.setattr(score.s3,"put_object",lambda **kw:(_ for _ in ()).throw(RuntimeError("Injected KMS denial")))
    with pytest.raises(RuntimeError):worker.process_envelope(invalid)
    assert q("SELECT count(*) FROM quarantine_cases")==[(0,)]


def test_publication_partial_failure_and_whole_file_attempt_audit(release_db):
    _,_,_,q,s3=release_db
    sqs=boto3.client("sqs",region_name="af-south-1")
    queue=sqs.create_queue(QueueName="release1.fifo",Attributes={"FifoQueue":"true"})["QueueUrl"]
    payload=file_bytes([row(tx_date="2024-02-29T10:00:00Z")])
    class Fail:
        def send_message_batch(self,**kw):return {"Successful":[],"Failed":[{"Id":"0"}]}
    with pytest.raises(RuntimeError):intake.publish(s3,Fail(),queue,"synthetic-input","raw/a.csv",payload,version="v1")
    first=s3.get_object(Bucket="release1-safe",Key="quarantine/batches/"+intake.metadata("synthetic-input",payload)["batch_id"]+"/receipt.json")["Body"].read()
    result=intake.publish(s3,sqs,queue,"synthetic-input","raw/a.csv",payload,version="v1")
    assert result["status"]=="QUEUED" and result["accepted"]==0
    messages=sqs.receive_message(QueueUrl=queue,MaxNumberOfMessages=10)["Messages"]
    for m in messages:worker.process_envelope(json.loads(m["Body"]));sqs.delete_message(QueueUrl=queue,ReceiptHandle=m["ReceiptHandle"])
    assert intake.publish(s3,sqs,queue,"synthetic-input","raw/renamed.csv",payload,version="v2")["status"]=="DUPLICATE_FILE"
    control=sqs.receive_message(QueueUrl=queue,MaxNumberOfMessages=10)["Messages"][0]
    assert worker.process_envelope(json.loads(control["Body"]))["status"]=="DUPLICATE_FILE"
    assert q("SELECT count(*) FROM ingestion_records")==[(1,)]
    assert q("SELECT count(*) FROM ingestion_attempts")==[(2,)]
    last=s3.get_object(Bucket="release1-safe",Key="quarantine/batches/"+result["batch_id"]+"/receipt.json")["Body"].read()
    assert first==last


def test_strict_input_boundaries_before_s3_read(monkeypatch):
    from fintrust import ingest
    monkeypatch.setenv("FINTRUST_RELEASE1","1");monkeypatch.setenv("INPUT_BUCKET","approved")
    monkeypatch.setattr(ingest.s3,"get_object",lambda **kw:pytest.fail("Unapproved input must not be read"))
    for bucket,key,version,event in [("wrong","raw/a.csv","v1","ObjectCreated:Put"),("approved","else/a.csv","v1","ObjectCreated:Put"),("approved","raw/a.csv",None,"ObjectCreated:Put"),("approved","raw/a.csv","v1","ObjectRemoved:Delete")]:
        with pytest.raises(ValueError):ingest.lambda_handler({"Records":[{"eventName":event,"s3":{"bucket":{"name":bucket},"object":{"key":key,"versionId":version}}}]},None)


def test_migration_order_partial_conflict_and_transactional_rollback(release_db):
    conn,name,_,q,_=release_db
    second="migration_order_"+uuid.uuid4().hex
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(second)))
            cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(second)))
            cur.execute((ROOT/"sql/schema.sql").read_text().split("-- Additive identity hardening.")[0].replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;",""))
            cur.execute((ROOT/"sql/seed.sql").read_text())
    try:
        with pytest.raises(migrations.SchemaDrift):migrations.apply_local(conn,2,schema=second)
        assert migrations.apply_local(conn,1,schema=second)=="APPLIED"
        with conn:
            with conn.cursor() as cur:cur.execute(sql.SQL("CREATE TABLE {}.risk_reviews(conflict INTEGER)").format(sql.Identifier(second)))
        with pytest.raises(psycopg2.Error):migrations.apply_local(conn,2,schema=second)
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)",(second+".ingestion_batches",));assert cur.fetchone()==(None,)
            cur.execute(sql.SQL("SELECT count(*) FROM {}.transactions").format(sql.Identifier(second)));assert cur.fetchone()==(200,)
            cur.execute(sql.SQL("SELECT version FROM {}.schema_migrations").format(sql.Identifier(second)));assert cur.fetchall()==[(1,)]
    finally:
        conn.rollback()
        with conn.cursor() as cur:cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(second)))
        conn.commit()


def test_quarantine_detail_safe_payload_and_history(release_db,authenticated_client):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    run(feed([row(amount="bad")]))
    case=q("SELECT quarantine_id::text FROM quarantine_cases")[0][0]
    result=client.get("/v1/quarantine/"+case,headers=headers("Risk/Compliance Analyst"))
    assert result.status_code==200 and result.json["data"]["candidate"]["amount"]=="bad"
    assert result.json["data"]["source"]["version"]=="v1"
    assert result.json["data"]["correction_history"]==[]


def test_new_runtime_policy_scopes_are_opt_in_and_no_ledger_admin():
    from infrastructure.iam.create_roles import build_policies
    options=dict(quarantine_bucket="safe-bucket",kms_key_arn="arn:aws:kms:af-south-1:966467878406:key/example")
    old=build_policies("966467878406","af-south-1","dev","raw-bucket","scores","db-example","sender@example.com",**options)
    new=build_policies("966467878406","af-south-1","dev","raw-bucket","scores","db-example","sender@example.com",release1=True,**options)
    statements=new["api"]["Statement"]
    assert any(s["Action"]==["s3:GetObjectVersion"] and s["Resource"].endswith("/quarantine/release1/*") for s in statements)
    assert any(s["Action"]==["s3:PutObject"] and s["Resource"].endswith("/quarantine/corrections/*") for s in statements)
    assert not any(any(a.startswith("s3:") for a in s["Action"]) for s in old["api"]["Statement"])
    assert not any(any(a.startswith(("iam:","rds:")) for a in s["Action"]) for s in statements)


def test_release1_projection_replay_sends_one_logical_alert(release_db,monkeypatch):
    _,_,_,q,_=release_db
    from fintrust import alert_delivery,dynamo
    from unittest.mock import Mock
    monkeypatch.setattr(alert_delivery,"dynamodb",dynamo.dynamodb)
    monkeypatch.setenv("SES_SENDER","synthetic@example.com");monkeypatch.setenv("SES_RECIPIENT","reviewer@example.com")
    send=Mock(return_value={"MessageId":"synthetic-message"});monkeypatch.setattr(alert_delivery.ses,"send_email",send)
    items=feed([row(amount="200000.01",country="US")]);result=run(items)[0]
    assert alert_delivery.deliver(ACCOUNT,result["transaction_id"])["status"]=="SENT"
    run(items);assert alert_delivery.deliver(ACCOUNT,result["transaction_id"])["status"]=="SENT"
    assert send.call_count==1 and q("SELECT count(*) FROM risk_reviews")==[(1,)]


def test_empty_file_worker_is_failed_not_success(release_db):
    _,_,_,q,_=release_db
    result=run(intake.envelopes("bucket","raw/empty.csv",b""))
    assert result[0]["status"]=="FAILED"
    assert q("SELECT rows_received,status FROM batch_reconciliation")==[(0,"FAILED")]


def test_multiple_errors_include_unknown_account_deterministically(release_db):
    result=run(feed([row(account_id=str(uuid.uuid4()),amount="bad",currency="XXX",tx_date="not-a-time")]))[0]
    assert [x["reason_code"] for x in result["validation_errors"]]==["UNKNOWN_ACCOUNT","INVALID_AMOUNT","UNSUPPORTED_CURRENCY","INVALID_TIMESTAMP"]


def test_fresh_empty_database_migration_sequence(release_db):
    conn,_,_,_,_=release_db;name="fresh_release1_"+uuid.uuid4().hex
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
            cur.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(name)))
            cur.execute((ROOT/"sql/schema.sql").read_text().split("-- Additive identity hardening.")[0].replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;",""))
    try:
        assert migrations.apply_local(conn,1,schema=name)=="APPLIED"
        assert migrations.apply_local(conn,2,schema=name)=="APPLIED"
        assert migrations.apply_local(conn,2,schema=name)=="ALREADY_APPLIED"
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT count(*) FROM {}.transactions").format(sql.Identifier(name)));assert cur.fetchone()==(0,)
            cur.execute(sql.SQL("SELECT version FROM {}.schema_migrations ORDER BY version").format(sql.Identifier(name)));assert cur.fetchall()==[(1,),(2,)]
    finally:
        conn.rollback()
        with conn.cursor() as cur:cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
        conn.commit()


def test_report_pagination_and_no_mixed_batch_scope_leak(release_db):
    run(feed([row(),row(account_id="20000000-0000-4000-8000-000000000002",source_transaction_id="OTHER")]))
    analyst=auth.Principal("analyst","Risk/Compliance Analyst",(ACCOUNT,))
    assert service.list_page("batches",analyst,{})["data"]==[]
    admin=auth.Principal("admin","Admin",(ACCOUNT,"20000000-0000-4000-8000-000000000002"))
    assert len(service.list_page("batches",admin,{})["data"])==1
    first=service.report(admin,{"limit":"1"});assert len(first["data"])==1 and first["meta"]["has_more"]
    assert service.report(admin,{"limit":"1","offset":"1"})["data"]!=first["data"]
    with pytest.raises(ValueError):service.report(admin,{"limit":"101"})

"""Actual derived A -> B -> A HTTP lifecycle against isolated SQL and mocked AWS."""
import csv,io,json,hashlib,os
from pathlib import Path
from unittest.mock import Mock
import pytest
from tests.test_release1_end_to_end import release_db,authenticated_client
from fintrust import api,batches,db,release_workflow,alert_delivery,dynamo
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"tests/fixtures/e2e/release1"

@pytest.fixture
def dataset_db(request,monkeypatch,authenticated_client):
    read=Path.read_text
    def seeded(path,*args,**kwargs):
        text=read(path,*args,**kwargs)
        return text.replace("NOW()", "TIMESTAMPTZ '2020-01-01T00:00:00Z'") if path==ROOT/"sql/seed.sql" else text
    monkeypatch.setattr(Path,"read_text",seeded)
    database=request.getfixturevalue("release_db")
    monkeypatch.setattr(db,"get_connection",database[2])
    monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD","1");monkeypatch.setenv("FINTRUST_MODE","local");monkeypatch.setenv("INPUT_BUCKET","dataset-input")
    s3=database[4];s3.create_bucket(Bucket="dataset-input",CreateBucketConfiguration={"LocationConstraint":"af-south-1"});s3.put_bucket_versioning(Bucket="dataset-input",VersioningConfiguration={"Status":"Enabled"})
    metadata=batches.metadata
    monkeypatch.setattr(batches,"metadata",lambda bucket,payload:{**metadata(bucket,payload),"ingested_at":"2026-10-09T22:00:00+00:00"})
    for name in tuple(os.environ):
        if name.startswith("RISK_"):monkeypatch.delenv(name)
    registry=Path(os.environ["FINTRUST_AUTH_FILE"]);settings=json.loads(registry.read_text())
    for principal in settings["principals"]:principal["accounts"]=[f"20000000-0000-4000-8000-{i:012d}" for i in range(1,5)]
    registry.write_text(json.dumps(settings))
    return database

def upload(client,headers,label):
    name=f"fintrust_release1_transactions_{label}.csv"
    response=client.post("/v1/upload",headers=headers("Risk/Compliance Analyst"),data={"file":(io.BytesIO((FIXTURES/name).read_bytes()),name)})
    assert response.status_code==200,response.json
    return response.json["data"]

def expected(label):
    def ok(points=0,*rules,status="ACCEPTED"):
        return {"status":status,"score":points,"risk_level":"High" if points>=40 else "Medium" if points>=20 else "Low","rules":list(rules)}
    def bad(code):return {"status":"QUARANTINED","reason_code":code}
    if label=="A":
        rows=[ok(),ok(),ok(),ok(15,"AMOUNT_RISK"),ok(15,"AMOUNT_RISK"),ok(15,"CROSS_BORDER"),ok(30,"AMOUNT_RISK","CROSS_BORDER")]
        rows += [ok() for _ in range(11)]+[ok(30,"AMOUNT_RISK","CROSS_BORDER"),ok(status="DUPLICATE"),ok(),ok(20,"POSSIBLE_DUPLICATE_CHARGE")]
        rows += [bad(c) for c in ["MISSING_REQUIRED_FIELD","INVALID_AMOUNT","NEGATIVE_AMOUNT","ZERO_AMOUNT","INVALID_TIMESTAMP","FUTURE_TIMESTAMP","UNKNOWN_ACCOUNT","UNSUPPORTED_CURRENCY","UNSUPPORTED_COUNTRY","MISSING_SOURCE_IDENTITY","MISSING_REQUIRED_FIELD"]]
        rows += [ok() for _ in range(5)]+[ok(25,"HIGH_VELOCITY"),ok(),ok(55,"AMOUNT_RISK","CROSS_BORDER"),bad("INVALID_COUNTRY")]
        return rows
    return [ok(),ok(),ok(15,"AMOUNT_RISK",status="DUPLICATE"),ok(35,"AMOUNT_RISK","POSSIBLE_DUPLICATE_CHARGE"),ok(15,"CROSS_BORDER"),ok(15,"AMOUNT_RISK"),ok(40,"AMOUNT_RISK","CROSS_BORDER"),ok(),bad("MISSING_REQUIRED_FIELD"),bad("INVALID_AMOUNT"),bad("UNKNOWN_ACCOUNT"),bad("DUPLICATE_IDENTITY_CONFLICT")]

def check_rows(q,label,batch):
    rows=list(csv.DictReader(io.StringIO((FIXTURES/f"fintrust_release1_transactions_{label}.csv").read_text())))
    actual=q("SELECT r.source_row,r.disposition,r.reason_code,p.result FROM ingestion_records r LEFT JOIN processed_transactions p ON p.tx_id=r.canonical_tx_id WHERE r.batch_id=%s ORDER BY r.source_row",(batch,))
    oracle=expected(label);assert len(actual)==len(rows)==len(oracle)
    evidence=[]
    for source,expect,(ordinal,status,reason,result) in zip(rows,oracle,actual):
        observed={"status":status}
        if status=="QUARANTINED":observed["reason_code"]=reason
        else:observed.update(score=result["score"],risk_level=result["risk_level"],rules=[r["rule"] for r in result["triggered_rules"]])
        evidence.append({"source_row":ordinal,"source_transaction_id":source["source_transaction_id"],"expected":expect,"actual":observed})
    assert all(x["expected"]==x["actual"] for x in evidence),json.dumps(evidence,indent=2)
    return evidence

def test_dataset_hashes_and_mapping_preserve_originals():
    manifest=json.loads((FIXTURES/"manifest.json").read_text())
    for label,item in manifest["files"].items():
        assert hashlib.sha256((FIXTURES/item["filename"]).read_bytes()).hexdigest()==item["sha256"]
        assert hashlib.sha256((FIXTURES.parent/item["original"]).read_bytes()).hexdigest()==item["original_sha256"]
        assert len(expected(label))==item["rows"]

def test_actual_A_B_exact_A_replay_every_row(dataset_db,authenticated_client,monkeypatch):
    client,headers=authenticated_client;q=dataset_db[3]
    a=upload(client,headers,"A");a_rows=check_rows(q,"A",a["batch_id"])
    b=upload(client,headers,"B");b_rows=check_rows(q,"B",b["batch_id"])
    for result,counts in [(a,(42,29,12,1)),(b,(12,7,4,1))]:
        state=result["reconciliation"]
        assert tuple(state[k] for k in ("rows_received","accepted","quarantined","duplicate"))==counts
        assert state["status"]=="COMPLETED" and state["counts_consistent"] and state["pending"]==0
        assert sum(counts[1:])==counts[0]
        assert result["notification"]["severity"]=="warning"
    assert q("SELECT count(*) FROM transactions")==[(236,)]
    assert q("SELECT count(*) FROM quarantine_cases")==[(16,)]
    assert q("SELECT count(*) FROM risk_reviews")==[(7,)]
    assert sorted(q("SELECT result->>'risk_level',count(*) FROM processed_transactions GROUP BY 1"))==[("High",2),("Low",29),("Medium",5)]
    high=q("SELECT tx_id::text,result->>'account_id' FROM processed_transactions WHERE result->>'risk_level'='High'")
    monkeypatch.setattr(alert_delivery,"dynamodb",dynamo.dynamodb);monkeypatch.setenv("SES_SENDER","synthetic@example.com");monkeypatch.setenv("SES_RECIPIENT","reviewer@example.com")
    send=Mock(return_value={"MessageId":"synthetic-local"});monkeypatch.setattr(alert_delivery.ses,"send_email",send)
    for tx,account in high:alert_delivery.deliver(account,tx);alert_delivery.deliver(account,tx)
    assert send.call_count==2
    projected=dynamo.dynamodb.Table("risk_scores").scan()["Items"]
    assert len([item for item in projected if item["score_date"].startswith("TX#")])==36
    from boto3.dynamodb.types import TypeSerializer
    serializer=TypeSerializer()
    records=[{"eventName":"INSERT","dynamodb":{"SequenceNumber":str(i),"NewImage":{k:serializer.serialize(v) for k,v in item.items()}}} for i,item in enumerate(projected) if item["score_date"].startswith("TX#")]
    assert alert_delivery.lambda_handler({"Records":records},None)=={"batchItemFailures":[]}
    assert send.call_count==2
    replay=upload(client,headers,"A");assert replay["upload_status"]=="DUPLICATE_FILE"
    assert q("SELECT count(*) FROM transactions")==[(236,)] and q("SELECT count(*) FROM quarantine_cases")==[(16,)] and q("SELECT count(*) FROM risk_reviews")==[(7,)]
    for tx,account in high:alert_delivery.deliver(account,tx)
    assert send.call_count==2
    evidence={"sequence":["A","B","exact A replay"],"A":a_rows,"B":b_rows,"batches":[a,b],"replay":replay,"new_ledger":36,"quarantine":16,"review_count":7,"risk_counts":{"Low":29,"Medium":5,"High":2},"mocked_alert_sends":2,"aws_access":False}
    path=ROOT/"build/release1-lifecycle/row-results.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(evidence,indent=2,default=str))

def test_good_file_bad_rows_do_not_stop_valid_rows(dataset_db,authenticated_client):
    result=upload(*authenticated_client,"A");state=result["reconciliation"]
    assert state["accepted"]==29 and state["quarantined"]==12 and state["duplicate"]==1
    assert dataset_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='R1-HIGH-001'")==[(1,)]

def test_suspicious_valid_rows_are_ledger_not_quarantine(dataset_db,authenticated_client):
    a=upload(*authenticated_client,"A");q=dataset_db[3]
    assert q("SELECT count(*) FROM processed_transactions WHERE result->>'risk_level' IN ('Medium','High')")==[(5,)]
    assert q("SELECT count(*) FROM ingestion_records r JOIN processed_transactions p ON p.tx_id=r.canonical_tx_id WHERE p.result->>'risk_level' IN ('Medium','High') AND r.disposition='QUARANTINED'")==[(0,)]
    assert q("SELECT count(*) FROM risk_reviews WHERE review_status='OPEN'")==[(5,)]

@pytest.mark.parametrize("payload,name",[(b"", "empty.csv"),(b"bad,headers\n1,2", "wrong.csv"),(b"\x00\xff", "binary.csv"),(b"data","unsupported.exe"),(b'source_system,source_transaction_id,account_id,amount,currency,country,tx_type,tx_date\n"unterminated',"malformed.csv")])
def test_bad_file_rejected_before_any_row_work(dataset_db,authenticated_client,payload,name):
    client,headers=authenticated_client
    response=client.post("/v1/upload",headers=headers("Risk/Compliance Analyst"),data={"file":(io.BytesIO(payload),name)})
    assert response.status_code==400 and response.json["error"].startswith("Upload rejected:")
    q=dataset_db[3]
    assert q("SELECT count(*) FROM ingestion_batches")==[(0,)] and q("SELECT count(*) FROM quarantine_cases")==[(0,)] and q("SELECT count(*) FROM transactions")==[(200,)]

@pytest.mark.parametrize("status,state,severity",[("COMPLETED",{"counts_consistent":True,"accepted":33},"success"),("COMPLETED",{"counts_consistent":True,"accepted":27,"quarantined":4,"duplicate":2},"warning"),("COMPLETED",{"counts_consistent":False},"error"),("COMPLETED",{"counts_consistent":True,"pending":1},"error"),("PROCESSING",{"counts_consistent":True},"error"),("DUPLICATE_FILE",{},"warning")])
def test_upload_notifications_never_claim_partial_success(status,state,severity):
    from fintrust.upload_notifications import notification
    result=notification(status,state);assert result["severity"]==severity
    if severity=="error":assert "incomplete" in result["message"] and "successfully" not in result["message"]


def test_valid_successful_batch_has_safe_success_notification(dataset_db,authenticated_client):
    rows=list(csv.DictReader(io.StringIO((FIXTURES/"fintrust_release1_transactions_A.csv").read_text())))[:1]
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    client,headers=authenticated_client
    response=client.post("/v1/upload",headers=headers("Risk/Compliance Analyst"),data={"file":(io.BytesIO(stream.getvalue().encode()),"normal.csv")})
    assert response.status_code==200,response.json
    assert response.json["data"]["notification"]=={"severity":"success","message":"Upload completed successfully: 1 rows processed."}
    assert dataset_db[3]("SELECT count(*) FROM transactions")==[(201,)]

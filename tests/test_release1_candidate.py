"""Release1 candidate integration; real isolated SQL and explicitly mocked AWS."""
import io,json,os,uuid,hashlib
from pathlib import Path
from unittest.mock import Mock
import pytest,boto3
from botocore.exceptions import ClientError
from werkzeug.datastructures import FileStorage
from tests.test_release1_end_to_end import release_db,authenticated_client,feed,run,row,file_bytes,ACCOUNT
from fintrust import api,score,operations,release_workflow as worker,dynamo,alert_delivery
from fintrust.file_admission import admit,AdmissionError

@pytest.mark.parametrize("name",["file.pdf","file.doc","file.docx","file.xls","file.xlsx","file.json","file.zip","file.exe","file.png"])
def test_csv_only_admission(name):
    with pytest.raises(AdmissionError) as error:admit(FileStorage(stream=io.BytesIO(file_bytes([row()])),filename=name))
    assert error.value.code=="UNSUPPORTED_FILE_TYPE"

@pytest.mark.parametrize("payload,code",[(b"", "EMPTY_FILE"),(b"\xff\xfea\0", "UNSUPPORTED_ENCODING"),(b"PK\x03\x04\0binary", "INVALID_FILE_FORMAT"),(b"MZ\0binary", "INVALID_FILE_FORMAT"),(b"%PDF-1.7", "INVALID_CSV_SCHEMA"),(b'{"amount":1}', "INVALID_CSV_SCHEMA"),(b"account_id,amount\n", "INVALID_CSV_SCHEMA"),(b"x"*1048577,"FILE_TOO_LARGE"),(file_bytes([row()]).splitlines()[0]+b"\n","HEADER_ONLY_FILE")],ids=["empty","encoding","zip","executable","pdf","json","schema","oversized","header-only"])
def test_file_rejected_before_rows(payload,code):
    with pytest.raises(AdmissionError) as error:admit(FileStorage(stream=io.BytesIO(payload),filename="renamed.csv"))
    assert error.value.code==code

def test_candidate_upload_batch_duplicate_and_wrong_files(release_db,authenticated_client,monkeypatch):
    _,_,_,q,s3=release_db;client,headers=authenticated_client
    monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD","1");monkeypatch.setenv("FINTRUST_MODE","local");monkeypatch.setenv("INPUT_BUCKET","candidate-input")
    s3.create_bucket(Bucket="candidate-input",CreateBucketConfiguration={"LocationConstraint":"af-south-1"});s3.put_bucket_versioning(Bucket="candidate-input",VersioningConfiguration={"Status":"Enabled"})
    rows=[row(source_transaction_id="NORMAL"),row(amount="200000.01",country="US",source_transaction_id="RISK"),row(amount="bad",source_transaction_id="INVALID")];payload=file_bytes(rows)
    send=lambda:client.post("/v1/upload",data={"file":(io.BytesIO(payload),"a.csv")},headers=headers("Risk/Compliance Analyst"))
    response=send();assert response.status_code==200,response.json
    assert response.json["data"]["reconciliation"]["accepted"]==2
    assert response.json["data"]["reconciliation"]["quarantined"]==1
    assert send().json["data"]["upload_status"]=="DUPLICATE_FILE"
    assert q("SELECT count(*) FROM transactions")==[(202,)]
    before=q("SELECT count(*) FROM ingestion_batches")
    response=client.post("/v1/upload",data={"file":(io.BytesIO(b"MZ\0"),"binary.csv")},headers=headers("Risk/Compliance Analyst"));assert response.status_code==400 and response.json["reason_code"]=="INVALID_FILE_FORMAT"
    response=client.post("/v1/upload",data={"file":[(io.BytesIO(payload),"a.csv"),(io.BytesIO(payload),"b.csv")]},headers=headers("Risk/Compliance Analyst"));assert response.status_code==400 and response.json["reason_code"]=="INVALID_FILE_COUNT"
    assert q("SELECT count(*) FROM ingestion_batches")==before
    assert client.post("/v1/upload",data={"file":(io.BytesIO(payload),"a.csv")},headers=headers("Read-only/Auditor")).status_code==403

@pytest.fixture
def maintainer_headers(authenticated_client):
    file=Path(os.environ["FINTRUST_AUTH_FILE"]);d=json.loads(file.read_text());d["principals"].append({"subject":"technical-operator","role":"Maintainer","accounts":[ACCOUNT],"token_sha256":hashlib.sha256(b"d"*64).hexdigest()});file.write_text(json.dumps(d));return {"Authorization":"Bearer "+"d"*64}

def test_maintainer_authority_and_safe_health(release_db,authenticated_client,maintainer_headers):
    client,headers=authenticated_client
    response=client.get("/v1/operations",headers=maintainer_headers);assert response.status_code==200,response.json
    assert [x["version"] for x in response.json["data"]["migration_versions"]]==[1,2,3]
    for route in ["/v1/transactions/"+str(uuid.uuid4()),"/v1/workflows/reviews","/v1/workflows/quarantine","/v1/administration","/v1/reports"]:assert client.get(route,headers=maintainer_headers).status_code==403
    for route in ["/v1/reviews/1/transition","/v1/quarantine/"+str(uuid.uuid4())+"/corrections","/v1/upload"]:assert client.post(route,json={},headers=maintainer_headers).status_code==403
    assert client.get("/v1/operations",headers=headers("Risk/Compliance Analyst")).status_code==403
    assert client.get("/v1/administration",headers=headers("Read-only/Auditor")).status_code==403

@pytest.mark.parametrize("field,value",[("request_id",None),("action",[]),("target",{}),("notes",[])])
def test_operations_malformed_input_is_400(release_db,authenticated_client,maintainer_headers,field,value):
    client,_=authenticated_client;body={"request_id":str(uuid.uuid4()),"action":"REBUILD_PROJECTION","target":str(uuid.uuid4()),"notes":"Investigated"};body[field]=value
    assert client.post("/v1/operations/retry",json=body,headers=maintainer_headers).status_code==400

def test_audited_projection_retry_after_sql_commit(release_db,authenticated_client,maintainer_headers,monkeypatch):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    original=dynamo.publish_score;monkeypatch.setattr(dynamo,"publish_score",Mock(side_effect=RuntimeError("projection unavailable")))
    item=feed([row(amount="200000.01",country="US")])[0]
    with pytest.raises(RuntimeError):worker.process_envelope(item)
    tx=q("SELECT tx_id::text FROM projection_outbox")[0][0];body={"request_id":str(uuid.uuid4()),"action":"REBUILD_PROJECTION","target":tx,"notes":"Fixed projection service"}
    response=client.post("/v1/operations/retry",json=body,headers=maintainer_headers);assert response.status_code==200 and response.json["data"]["work"]=="QUEUED"
    assert client.post("/v1/operations/retry",json={**body,"notes":"Different"},headers=maintainer_headers).status_code==409
    assert client.post("/v1/operations/retry",json=body,headers=headers("Read-only/Auditor")).status_code==403
    monkeypatch.setattr(dynamo,"publish_score",original);assert worker.drain_projections()["completed"]==1
    assert client.post("/v1/operations/retry",json=body,headers=maintainer_headers).status_code==200
    assert q("SELECT count(*) FROM transactions")==[(201,)] and q("SELECT count(*) FROM risk_reviews")==[(1,)]
    assert q("SELECT actor_subject,state FROM operations_requests")==[("technical-operator","COMPLETED")]
    with pytest.raises(Exception):q("UPDATE operations_requests SET actor_subject='spoofed'")

def test_fifo_failure_dlq_controlled_redrive_no_duplicates(release_db,authenticated_client,maintainer_headers,monkeypatch):
    _,_,_,q,_=release_db;client,_=authenticated_client;sqs=boto3.client("sqs",region_name="af-south-1")
    account=sqs.get_queue_attributes(QueueUrl=sqs.create_queue(QueueName="fintrust-transactions-dlq-dev.fifo",Attributes={"FifoQueue":"true","VisibilityTimeout":"0"})["QueueUrl"],AttributeNames=["QueueArn"])["Attributes"]["QueueArn"].split(":")[4]
    dlq=sqs.get_queue_url(QueueName="fintrust-transactions-dlq-dev.fifo")["QueueUrl"];dlqarn=sqs.get_queue_attributes(QueueUrl=dlq,AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    queue=sqs.create_queue(QueueName="fintrust-transactions-dev.fifo",Attributes={"FifoQueue":"true","VisibilityTimeout":"0","RedrivePolicy":json.dumps({"deadLetterTargetArn":dlqarn,"maxReceiveCount":"2"})})["QueueUrl"]
    monkeypatch.setenv("FINTRUST_MODE","local");monkeypatch.setenv("FINTRUST_ACCOUNT_ID",account);monkeypatch.setenv("TRANSACTION_QUEUE_URL",queue);monkeypatch.setenv("TRANSACTION_DLQ_URL",dlq)
    item=feed([row(amount="200000.01",country="US")])[0];sqs.send_message(QueueUrl=queue,MessageBody=json.dumps(item),MessageGroupId=ACCOUNT,MessageDeduplicationId=str(uuid.uuid4()))
    original=score.persist_score;monkeypatch.setattr(score,"persist_score",Mock(side_effect=RuntimeError("RDS unavailable")))
    for _ in range(3):
        messages=sqs.receive_message(QueueUrl=queue,MaxNumberOfMessages=1).get("Messages",[])
        if messages:
            with pytest.raises(RuntimeError):worker.process_envelope(json.loads(messages[0]["Body"]))
    assert q("SELECT count(*) FROM transactions")==[(200,)]
    attrs=sqs.get_queue_attributes(QueueUrl=dlq,AttributeNames=["ApproximateNumberOfMessages"])["Attributes"];assert attrs["ApproximateNumberOfMessages"]=="1"
    monkeypatch.setattr(score,"persist_score",original)
    body={"request_id":str(uuid.uuid4()),"action":"REDRIVE","target":1,"notes":"RDS repaired, scoped redrive approved"};response=client.post("/v1/operations/retry",json=body,headers=maintainer_headers);assert response.status_code==200,response.json
    assert response.json["data"]["redriven"]==1
    assert client.post("/v1/operations/retry",json=body,headers=maintainer_headers).json["data"]["redriven"]==1
    message=sqs.receive_message(QueueUrl=queue,MaxNumberOfMessages=1)["Messages"][0];value=json.loads(message["Body"]);worker.process_envelope(value);worker.process_envelope(value);sqs.delete_message(QueueUrl=queue,ReceiptHandle=message["ReceiptHandle"])
    assert q("SELECT count(*) FROM transactions")==[(201,)] and q("SELECT count(*) FROM risk_reviews")==[(1,)]
    from fintrust import alert_delivery
    monkeypatch.setattr(alert_delivery,"dynamodb",dynamo.dynamodb);monkeypatch.setenv("SES_SENDER","synthetic@example.com");monkeypatch.setenv("SES_RECIPIENT","reviewer@example.com");send=Mock(return_value={"MessageId":"one"});monkeypatch.setattr(alert_delivery.ses,"send_email",send)
    tx=q("SELECT tx_id::text FROM projection_outbox")[0][0];alert_delivery.deliver(ACCOUNT,tx);alert_delivery.deliver(ACCOUNT,tx);assert send.call_count==1

def test_alert_definite_failure_retries_once_without_ledger_rollback(release_db,monkeypatch):
    _,_,_,q,_=release_db;result=run(feed([row(amount="200000.01",country="US")]))[0]
    monkeypatch.setattr(alert_delivery,"dynamodb",dynamo.dynamodb);monkeypatch.setenv("SES_SENDER","synthetic@example.com");monkeypatch.setenv("SES_RECIPIENT","reviewer@example.com")
    error=ClientError({"Error":{"Code":"MessageRejected"},"ResponseMetadata":{"HTTPStatusCode":400}},"SendEmail");send=Mock(side_effect=error);monkeypatch.setattr(alert_delivery.ses,"send_email",send)
    with pytest.raises(ClientError):alert_delivery.deliver(ACCOUNT,result["transaction_id"])
    table=dynamo.dynamodb.Table("risk_scores");key={"account_id":ACCOUNT,"score_date":"ALERT#"+result["transaction_id"]};assert table.get_item(Key=key)["Item"]["delivery_state"]=="FAILED"
    observed=[]
    def sent(**kwargs):observed.append(table.get_item(Key=key)["Item"]["delivery_state"]);return {"MessageId":"one"}
    monkeypatch.setattr(alert_delivery.ses,"send_email",sent);alert_delivery.deliver(ACCOUNT,result["transaction_id"]);alert_delivery.deliver(ACCOUNT,result["transaction_id"])
    assert observed==["RETRYING"] and q("SELECT count(*) FROM transactions")==[(201,)]


def test_upload_denies_unassigned_known_account_before_storage(release_db,authenticated_client,monkeypatch):
    _,_,_,q,_=release_db;client,headers=authenticated_client
    other=q("SELECT account_id::text FROM accounts WHERE account_id<>%s LIMIT 1",(ACCOUNT,))[0][0]
    monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD","1");monkeypatch.setenv("FINTRUST_MODE","local")
    upload=Mock();monkeypatch.setattr(score.s3,"put_object",upload)
    response=client.post("/v1/upload",data={"file":(io.BytesIO(file_bytes([row(account_id=other)])),"scoped.csv")},headers=headers("Risk/Compliance Analyst"))
    assert response.status_code==403,response.json
    upload.assert_not_called()
    assert q("SELECT count(*) FROM ingestion_batches")==[(0,)]

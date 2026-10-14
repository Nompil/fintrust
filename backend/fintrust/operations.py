"""Bounded, authenticated technical operations; no compliance decision endpoints."""
from .paths import RESOURCE_ROOT
import hashlib,json,os,uuid
from datetime import datetime,timezone
from psycopg2.extras import RealDictCursor,Json
from . import workflow_api as api,release_workflow as worker,score
from .release_contract import VERSION

def release_info():
    from pathlib import Path
    path=RESOURCE_ROOT/"release-info.json"
    return json.loads(path.read_text()) if path.exists() else {"source_commit":os.getenv("FINTRUST_RELEASE_COMMIT","UNDECLARED")}

def alert_states(principal):
    from . import dynamo
    from boto3.dynamodb.conditions import Key
    table=dynamo.dynamodb.Table(os.environ["DYNAMODB_TABLE"])
    result=[]
    for account in principal.accounts[:20]:
        response=table.query(KeyConditionExpression=Key("account_id").eq(account)&Key("score_date").begins_with("ALERT#"),Limit=25)
        result.extend({k:v for k,v in item.items() if k in {"account_id","score_date","delivery_state","updated_at","risk_event_id"}} for item in response.get("Items",[]))
    return {"data":result,"limit_per_account":25,"account_limit":20,"meaning":"Bounded delivery-claim view; absence of a claim is pending until the alert worker evaluates it"}

def snapshot(principal):
    principal.require("operations")
    return {"contract_version":VERSION,"source_commit":release_info()["source_commit"],"alert_states":alert_states(principal),
        "migration_versions":api._query("SELECT version,source_sha256,catalog_sha256 FROM schema_migrations ORDER BY version"),
        "batches":api._query("SELECT batch_id,status,rows_received,accepted,quarantined,duplicate,failed_technical,pending,counts_consistent FROM batch_reconciliation ORDER BY batch_id LIMIT 100"),
        "projection_pending":api._query("SELECT count(*) AS count FROM projection_outbox WHERE state='PENDING'"),
        "correction_pending":api._query("SELECT count(*) AS count FROM correction_outbox WHERE state='PENDING'"),
        "operations_receipts":api._query("SELECT request_id,actor_subject,action,target,state,result,created_at,completed_at FROM operations_requests ORDER BY created_at DESC LIMIT 50"),
        "queue_metrics":queue_metrics(),"limits":{"batches":100,"receipts":50,"redrive":10},
        "alerts":"PENDING (no claim), SENDING/RETRYING (owned attempt), SENT, FAILED (definite rejection), UNKNOWN (operator reconciliation required)",
        "alert_retry":"Never automatically reclaim SENDING/RETRYING/UNKNOWN; transactions are committed independently"}

def queue_metrics():
    import boto3
    client=boto3.client("sqs",region_name="af-south-1")
    result={}
    for label,key in [("transactions","TRANSACTION_QUEUE_URL"),("dlq","TRANSACTION_DLQ_URL")]:
        if not os.getenv(key):result[label]={"status":"NOT_CONFIGURED"};continue
        try:result[label]=client.get_queue_attributes(QueueUrl=os.environ[key],AttributeNames=["ApproximateNumberOfMessages","ApproximateNumberOfMessagesNotVisible"])["Attributes"]
        except Exception:result[label]={"status":"UNAVAILABLE"}
    return result

def redrive(limit=1):
    import boto3
    source=os.environ["TRANSACTION_DLQ_URL"];destination=os.environ["TRANSACTION_QUEUE_URL"]
    client=boto3.client("sqs",region_name="af-south-1")
    attrs=client.get_queue_attributes(QueueUrl=destination,AttributeNames=["QueueArn","RedrivePolicy"])["Attributes"]
    origin=client.get_queue_attributes(QueueUrl=source,AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    approved=f"arn:aws:sqs:af-south-1:{os.environ['FINTRUST_ACCOUNT_ID']}:fintrust-transactions-dev.fifo"
    if attrs["QueueArn"]!=approved or origin!=approved.replace("transactions-dev.fifo","transactions-dlq-dev.fifo") or json.loads(attrs.get("RedrivePolicy","{}" )).get("deadLetterTargetArn")!=origin:
        raise ValueError("Redrive queue scope is not the approved FinTrust pair")
    messages=client.receive_message(QueueUrl=source,MaxNumberOfMessages=limit,VisibilityTimeout=30,WaitTimeSeconds=0,MessageSystemAttributeNames=["MessageGroupId"] ).get("Messages",[])
    for message in messages:
        envelope=json.loads(message["Body"]);worker._check(envelope)
        body=message["Body"]
        # New delivery token avoids the previous five-minute SQS dedup window;
        # durable SQL source identity remains the financial idempotency boundary.
        client.send_message(QueueUrl=destination,MessageBody=body,MessageGroupId=message.get("Attributes",{}).get("MessageGroupId",envelope["batch"]["batch_id"]),MessageDeduplicationId=str(uuid.uuid4()))
        client.delete_message(QueueUrl=source,ReceiptHandle=message["ReceiptHandle"])
    return {"redriven":len(messages),"limit":limit,"queue_scope":"approved transactions DLQ -> source FIFO only"}

def retry(body,principal):
    principal.require("retry")
    if not isinstance(body,dict) or set(body)!={"request_id","action","target","notes"}:raise ValueError("Exact retry fields required")
    if not isinstance(body["request_id"],str) or not isinstance(body["action"],str):raise ValueError("Text request UUID and action required")
    request=str(uuid.UUID(body["request_id"]));action=body["action"];target=body["target"]
    if action not in {"REBUILD_PROJECTION","RETRY_CORRECTION","REDRIVE"} or not isinstance(body["notes"],str) or not 1<=len(body["notes"].strip())<=2000:raise ValueError("Valid action and investigation notes required")
    if action=="REDRIVE":
        if os.getenv("FINTRUST_MODE")!="local":raise ValueError("Cloud redrive controller is separately gated")
        if type(target) is not int or not 1<=target<=10:raise ValueError("Redrive limit must be 1..10")
    else:
        if not isinstance(target,str):raise ValueError("Text target UUID required")
        target=str(uuid.UUID(target))
    digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    previous=api._query("SELECT actor_subject,request_digest,state,result FROM operations_requests WHERE request_id=%s",(request,))
    if previous:
        prior=previous[0]
        if prior["actor_subject"]!=principal.subject or prior["request_digest"]!=digest or prior["state"]!="COMPLETED":raise api.Conflict()
        return prior["result"]
    if action!="REDRIVE":
        table="projection_outbox" if action=="REBUILD_PROJECTION" else "correction_outbox";key="tx_id" if action=="REBUILD_PROJECTION" else "correction_id"
        if not api._query(f"SELECT 1 FROM {table} WHERE {key}=%s AND state='PENDING'",(target,)):raise api.NotFound()
    digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    conn=api.connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("INSERT INTO operations_requests(request_id,actor_subject,action,target,request_digest,state,result) VALUES(%s,%s,%s,%s,%s,'RUNNING',%s) ON CONFLICT DO NOTHING",(request,principal.subject,action,str(target),digest,Json({"notes":body["notes"]})))
                inserted=cur.rowcount
                cur.execute("SELECT * FROM operations_requests WHERE request_id=%s",(request,));prior=cur.fetchone()
                if prior["actor_subject"]!=principal.subject or prior["request_digest"]!=digest:raise api.Conflict()
                if not inserted:
                    if prior["state"]=="COMPLETED":return prior["result"]
                    raise api.Conflict("Operation in progress or failed; investigate before a new receipt")
        try:
            if action in {"REBUILD_PROJECTION","RETRY_CORRECTION"}:
                # HTTP role can request derived-work retry, never execute financial DDL/DML.
                table="projection_outbox" if action=="REBUILD_PROJECTION" else "correction_outbox"
                key="tx_id" if action=="REBUILD_PROJECTION" else "correction_id"
                with conn:
                    with conn.cursor() as cur:cur.execute(f"UPDATE {table} SET state='PENDING' WHERE {key}=%s",(target,))
                result={"work":"QUEUED","target":target,"note":"Worker must complete and reconcile separately"}
            else:result=redrive(target)
        except Exception as error:
            with conn:
                with conn.cursor() as cur:cur.execute("UPDATE operations_requests SET state='FAILED',completed_at=NOW(),result=%s WHERE request_id=%s",(Json({"error_type":type(error).__name__,"notes":body["notes"]}),request))
            raise
        result={**result,"notes":body["notes"]}
        with conn:
            with conn.cursor() as cur:cur.execute("UPDATE operations_requests SET state='COMPLETED',completed_at=NOW(),result=%s WHERE request_id=%s",(Json(result),request))
        return result
    finally:conn.close()

def upload_csv(filename,payload,principal):
    principal.require("upload")
    # The synchronous local adapter is explicitly gated. Cloud uses versioned S3
    # intake -> FIFO -> private scoring worker, never an HTTP SQL write shortcut.
    if os.getenv("FINTRUST_MODE")!="local":raise ValueError("Synchronous upload is local-only; cloud intake is separately gated")
    from .release_ingest import envelopes,parse_file
    # Known accounts outside the caller's scope are denied before storage or
    # processing. Unknown/malformed accounts remain business-invalid quarantine.
    identifiers=set()
    for _,row,_ in parse_file(payload):
        try:identifiers.add(str(uuid.UUID(row.get("account_id","").strip())))
        except (ValueError,AttributeError):continue
    if identifiers:
        known=api._query("SELECT account_id::text FROM accounts WHERE account_id = ANY(%s::uuid[])",(list(identifiers),))
        for account in known:principal.account(account["account_id"])
    from .batches import metadata,BatchAudit
    bucket=os.environ["INPUT_BUCKET"];digest=hashlib.sha256(payload).hexdigest();key="raw/uploads/"+digest+".csv"
    response=score.s3.put_object(Bucket=bucket,Key=key,Body=payload,ContentType="text/csv")
    if not response.get("VersionId"):raise RuntimeError("Input bucket must be versioned")
    batch=metadata(bucket,payload);audit=BatchAudit(score.s3,os.environ["QUARANTINE_BUCKET"],bucket,key,batch,response["VersionId"]);audit.first_receipt()
    # Existing batches without trusted ownership remain unowned. A replay must
    # never adopt a historical or another Analyst's source file.
    from .upload_ownership import claim
    if not api._query("SELECT 1 FROM ingestion_batches WHERE batch_id=%s",(batch["batch_id"],)):
        claim(batch["batch_id"],principal,{"bucket":bucket,"key":key,"version":response["VersionId"],"sha256":digest,
            "filename":filename,"actor_role":principal.role,"channel":"MANUAL_UPLOAD"})
    items=envelopes(bucket,key,payload,version=response["VersionId"],batch=batch)
    exists=api._query("SELECT 1 FROM ingestion_batches WHERE batch_id=%s AND publication_complete",(batch["batch_id"],))
    if exists:
        control={**items[-1],"kind":"DUPLICATE_FILE"};worker.process_envelope(control)
    else:
        for item in items:worker.process_envelope(item)
    state=api._query("SELECT * FROM batch_reconciliation WHERE batch_id=%s",(batch["batch_id"],))[0]
    from .upload_notifications import notification
    status="DUPLICATE_FILE" if exists else state["status"]
    from .frontend_workflows import record_upload
    record_upload(principal,filename,"UPLOAD_REPLAY" if exists else "UPLOAD_ACCEPTED",status,batch_id=batch["batch_id"])
    from .case_provenance import source
    provenance=source(batch['batch_id'],principal)
    return {"filename":filename,"batch_id":batch["batch_id"],"upload_status":status,"reconciliation":state,"notification":notification(status,state),"execution":"local synchronous real worker; AWS services mocked",
        'source_provenance':provenance,'submitted_by':provenance.get('submitted_by'),'submitted_at':provenance.get('submitted_at'),
        'original_filename':provenance.get('original_filename'),'submission_channel':provenance.get('submission_channel'),
        'risk_event_counts':api.run_risk_counts(batch['batch_id'],principal)}

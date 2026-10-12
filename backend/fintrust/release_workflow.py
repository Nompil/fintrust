"""Release 1 authoritative row accounting and replayable worker effects.
No distributed transaction: SQL business commit precedes DynamoDB projection.
Business rejection is a successful terminal outcome; infrastructure errors retry.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from psycopg2.extras import Json
from .db import get_connection
from . import score, jobs, dynamo
from .release_contract import validation_errors, VERSION

TERMINAL={"ACCEPTED","QUARANTINED","DUPLICATE"}

def _check(item):
    if not isinstance(item,dict) or item.get("schema_version")!=3 or item.get("kind") not in {"ROW","PUBLICATION","FILE_FAILURE","DUPLICATE_FILE"}:
        raise ValueError("Invalid Release 1 envelope")
    b=item["batch"]; uuid.UUID(b["batch_id"]); uuid.UUID(item["attempt_id"])
    if set(b)!={"batch_id","file_sha256","ingested_at"} or len(b["file_sha256"])!=64 or any(c not in "0123456789abcdef" for c in b["file_sha256"]):
        raise ValueError("Invalid batch identity")
    clock=datetime.fromisoformat(b["ingested_at"])
    if clock.tzinfo is None: raise ValueError("Receipt timestamp must be timezone aware")
    source=item["source"]
    if not isinstance(source.get("bucket"),str) or not source["bucket"] or not isinstance(source.get("key"),str) or not source["key"]:
        raise ValueError("Invalid source")
    total=item.get("rows_received")
    if total is not None and (type(total) is not int or not (0 if item["kind"]=="FILE_FAILURE" else 1)<=total<=5000): raise ValueError("Invalid parsed total")
    if item["kind"]=="ROW":
        if total is None or type(source.get("row")) is not int or not 2<=source["row"]<=total+1:
            raise ValueError("Invalid row occurrence")
        if not isinstance(item.get("row"),dict): raise ValueError("Candidate must be an object")
    return clock

def _with_connection(fn):
    conn=get_connection()
    try:
        with conn:
            with conn.cursor() as cur: return fn(cur)
    finally: conn.close()

def register(item):
    _check(item);b=item["batch"];s=item["source"]
    def write(cur):
        cur.execute("""INSERT INTO ingestion_batches(batch_id,source_system,source_bucket,file_sha256,received_at,rows_received)
            VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (b["batch_id"],item.get("source_system","release1-feed"),s["bucket"],b["file_sha256"],b["ingested_at"],item["rows_received"]))
        cur.execute("SELECT file_sha256,rows_received,received_at,source_bucket FROM ingestion_batches WHERE batch_id=%s FOR UPDATE",(b["batch_id"],))
        saved=cur.fetchone()
        if saved!=(b["file_sha256"],item["rows_received"],datetime.fromisoformat(b["ingested_at"]),s["bucket"]):
            raise ValueError("Batch metadata conflicts with immutable receipt")
        cur.execute("""INSERT INTO ingestion_attempts(attempt_id,batch_id,source_bucket,source_file,source_version,source_etag,received_at,status)
            VALUES(%s,%s,%s,%s,%s,%s,%s,'PROCESSING') ON CONFLICT(attempt_id) DO NOTHING""",
            (item["attempt_id"],b["batch_id"],s["bucket"],s["key"],s.get("version"),s.get("etag"),b["ingested_at"]))
        cur.execute("SELECT batch_id,source_bucket,source_file,source_version,source_etag FROM ingestion_attempts WHERE attempt_id=%s",(item["attempt_id"],))
        if tuple(str(x) if i==0 else x for i,x in enumerate(cur.fetchone()))!=(b["batch_id"],s["bucket"],s["key"],s.get("version"),s.get("etag")):
            raise ValueError("Attempt identity conflict")
        if item["rows_received"] is not None:
            cur.execute("""INSERT INTO ingestion_records(batch_id,source_row,source_attempt_id,disposition)
                SELECT %s,n,%s,'RECEIVED' FROM generate_series(2,%s) n ON CONFLICT DO NOTHING""",
                (b["batch_id"],item["attempt_id"],item["rows_received"]+1))
        if item["kind"]=="FILE_FAILURE":
            cur.execute("UPDATE ingestion_batches SET file_failure_code=%s WHERE batch_id=%s",(item["error_code"],b["batch_id"]))
            cur.execute("UPDATE ingestion_attempts SET status='FAILED',error_code=%s WHERE attempt_id=%s",(item["error_code"],item["attempt_id"]))
        elif item["kind"]=="DUPLICATE_FILE":
            cur.execute("UPDATE ingestion_attempts SET status='DUPLICATE_FILE' WHERE attempt_id=%s",(item["attempt_id"],))
        elif item["kind"]=="PUBLICATION":
            cur.execute("UPDATE ingestion_batches SET publication_complete=TRUE WHERE batch_id=%s",(b["batch_id"],))
            cur.execute("UPDATE ingestion_attempts SET status='QUEUED' WHERE attempt_id=%s",(item["attempt_id"],))
        else:
            digest=hashlib.sha256(json.dumps([item["row"],item.get("parse_error")],sort_keys=True).encode()).hexdigest()
            cur.execute("SELECT candidate_digest FROM ingestion_records WHERE batch_id=%s AND source_row=%s",(b["batch_id"],s["row"]))
            original=cur.fetchone()[0]
            if original is not None and original!=digest: raise ValueError("Row occurrence content changed")
            if original is None:
                cur.execute("UPDATE ingestion_records SET candidate_digest=%s WHERE batch_id=%s AND source_row=%s",(digest,b["batch_id"],s["row"]))
    _with_connection(write)

def outcome(cur,item,disposition,canonical=None,reason=None):
    b=item["batch"];n=item["source"]["row"]
    cur.execute("SELECT batch_id FROM ingestion_batches WHERE batch_id=%s FOR UPDATE",(b["batch_id"],))
    cur.execute("SELECT disposition,canonical_tx_id::text FROM ingestion_records WHERE batch_id=%s AND source_row=%s FOR UPDATE",(b["batch_id"],n))
    previous=cur.fetchone()
    if previous[0] in TERMINAL:
        if previous!=(disposition,canonical): raise ValueError("Terminal occurrence conflicts with retry")
        return
    cur.execute("""UPDATE ingestion_records SET disposition=%s,canonical_tx_id=%s,reason_code=%s,updated_at=NOW()
        WHERE batch_id=%s AND source_row=%s""",(disposition,canonical,reason,b["batch_id"],n))

def quarantine(item,errors):
    source=item["source"];b=item["batch"]
    from .quarantine import rejection
    identity=str(uuid.uuid5(uuid.UUID(b["batch_id"]),str(source["row"])))
    key="quarantine/release1/"+identity+".json"
    value=rejection(errors[0]["reason_code"],errors[0]["reason_detail"],item["row"],bucket=source["bucket"],key=source["key"],
                    row_number=source["row"],batch=b,version=source.get("version"),etag=source.get("etag"))
    value["validation_errors"]=errors
    # No terminal SQL success is acknowledged before immutable, versioned evidence exists.
    response=score.s3.put_object(Bucket=os.environ["QUARANTINE_BUCKET"],Key=key,Body=json.dumps(value).encode(),ContentType="application/json")
    version=response.get("VersionId")
    if not version: raise RuntimeError("Quarantine bucket must be versioned")
    try: account=str(uuid.UUID(item["row"].get("account_id","")))
    except (ValueError,TypeError,AttributeError): account=None
    def finish(cur):
        outcome(cur,item,"QUARANTINED",reason=errors[0]["reason_code"])
        cur.execute("""INSERT INTO quarantine_cases(quarantine_id,batch_id,source_row,reason_code,reason_detail,
            validation_errors,candidate_account_id,safe_payload_key,safe_payload_version,source_reference,quarantined_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT(batch_id,source_row) DO NOTHING""",
            (identity,b["batch_id"],source["row"],errors[0]["reason_code"],errors[0]["reason_detail"],Json(errors),account,key,version,
             item["row"].get("source_transaction_id") or item["row"].get("source_reference")))
    _with_connection(finish)
    return {"status":"QUARANTINED","quarantine_id":identity,"validation_errors":errors}

def process_envelope(item):
    clock=_check(item); register(item)
    if item["kind"]!="ROW": return {"status":"FAILED" if item["kind"]=="FILE_FAILURE" else "DUPLICATE_FILE" if item["kind"]=="DUPLICATE_FILE" else "QUEUED","batch_id":item["batch"]["batch_id"]}
    def saved(cur):
        cur.execute("SELECT disposition FROM ingestion_records WHERE batch_id=%s AND source_row=%s",(item["batch"]["batch_id"],item["source"]["row"]))
        return cur.fetchone()[0]
    if _with_connection(saved)=="QUARANTINED": return {"status":"QUARANTINED"}
    known=True
    try: account=str(uuid.UUID(item["row"].get("account_id","")))
    except (ValueError,TypeError,AttributeError): pass
    else:
        def exists(cur):
            cur.execute("SELECT 1 FROM accounts WHERE account_id=%s",(account,));return cur.fetchone() is not None
        known=_with_connection(exists)
    errors=validation_errors(item["row"],clock,known_account=known)
    if item.get("parse_error"): errors.insert(0,{"reason_code":item["parse_error"],"reason_detail":"CSV row shape or size is invalid"})
    if errors: return quarantine(item,errors)
    s=item["source"];b=item["batch"]
    job=jobs.make_job(item["row"],s["bucket"],s["key"],"batch:"+b["batch_id"],s["row"],s.get("version"),s.get("etag"),batch=b)
    state={}
    def commit(cur,result,existing):
        # A repeated occurrence is ACCEPTED again; a different occurrence is DUPLICATE.
        canonical=result["transaction_id"]
        first=result.get("batch",{}); original=result.get("source",{})
        duplicate=existing and (first is None or first.get("batch_id")!=b["batch_id"] or original.get("row")!=s["row"])
        state["status"]="DUPLICATE" if duplicate else "ACCEPTED"
        outcome(cur,item,state["status"],canonical,"DUPLICATE_TRANSACTION" if duplicate else None)
        cur.execute("INSERT INTO projection_outbox(tx_id) VALUES(%s) ON CONFLICT DO NOTHING",(canonical,))
        if result["risk_level"] in {"Medium","High"}:
            cur.execute("INSERT INTO risk_reviews(risk_event_id,change_actor) VALUES(%s,'scoring-worker') ON CONFLICT DO NOTHING",(result["risk_event_id"],))
    try: result=score.persist_score(job,commit_hook=commit)
    except (score.UnknownAccount,score.IdentityConflict) as error:
        code="INACTIVE_ACCOUNT" if isinstance(error,score.InactiveAccount) else "UNKNOWN_ACCOUNT" if isinstance(error,score.UnknownAccount) else "DUPLICATE_IDENTITY_CONFLICT"
        return quarantine(item,[{"reason_code":code,"reason_detail":"Account is not eligible" if code in {"UNKNOWN_ACCOUNT","INACTIVE_ACCOUNT"} else "Trusted transaction identity conflicts with accepted financial data"}])
    # Infrastructure failure here leaves committed SQL outcome and retry-safe projection backlog.
    dynamo.publish_score(os.environ["DYNAMODB_TABLE"],{**result,"score_date":"TX#"+result["transaction_id"],"risk_score":result["score"]})
    def projected(cur):
        cur.execute("UPDATE projection_outbox SET state='COMPLETED',completed_at=NOW() WHERE tx_id=%s",(result["transaction_id"],))
    _with_connection(projected)
    return {**result,"status":state["status"],"contract_version":VERSION}

def drain_corrections(limit=10):
    if type(limit) is not int or not 1<=limit<=100: raise ValueError("Bounded drain required")
    def pending(cur):
        cur.execute("SELECT correction_id::text,envelope FROM correction_outbox WHERE state='PENDING' ORDER BY correction_id LIMIT %s",(limit,))
        return cur.fetchall()
    completed=0
    for identifier,item in _with_connection(pending):
        try:
            process_envelope(item)
            def finish(cur):
                cur.execute("UPDATE correction_outbox SET state='COMPLETED',attempts=attempts+1,completed_at=NOW(),last_error_type=NULL WHERE correction_id=%s",(identifier,))
            _with_connection(finish);completed+=1
        except Exception as error:
            def failed(cur):
                cur.execute("UPDATE correction_outbox SET attempts=attempts+1,last_error_type=%s WHERE correction_id=%s",(type(error).__name__,identifier))
            _with_connection(failed)
            raise
    return {"completed":completed}

def rebuild_projection(transaction_id):
    identifier=str(uuid.UUID(transaction_id))
    def read(cur):
        cur.execute("SELECT result FROM processed_transactions WHERE tx_id=%s",(identifier,));row=cur.fetchone()
        if not row: raise ValueError("No authoritative frozen result; manual recovery required")
        return row[0]
    result=_with_connection(read)
    dynamo.publish_score(os.environ["DYNAMODB_TABLE"],{**result,"score_date":"TX#"+identifier,"risk_score":result["score"]})
    def projected(cur):
        cur.execute("UPDATE projection_outbox SET state='COMPLETED',completed_at=NOW() WHERE tx_id=%s",(identifier,))
    _with_connection(projected)
    return identifier


def drain_projections(limit=10):
    if type(limit) is not int or not 1<=limit<=100:raise ValueError("Bounded drain required")
    items=_with_connection(lambda cur:(cur.execute("SELECT tx_id::text FROM projection_outbox WHERE state='PENDING' ORDER BY tx_id LIMIT %s",(limit,)),cur.fetchall())[1])
    completed=0
    for (identifier,) in items:
        rebuild_projection(identifier);completed+=1
    return {"completed":completed,"limit":limit}

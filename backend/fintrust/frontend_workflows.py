"""Release 1 presentation reads and local intake receipts. No ledger mutation.
Local upload receipts use the existing versioned S3 audit bucket; cloud intake
remains separately gated. Never store CSV bodies, bearer tokens or exceptions.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from . import workflow_api as api, score
PREFIX = "quarantine/ui-events/"

def record_upload(principal, filename, action, result, *, reason_code=None, batch_id=None):
    if os.getenv("FINTRUST_MODE") != "local":
        raise ValueError("Local intake receipt required")
    event = {"event_id":str(uuid.uuid4()), "filename":secure_filename(filename or "")[:200],
        "actor":principal.subject, "actor_role":principal.role, "accounts":list(principal.accounts),
        "attempted_at":datetime.now(timezone.utc).isoformat(), "action":action,
        "result":result, "reason_code":reason_code, "batch_id":batch_id,
        "rows_processed":0 if action=="UPLOAD_REJECTED" else None}
    score.s3.put_object(Bucket=os.environ["QUARANTINE_BUCKET"], Key=PREFIX+event["event_id"]+".json",
        Body=json.dumps(event).encode(), ContentType="application/json", IfNoneMatch="*")
    return {k:v for k,v in event.items() if k!="accounts"}

def upload_history(principal):
    principal.require("read")
    if principal.role == "Maintainer": raise PermissionError("Financial intake history")
    if os.getenv("FINTRUST_MODE") != "local": raise ValueError("Cloud intake history is separately gated")
    rows=[]; cursor=None; scanned=0
    while True:
        args={"Bucket":os.environ["QUARANTINE_BUCKET"],"Prefix":PREFIX,"MaxKeys":1000}
        if cursor: args["ContinuationToken"]=cursor
        listing=score.s3.list_objects_v2(**args)
        for entry in listing.get("Contents",[]):
            body=score.s3.get_object(Bucket=args["Bucket"],Key=entry["Key"])["Body"]
            try: item=json.loads(body.read())
            finally: body.close()
            if set(item["accounts"]) <= set(principal.accounts):
                rows.append({k:v for k,v in item.items() if k!="accounts"})
        scanned+=len(listing.get("Contents",[]))
        if not listing.get("IsTruncated"): break
        if scanned>=5000: raise ValueError("Receipt history exceeds bounded local view")
        cursor=listing["NextContinuationToken"]
    return sorted(rows,key=lambda x:x["attempted_at"],reverse=True)

def batch_detail(identifier, principal, args):
    identifier=str(uuid.UUID(identifier));limit,offset=api.page_args(args,{"disposition"})
    # Reuse exactly the list authority; never grant a guessed batch UUID access.
    rows=api.list_page("batches",principal,{"limit":1,"batch_id":identifier})
    batch=rows["data"][0] if rows["data"] else None
    if not batch: raise api.NotFound()
    where="i.batch_id=%s";params=[identifier]
    disposition=args.get("disposition")
    if disposition:
        if disposition not in {"ACCEPTED","QUARANTINED","DUPLICATE","FAILED_TECHNICAL","PENDING"}: raise ValueError("Invalid disposition")
        if disposition=='PENDING':where+=" AND i.disposition IN ('RECEIVED','QUEUED')"
        else:where+=" AND i.disposition=%s";params.append(disposition)
    rows=api._query("""SELECT i.*,t.source_transaction_id,t.source_system,t.tx_date,
        q.source_reference,q.quarantine_id,
        (SELECT min(original.updated_at) FROM ingestion_records original
          WHERE original.canonical_tx_id=i.canonical_tx_id AND original.disposition='ACCEPTED') AS first_processed_at,
        CASE WHEN i.disposition='DUPLICATE' THEN CASE WHEN EXISTS
          (SELECT 1 FROM ingestion_records original WHERE original.batch_id=i.batch_id
           AND original.canonical_tx_id=i.canonical_tx_id AND original.disposition='ACCEPTED')
          THEN 'SAME_FILE_DUPLICATE' ELSE 'CROSS_FILE_DUPLICATE' END
          ELSE i.reason_code END AS classification
        FROM ingestion_records i LEFT JOIN transactions t ON t.tx_id=i.canonical_tx_id
        LEFT JOIN quarantine_cases q ON q.batch_id=i.batch_id AND q.source_row=i.source_row
        WHERE """+where+" ORDER BY i.source_row LIMIT %s OFFSET %s",tuple(params+[limit+1,offset]))
    attempts=api._query("SELECT attempt_id,source_file,received_at,status,error_code FROM ingestion_attempts WHERE batch_id=%s ORDER BY received_at",(identifier,))
    events=[r for r in upload_history(principal) if r.get("batch_id")==identifier]
    batch.update({"filename":events[-1]["filename"] if events else attempts[0]["source_file"] if attempts else None,
        "actor":events[-1]["actor"] if events else None,
        "accounted_for":sum(batch[k] for k in ("accepted","quarantined","duplicate","failed_technical")),
        "display_status":batch["status"] if batch["counts_consistent"] else "AWAITING_RECONCILIATION" if batch["rows_received"] is None else "RECONCILIATION_FAILED"})
    stamps=api._query('SELECT min(updated_at) AS first_row_observed_at,max(updated_at) AS last_row_observed_at FROM ingestion_records WHERE batch_id=%s',(identifier,))[0]
    batch['started_at']=batch['received_at']
    batch['completed_at']=stamps['last_row_observed_at'] if batch['counts_consistent'] and batch['pending']==0 and batch['status'] in {'COMPLETED','PARTIAL','FAILED'} else None
    batch['completed_at_note']='Last recorded row outcome; no separate processing completion event is recorded.'
    total=api._query('SELECT count(*) AS total_count FROM ingestion_records i WHERE '+where,tuple(params))[0]['total_count']
    return {"batch":batch,"rows":rows[:limit],"attempts":attempts,
        "meta":{"count":len(rows[:limit]),"total_count":total,"has_more":len(rows)>limit,"offset":offset,"limit":limit,"filters":{"disposition":disposition} if disposition else {}}}

def overview(principal):
    from .query import get_overview
    data=get_overview(principal.accounts)
    scope=list(principal.accounts)
    from .analyst_workflow import assessed_sql
    data["risk_distribution"]=api._query("SELECT p.result->>'risk_level' AS risk_level,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) WHERE t.account_id=ANY(%s::uuid[]) AND "+assessed_sql()+" GROUP BY 1",(scope,))
    data["new_ledger_entries"]=sum(r["count"] for r in data["risk_distribution"])
    data["open_reviews"]=api._query("SELECT count(*) AS count FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE t.account_id=ANY(%s::uuid[]) AND w.review_status IN ('OPEN','UNDER_REVIEW','ESCALATED')",(scope,))[0]["count"]
    data.update(api.review_workload(principal))
    from .analyst_workflow import policy
    data['sla_policy']=policy()
    q=api.list_page("quarantine",principal,{"limit":100})
    # Counts share list scoping; exact counters are marked bounded when paginated.
    batches=api.list_page("batches",principal,{"limit":100})
    data.update({"quarantined_rows":q['meta']['total_count'],"quarantine_requiring_action":api.list_page('quarantine',principal,{'limit':1,'status':'OPEN'})['meta']['total_count'],"duplicate_occurrences":sum(b["duplicate"] for b in batches["data"]),
        "technical_failures":sum(b["failed_technical"] for b in batches["data"]),
        "partial_failed_batches":sum(b["status"] in ('PARTIAL','FAILED') or (b["rows_received"] is not None and not b["counts_consistent"]) for b in batches["data"]),
        "rejected_uploads":sum(e["action"]=='UPLOAD_REJECTED' for e in upload_history(principal)),
        "bounded_counts":q["meta"]["has_more"] or batches["meta"]["has_more"],
        "recent_batches":batches["data"][:5],
        "recent_transactions":api.list_page("transactions",principal,{"limit":8})["data"],
        "attention":api.list_page("reviews",principal,{"limit":8,"queue":"open"})["data"]})
    return data

def audit_events(principal, args):
    principal.require("audit")
    limit,offset=api.page_args(args)
    scope=list(principal.accounts)
    from .upload_ownership import owned_batches
    owned=owned_batches(principal)
    events=[{"timestamp":e["attempted_at"],"actor":e["actor"],"action":e["action"],"resource":e.get("target") or e.get("batch_id") or e["event_id"],"result":e["result"],"actor_role":e.get("actor_role","Not captured"),"details":e.get("notes") or e.get("reason_code") or e["filename"]} for e in upload_history(principal)]
    events+=api._query("SELECT h.changed_at AS timestamp,h.actor_subject AS actor,CASE WHEN h.before_status='OPEN' AND h.after_status='UNDER_REVIEW' THEN 'REVIEW_CLAIMED' WHEN h.before_status=h.after_status AND h.after_status='UNDER_REVIEW' AND h.reviewer_subject=(SELECT previous.reviewer_subject FROM risk_review_history previous WHERE previous.risk_event_id=h.risk_event_id AND previous.version=h.version-1) THEN 'REVIEW_NOTE_ADDED' WHEN h.before_status=h.after_status AND h.after_status IN ('UNDER_REVIEW','ESCALATED') THEN 'REVIEW_REASSIGNED' WHEN h.before_status='UNDER_REVIEW' AND h.after_status='OPEN' THEN 'REVIEW_UNASSIGNED' ELSE 'REVIEW_'||h.after_status END AS action,h.risk_event_id::text AS resource,h.after_status AS result,h.notes AS details FROM risk_review_history h JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE t.account_id=ANY(%s::uuid[]) ORDER BY h.changed_at DESC LIMIT 1000",(scope,))
    events+=api._query("SELECT i.updated_at AS timestamp,'system' AS actor,'ROW_'||i.disposition AS action,i.batch_id::text||':'||i.source_row::text AS resource,i.disposition AS result,i.reason_code AS details FROM ingestion_records i LEFT JOIN transactions t ON t.tx_id=i.canonical_tx_id LEFT JOIN quarantine_cases q ON q.batch_id=i.batch_id AND q.source_row=i.source_row WHERE COALESCE(t.account_id,q.candidate_account_id)=ANY(%s::uuid[]) OR ((%s OR q.batch_id=ANY(%s::uuid[])) AND i.disposition='QUARANTINED' AND NOT EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id)) ORDER BY i.updated_at DESC LIMIT 1000",(scope,principal.role=='Admin',owned))
    events+=api._query("SELECT c.submitted_at AS timestamp,c.submitted_by AS actor,'QUARANTINE_'||c.action AS action,c.quarantine_id::text AS resource,c.action AS result,c.correction_notes AS details FROM quarantine_corrections c JOIN quarantine_cases q USING(quarantine_id) WHERE q.candidate_account_id=ANY(%s::uuid[]) OR ((%s OR q.batch_id=ANY(%s::uuid[])) AND NOT EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id)) ORDER BY c.submitted_at DESC LIMIT 1000",(scope,principal.role=='Admin',owned))
    if principal.role=='Admin':
        events+=api._query("SELECT COALESCE(completed_at,created_at) AS timestamp,actor_subject AS actor,action,request_id::text AS resource,state AS result,result->>'notes' AS details FROM operations_requests ORDER BY created_at DESC LIMIT 1000")
    for event in events:
        automated=event.get('actor')=='system' and event.get('action','').startswith('ROW_') or event.get('actor')=='scoring-worker' and event.get('action')=='REVIEW_OPEN'
        event.setdefault('actor_type','SYSTEM' if automated else 'HUMAN')
        event.setdefault('actor_role','SYSTEM' if automated else 'Not recorded')
        if event['actor_role']=='Not recorded':event['actor_role_note']='Role-at-action is not stored in this historical SQL record; current user roles are not substituted.'
    events.sort(key=lambda x:datetime.fromisoformat(x['timestamp'].replace('Z','+00:00')) if isinstance(x['timestamp'],str) else x['timestamp'],reverse=True)
    return {"data":events[offset:offset+limit],"meta":{"count":len(events[offset:offset+limit]),"has_more":len(events)>offset+limit,"bounded_per_source":1000}}

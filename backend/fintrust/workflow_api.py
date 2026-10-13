"""Bounded, scoped analyst workflow service. No financial UPDATE endpoints."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from psycopg2.extras import RealDictCursor, Json
from . import release_workflow as workflow
from .release_contract import review_transition
from .quarantine import FIELDS

class Conflict(ValueError): pass
class NotFound(LookupError): pass

def connection(): return workflow.get_connection()

def _query(statement,params=()):
    conn=connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(statement,params);return [dict(x) for x in cur.fetchall()]
    finally: conn.close()

def page_args(args,allowed=()):
    if hasattr(args,"getlist") and any(len(args.getlist(k))!=1 for k in args): raise ValueError("Duplicate filter")
    if set(args)-{"limit","offset",*allowed}: raise ValueError("Unsupported filter")
    try: limit=int(args.get("limit",25));offset=int(args.get("offset",0))
    except ValueError: raise ValueError("Pagination must be integer") from None
    if not 1<=limit<=100 or not 0<=offset<=100000: raise ValueError("Pagination outside allowed range")
    return limit,offset

def list_page(kind,principal,args):
    limit,offset=page_args(args,{"status","account_id",*( {"tx_id","source_id","country","risk_level","batch_id","from","to","min_amount","max_amount"} if kind=="transactions" else {"batch_id"} if kind=="batches" else {"queue","scenario","risk_level","assignee","sort"} if kind=="reviews" else {"scenario","risk_level","assignee","sort"} if kind=="risk-events" else set())})
    scope=list(principal.accounts)
    if args.get("account_id"): scope=[principal.account(args["account_id"])]
    selects={
      "transactions":("SELECT t.*,p.result AS risk FROM transactions t LEFT JOIN processed_transactions p USING(tx_id)","t.account_id=ANY(%s::uuid[])","t.tx_date DESC,t.tx_id DESC"),
      "risk-events":("SELECT r.*,t.account_id,t.amount,t.currency,t.tx_date,w.review_status,w.reviewer_subject,w.version,p.result AS risk FROM risk_events r JOIN transactions t USING(tx_id) LEFT JOIN risk_reviews w USING(risk_event_id) LEFT JOIN processed_transactions p USING(tx_id)","t.account_id=ANY(%s::uuid[])","r.risk_event_id DESC"),
      "reviews":("SELECT w.*,r.tx_id,r.risk_score,t.account_id,t.amount,t.currency,t.tx_date,p.result AS risk FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) LEFT JOIN processed_transactions p USING(tx_id)","t.account_id=ANY(%s::uuid[])","w.created_at,w.risk_event_id"),
      "quarantine":("SELECT q.* FROM quarantine_workflow q","(q.candidate_account_id=ANY(%s::uuid[]) OR (%s AND NOT EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id)))","q.quarantined_at,q.quarantine_id"),
      "batches":("SELECT b.*,r.* FROM ingestion_batches b JOIN batch_reconciliation r USING(batch_id)","(NOT EXISTS(SELECT 1 FROM ingestion_records i LEFT JOIN transactions t ON t.tx_id=i.canonical_tx_id LEFT JOIN quarantine_cases q ON q.batch_id=i.batch_id AND q.source_row=i.source_row WHERE i.batch_id=b.batch_id AND (COALESCE(t.account_id,q.candidate_account_id) IS NULL OR NOT (COALESCE(t.account_id,q.candidate_account_id)=ANY(%s::uuid[])))) AND EXISTS(SELECT 1 FROM ingestion_records i WHERE i.batch_id=b.batch_id) OR %s)","b.received_at DESC,b.batch_id"),
      "audit":("SELECT h.*,t.account_id FROM risk_review_history h JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id)","t.account_id=ANY(%s::uuid[])","h.changed_at DESC,h.risk_event_id,h.version"),
    }
    if kind not in selects: raise NotFound()
    if kind=="audit": principal.require("audit")
    select,where,order=selects[kind];params=[scope]
    if kind in {"quarantine","batches"}:
        from .upload_ownership import owned_batches
        owned=owned_batches(principal)
        if kind=='quarantine':
            where="(q.candidate_account_id=ANY(%s::uuid[]) OR ((%s OR q.batch_id=ANY(%s::uuid[])) AND NOT EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id)))"
            params.extend([principal.role=='Admin',owned])
        else:
            # A whole batch is visible only if every row is assigned, or is
            # genuinely unknown and belongs to the original authenticated uploader.
            where="(NOT EXISTS(SELECT 1 FROM ingestion_records i LEFT JOIN transactions t ON t.tx_id=i.canonical_tx_id LEFT JOIN quarantine_cases q ON q.batch_id=i.batch_id AND q.source_row=i.source_row WHERE i.batch_id=b.batch_id AND NOT (COALESCE(COALESCE(t.account_id,q.candidate_account_id)=ANY(%s::uuid[]),false) OR (b.batch_id=ANY(%s::uuid[]) AND i.disposition='QUARANTINED' AND NOT EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id)))) AND EXISTS(SELECT 1 FROM ingestion_records i WHERE i.batch_id=b.batch_id) OR %s)"
            params.extend([owned,principal.role=='Admin'])
    if kind=="transactions":
        from decimal import Decimal, InvalidOperation
        for key,column,operator in (("tx_id","t.tx_id","="),("source_id","t.source_transaction_id","="),("country","t.country","="),("risk_level","p.result->>'risk_level'","="),("from","t.tx_date",">="),("to","t.tx_date","<="),("min_amount","t.amount",">="),("max_amount","t.amount","<=")):
            value=args.get(key)
            if not value: continue
            if key=="tx_id": value=str(uuid.UUID(value))
            elif key in {"from","to"}:
                value=datetime.fromisoformat(value.replace("Z","+00:00"))
                if value.tzinfo is None: raise ValueError("Timezone required")
            elif key in {"min_amount","max_amount"}:
                try: value=Decimal(value)
                except InvalidOperation: raise ValueError("Invalid amount") from None
                if not value.is_finite(): raise ValueError("Invalid amount")
            elif len(value)>200: raise ValueError("Filter too long")
            where+=" AND "+column+operator+"%s";params.append(value)
        if args.get("batch_id"):
            where+=" AND EXISTS(SELECT 1 FROM ingestion_records i WHERE i.canonical_tx_id=t.tx_id AND i.batch_id=%s)";params.append(str(uuid.UUID(args["batch_id"])))
    if kind=="batches" and args.get("batch_id"):
        where+=" AND b.batch_id=%s";params.append(str(uuid.UUID(args["batch_id"])))
    if kind=="reviews":
        queue=args.get("queue")
        if queue and queue not in {"mine","unassigned","open","high","over_sla"}:raise ValueError("Invalid review queue")
        if queue:
            where+=" AND w.review_status IN ('OPEN','UNDER_REVIEW','ESCALATED')"
            if queue=="mine":where+=" AND w.reviewer_subject=%s";params.append(principal.subject)
            elif queue=="unassigned":where+=" AND w.reviewer_subject IS NULL"
            elif queue=="high":where+=" AND p.result->>'risk_level'='High'"
            elif queue=="over_sla":
                from .review_assignment import sla_seconds
                seconds=sla_seconds()
                if seconds is None:return {"data":[],"meta":{"count":0,"limit":limit,"offset":offset,"has_more":False,"sla_configured":False}}
                where+=" AND w.created_at<=NOW()-(%s * INTERVAL '1 second')";params.append(seconds)
    if kind in {"reviews","risk-events"}:
        level=args.get("risk_level")
        if level:
            if level not in {"Low","Medium","High"}:raise ValueError("Invalid risk level")
            where+=" AND p.result->>'risk_level'=%s";params.append(level)
        scenario=args.get("scenario")
        if scenario:
            if scenario not in {"AMOUNT_RISK","HIGH_AMOUNT","VERY_HIGH_AMOUNT","HIGH_VELOCITY","CROSS_BORDER","POSSIBLE_DUPLICATE_CHARGE","TRANSFER","MERCHANT_MARKER"}:raise ValueError("Invalid scenario")
            where+=" AND EXISTS(SELECT 1 FROM jsonb_array_elements(p.result->'triggered_rules') signal WHERE signal->>'rule'=%s)";params.append(scenario)
        assignee=args.get("assignee")
        if assignee:
            if len(assignee)>200:raise ValueError("Invalid assignee")
            where+=" AND w.reviewer_subject=%s";params.append(assignee)
        sorting=args.get("sort","oldest")
        orders={"oldest":"r.created_at,r.risk_event_id","newest":"r.created_at DESC,r.risk_event_id DESC","severity":"r.risk_score DESC,r.created_at,r.risk_event_id","amount":"t.amount DESC,r.created_at,r.risk_event_id"}
        if sorting not in orders:raise ValueError("Invalid investigation sort")
        order=orders[sorting]
    status=args.get("status")
    if status:
        valid={"risk-events":{"OPEN","UNDER_REVIEW","CLEARED","CONFIRMED_RISK","ESCALATED"},"reviews":{"OPEN","UNDER_REVIEW","CLEARED","CONFIRMED_RISK","ESCALATED"},"quarantine":{"OPEN","RESUBMITTED","RESOLVED","REJECTED"},"batches":{"RECEIVED","PROCESSING","QUEUED","COMPLETED","PARTIAL","FAILED"}}
        if status not in valid.get(kind,set()): raise ValueError("Unsupported status filter")
        field={"risk-events":"w.review_status","reviews":"w.review_status","quarantine":"q.workflow_status","batches":"r.status"}[kind]
        where+=" AND "+field+"=%s";params.append(status)
    rows=_query(select+" WHERE "+where+" ORDER BY "+order+" LIMIT %s OFFSET %s",tuple(params+[limit+1,offset]))
    if kind in {"reviews","risk-events"}:
        from .review_assignment import decorate
        rows=decorate(rows)
    if kind=="quarantine":
        for row in rows:
            row["recovery_status"]="ACCEPTED" if row["workflow_status"]=="RESOLVED" else "CORRECTED" if row["workflow_status"]=="RESUBMITTED" else "REVALIDATION_FAILED" if row.get("correction_id") and row["workflow_status"]=="OPEN" else row["workflow_status"]
    if kind=="batches":
        import os
        if os.getenv("FINTRUST_MODE")=="local" and principal.role!="Maintainer":
            from .frontend_workflows import upload_history
            receipts=upload_history(principal)
            for row in rows:
                events=[e for e in receipts if e.get("batch_id")==str(row["batch_id"])]
                row["filename"]=events[-1]["filename"] if events else None
                row["actor"]=events[-1]["actor"] if events else None
        for row in rows:
            row["display_status"]=row["status"] if row["counts_consistent"] else "AWAITING_RECONCILIATION" if row["rows_received"] is None else "RECONCILIATION_FAILED"
    meta={"count":len(rows[:limit]),"limit":limit,"offset":offset,"has_more":len(rows)>limit}
    if kind in {"reviews","risk-events"}:
        counts=_query("SELECT count(*) AS total_count,count(*) FILTER(WHERE evidence.risk->>'risk_level'='High') AS high_count,count(*) FILTER(WHERE evidence.review_status IN ('OPEN','UNDER_REVIEW','ESCALATED')) AS active_count FROM ("+select+" WHERE "+where+") evidence",tuple(params))[0]
        meta.update(counts)
    return {"data":rows[:limit],"meta":meta}

def detail(identifier,principal):
    identifier=str(uuid.UUID(identifier))
    rows=_query("SELECT t.*,p.result AS risk FROM transactions t LEFT JOIN processed_transactions p USING(tx_id) WHERE t.tx_id=%s AND t.account_id=ANY(%s::uuid[])",(identifier,list(principal.accounts)))
    if not rows: raise NotFound()
    result=rows[0]
    result["review_history"]=_query("SELECT h.* FROM risk_review_history h JOIN risk_events r USING(risk_event_id) WHERE r.tx_id=%s ORDER BY h.changed_at,h.version",(identifier,))
    result["alert_delivery"]=_query("SELECT delivery_key,delivery_state,sent_at,provider_message_id FROM alerts a JOIN risk_events r USING(risk_event_id) WHERE r.tx_id=%s",(identifier,))
    from .dynamo import get_item
    import os
    from botocore.exceptions import ClientError,BotoCoreError
    try:claim=get_item(os.environ.get("DYNAMODB_TABLE","risk_scores"),{"account_id":str(result["account_id"]),"score_date":"ALERT#"+identifier})
    except (ClientError,BotoCoreError):claim={"delivery_state":"UNAVAILABLE"}
    allowed=("delivery_state","risk_event_id","provider_message_id","updated_at")
    result["cloud_alert"]={k:claim[k] for k in allowed if k in claim} if claim else {"delivery_state":"PENDING" if (result.get("risk") or {}).get("risk_level")=="High" else "NOT_REQUIRED"}
    result["cloud_alert_note"]="SQL delivery entries are local/legacy evidence; cloud claims are read separately. SENDING/UNKNOWN require provider reconciliation."
    return result

def _body(body,fields):
    if not isinstance(body,dict) or set(body)!=set(fields): raise ValueError("Exact mutation fields required")
    if not isinstance(body["request_id"],str): raise ValueError("Request identity must be UUID text")
    identifier=str(uuid.UUID(body["request_id"]))
    notes=body["notes"]
    if not isinstance(notes,str) or not 1<=len(notes.strip())<=2000: raise ValueError("A bounded review note is required")
    digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    return identifier,digest

def _update_review(event,body,principal):
    principal.require("review")
    if type(event) is not int or event<1: raise ValueError("Invalid risk event identifier")
    request,digest=_body(body,{"request_id","expected_version","status","notes","resolution_code"})
    if not isinstance(body["status"],str) or body["resolution_code"] is not None and not isinstance(body["resolution_code"],str): raise ValueError("Invalid review state values")
    if type(body["expected_version"]) is not int or body["expected_version"]<1: raise ValueError("Integer expected version required")
    conn=connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT w.*,t.account_id::text FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE w.risk_event_id=%s FOR UPDATE OF w",(event,));row=cur.fetchone()
                if not row: raise NotFound()
                principal.account(row["account_id"])
                cur.execute("SELECT * FROM risk_review_history WHERE request_id=%s",(request,));prior=cur.fetchone()
                if prior:
                    if prior["risk_event_id"]!=event or prior["actor_subject"]!=principal.subject or prior["request_digest"]!=digest: raise Conflict("Request identifier reused")
                    return {"risk_event_id":event,"version":prior["version"],"review_status":prior["after_status"],"replayed":True}
                if row["version"]!=body["expected_version"]: raise Conflict("Review changed; refresh before retry")
                review_transition(row["review_status"],body["status"],role=principal.role,notes=body["notes"],resolution_code=body["resolution_code"])
                if row["reviewer_subject"] is not None and row["reviewer_subject"]!=principal.subject: raise PermissionError("Review is assigned to another analyst")
                if row["review_status"]=="UNDER_REVIEW" and not row["reviewer_subject"]: raise Conflict("Review must be claimed before decision")
                terminal=body["status"] in {"CLEARED","CONFIRMED_RISK","ESCALATED"}
                cur.execute("""UPDATE risk_reviews SET review_status=%s,reviewer_subject=%s,reviewed_by=%s,reviewed_at=%s,
                    review_notes=%s,resolution_code=%s,change_actor=%s,change_request_id=%s,request_digest=%s,version=version+1
                    WHERE risk_event_id=%s RETURNING version""",
                    (body["status"],principal.subject,principal.subject if terminal else None,datetime.now(timezone.utc) if terminal else None,
                     body["notes"],body["resolution_code"] if terminal else None,principal.subject,request,digest,event))
                return {"risk_event_id":event,"version":cur.fetchone()["version"],"review_status":body["status"]}
    finally: conn.close()

def _correct_case(identifier,body,principal):
    identifier=str(uuid.UUID(identifier))
    request,digest=_body(body,{"request_id","action","notes","candidate"})
    action=body["action"]
    principal.require("reject_quarantine" if action=="REJECT" else "correct")
    if not isinstance(action,str) or action not in {"RESUBMIT","REJECT"}: raise ValueError("Invalid correction action")
    candidate=body["candidate"]
    if action=="REJECT" and candidate is not None: raise ValueError("Rejection cannot contain replacement values")
    if action=="RESUBMIT":
        if not isinstance(candidate,dict) or set(candidate)-FIELDS or not all(isinstance(v,str) for v in candidate.values()):
            raise ValueError("Only named transaction candidate fields are allowed")
        # Corrections must target assigned real accounts; all other validation is repeated by the worker.
        principal.account(candidate.get("account_id",""))
    conn=connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT quarantine_id FROM quarantine_cases WHERE quarantine_id=%s FOR UPDATE",(identifier,))
                cur.execute("SELECT q.*,EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id) AS account_known FROM quarantine_workflow q WHERE quarantine_id=%s",(identifier,))
                # Views with lateral joins cannot be locked: lock the immutable parent separately below.
                row=cur.fetchone()
                if not row: raise NotFound()
                if row["account_known"]: principal.account(row["candidate_account_id"])
                else:
                    from .upload_ownership import owns
                    if not owns(row['batch_id'],principal):raise PermissionError('Unknown-account correction requires original upload ownership')
                if action=='RESUBMIT':
                    cur.execute('SELECT 1 FROM accounts WHERE account_id=%s',(candidate['account_id'],))
                    if not cur.fetchone():raise PermissionError('Corrected account must exist and be assigned')
                cur.execute("SELECT quarantine_id FROM quarantine_cases WHERE quarantine_id=%s FOR UPDATE",(identifier,))
                cur.execute("SELECT * FROM quarantine_corrections WHERE request_id=%s",(request,));prior=cur.fetchone()
                if prior:
                    if str(prior["quarantine_id"])!=identifier or prior["submitted_by"]!=principal.subject or prior["request_digest"]!=digest: raise Conflict("Request identifier reused")
                    return {"correction_id":str(prior["correction_id"]),"status":"REPLAYED"}
                if row["workflow_status"]!="OPEN": raise Conflict("Case is resolved or awaiting processing")
                from .evidence_reads import read
                if read(row['safe_payload_key'],row['safe_payload_version'])[0] is None:
                    raise Conflict('Original evidence required before a new correction or rejection')
                correction=str(uuid.uuid5(uuid.UUID(identifier),request))
                envelope=None;key=None;version=None;batch=None
                if action=="RESUBMIT":
                    from .release_ingest import envelopes
                    import os
                    from .batches import metadata
                    payload=json.dumps({"correction_id":correction,"candidate":candidate},sort_keys=True).encode()
                    bucket=os.environ["QUARANTINE_BUCKET"]
                    key="quarantine/corrections/"+correction+".json"
                    response=workflow.score.s3.put_object(Bucket=bucket,Key=key,Body=payload,ContentType="application/json")
                    version=response.get("VersionId")
                    if not version: raise RuntimeError("Versioned correction evidence required")
                    b=metadata(bucket,payload)
                    # Different correction attempts are distinct batch occurrences, even for identical candidate values.
                    b["batch_id"]=correction
                    batch=b["batch_id"]
                    envelope={"schema_version":3,"kind":"ROW","batch":b,"attempt_id":correction,"rows_received":1,
                              "source_system":"manual-correction","source":{"bucket":bucket,"key":key,"version":version,"etag":None,"row":2},"row":candidate,"parse_error":None}
                    cur.execute("INSERT INTO ingestion_batches(batch_id,source_system,source_bucket,file_sha256,received_at,rows_received,publication_complete) VALUES(%s,'manual-correction',%s,%s,%s,1,TRUE)",(batch,bucket,b["file_sha256"],b["ingested_at"]))
                    cur.execute("INSERT INTO ingestion_attempts(attempt_id,batch_id,source_bucket,source_file,source_version,received_at,status) VALUES(%s,%s,%s,%s,%s,%s,'QUEUED')",(correction,batch,bucket,key,version,b["ingested_at"]))
                    cur.execute("INSERT INTO ingestion_records(batch_id,source_row,source_attempt_id,disposition) VALUES(%s,2,%s,'QUEUED')",(batch,correction))
                cur.execute("""INSERT INTO quarantine_corrections(correction_id,quarantine_id,request_id,request_digest,submitted_by,submitted_at,correction_notes,
                    corrected_payload_key,corrected_payload_version,action,reprocess_batch_id,reprocess_source_row)
                    VALUES(%s,%s,%s,%s,%s,NOW(),%s,%s,%s,%s,%s,%s)""",
                    (correction,identifier,request,digest,principal.subject,body["notes"],key,version,action,batch,2 if batch else None))
                if envelope: cur.execute("INSERT INTO correction_outbox(correction_id,envelope) VALUES(%s,%s)",(correction,Json(envelope)))
                return {"correction_id":correction,"status":"RESUBMITTED" if envelope else "REJECTED"}
    finally: conn.close()


def report(principal,args):
    limit,offset=page_args(args,{"account_id","from","to","currency"})
    scope=[principal.account(args["account_id"])] if args.get("account_id") else list(principal.accounts)
    where="account_id=ANY(%s::uuid[])";params=[scope];dates={}
    for key,operator in (("from",">="),("to","<")):
        if args.get(key):
            try:value=datetime.strptime(args[key],"%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:raise ValueError("Report date must be YYYY-MM-DD") from None
            dates[key]=value;where+=" AND tx_date"+operator+"%s";params.append(value)
    if len(dates)==2 and dates["from"]>=dates["to"]:raise ValueError("Report end must be after start")
    if args.get("currency"):
        currency=args["currency"]
        if len(currency)!=3 or not currency.isascii() or not currency.isalpha() or currency!=currency.upper():raise ValueError("Report currency must be three uppercase letters")
        where+=" AND currency=%s";params.append(currency)
    rows=_query("""SELECT account_id::text,currency,count(*) AS transactions,
        sum(CASE WHEN tx_type='credit' THEN amount ELSE -amount END)::text AS net_movement,
        sum(amount)::text AS gross_amount FROM transactions WHERE """+where+" GROUP BY account_id,currency ORDER BY account_id,currency LIMIT %s OFFSET %s",tuple(params+[limit+1,offset]))
    return {"data":rows[:limit],"meta":{"limit":limit,"offset":offset,"has_more":len(rows)>limit},"meaning":"Accepted ledger net movement from zero by account/currency; not current balances; no FX conversion", "filters":{k:args[k] for k in ("account_id","from","to","currency") if args.get(k)}}


def metrics(principal):
    principal.require("audit")
    scope=list(principal.accounts)
    feeds=_query("""SELECT status,count(*) AS batches,sum(rows_received) AS rows_received,sum(accepted) AS accepted,
        sum(quarantined) AS quarantined,sum(duplicate) AS duplicate,sum(failed_technical) AS technical_failed,
        sum(pending) AS pending FROM batch_reconciliation GROUP BY status ORDER BY status""") if principal.role=="Admin" else []
    return {"feed_metrics":feeds,"feed_scope":"Global feed health is Admin-only; financial/review metrics are assigned-account scoped", "projection_backlog":_query("SELECT count(*) AS pending FROM projection_outbox p JOIN transactions t USING(tx_id) WHERE p.state='PENDING' AND t.account_id=ANY(%s::uuid[])",(scope,)),"reviews":_query("""SELECT w.review_status,count(*) AS count,min(w.created_at) AS oldest
        FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id)
        WHERE t.account_id=ANY(%s::uuid[]) GROUP BY w.review_status""",(scope,)),
        "financial":_query("""SELECT count(*) AS accepted_transactions,
        count(*) FILTER(WHERE (p.result->>'risk_level')='High') AS high_risk
        FROM transactions t LEFT JOIN processed_transactions p USING(tx_id) WHERE t.account_id=ANY(%s::uuid[])""",(scope,)),
        "scope":"Assigned accounts only; SQS/DLQ/SES CloudWatch metrics require separately approved cloud verification"}


def quarantine_detail(identifier,principal):
    identifier=str(uuid.UUID(identifier))
    rows=_query("""SELECT q.*,EXISTS(SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id) AS account_known
        FROM quarantine_workflow q WHERE quarantine_id=%s""",(identifier,))
    if not rows: raise NotFound()
    case=rows[0]
    if case["account_known"]: principal.account(case["candidate_account_id"])
    else:
        from .upload_ownership import owns
        if principal.role!='Admin' and not owns(case['batch_id'],principal):raise PermissionError('Unknown case requires original upload ownership')
    from .upload_ownership import owner
    admission=owner(case['batch_id']) if not case['account_known'] else None
    case['original_uploader']=admission['actor'] if admission else None
    import os
    from .evidence_reads import read
    evidence,status=read(case['safe_payload_key'],case['safe_payload_version'])
    case['evidence_status']=status
    case['evidence_available']=status=='AVAILABLE'
    case['evidence_note']='Original version-pinned evidence available.' if evidence is not None else 'Original evidence is unavailable. Correction is blocked until the exact original evidence is restored. Metadata and audit history remain available.'
    case['candidate']={k:v for k,v in (evidence or {}).get('record',{}).items() if k in FIELDS and isinstance(v,str)}
    case['source']=(evidence or {}).get('source')
    case["correction_history"]=_query("""SELECT correction_id,request_id,correction_version,submitted_by,submitted_at,
        correction_notes,action,reprocess_batch_id,reprocess_source_row FROM quarantine_corrections
        WHERE quarantine_id=%s ORDER BY correction_version DESC LIMIT 100""",(identifier,))
    case["history_limit"]=100
    from .quarantine_recovery import enrich
    return enrich(case,principal)

def update_review(event,body,principal):
    from .identity_registry import locked_registry,read_registry
    import os
    with locked_registry(os.environ["FINTRUST_AUTH_FILE"]):
        users=[u for u in read_registry()["principals"] if u["subject"]==principal.subject and u["role"]==principal.role and u.get("status","ACTIVE")=="ACTIVE"]
        if len(users)!=1:raise PermissionError("Identity changed")
        return _update_review(event,body,principal)

def correct_case(identifier,body,principal):
    from .identity_registry import locked_registry,read_registry
    import os
    with locked_registry(os.environ["FINTRUST_AUTH_FILE"]):
        users=[u for u in read_registry()["principals"] if u["subject"]==principal.subject and u["role"]==principal.role and u.get("status","ACTIVE")=="ACTIVE"]
        if len(users)!=1:raise PermissionError("Identity changed")
        return _correct_case(identifier,body,principal)

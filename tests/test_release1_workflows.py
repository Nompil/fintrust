"""Acceptance scenarios from the supplied CSV A/B description; actual files pending.
Reference contract tests are NOT production API/end-to-end verification.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import uuid
import os
import pytest
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
from tools import release1_contract as contract
from fintrust import rules, jobs

RECEIVED=datetime(2026,10,9,10,tzinfo=timezone.utc)
ACCOUNT="20000000-0000-4000-8000-000000000001"
ROOT=Path(__file__).resolve().parents[1]

def row(**changes):
    return {**dict(account_id=ACCOUNT,amount="10.00",currency="ZAR",country="ZA",
        tx_date="2026-10-09T10:00:00Z",tx_type="debit",merchant="Shop",
        source_system="synthetic-demo",source_transaction_id="REF-001"),**changes}

@pytest.mark.parametrize("changes,code",[
    ({"account_id":""},"MISSING_REQUIRED_FIELD"),({"amount":"bad"},"INVALID_AMOUNT"),
    ({"amount":"NaN"},"INVALID_AMOUNT"),({"amount":"0"},"ZERO_AMOUNT"),
    ({"amount":"-1"},"NEGATIVE_AMOUNT"),({"tx_date":"bad"},"INVALID_TIMESTAMP"),
    ({"tx_date":""},"MISSING_REQUIRED_FIELD"),({"tx_date":"2026-10-09"},"INVALID_TIMESTAMP"),
    ({"tx_date":"2026-10-09T10:05:00.000001Z"},"FUTURE_TIMESTAMP"),
    ({"country":"ZZA"},"INVALID_COUNTRY"),({"country":"ZZ"},"UNSUPPORTED_COUNTRY"),
    ({"currency":"XXX"},"UNSUPPORTED_CURRENCY"),({"tx_type":"refund"},"UNSUPPORTED_FINANCIAL_OPERATION"),
    ({"tx_type":"reversal"},"UNSUPPORTED_FINANCIAL_OPERATION"),({"tx_type":"chargeback"},"UNSUPPORTED_FINANCIAL_OPERATION"),
    ({"source_transaction_id":""},"MISSING_SOURCE_IDENTITY"),({"transaction_id":""},"INVALID_TRANSACTION_ID"),
    ({"amount":"0.001"},"AMOUNT_PRECISION"),({"amount":"10000000000000"},"AMOUNT_OUT_OF_RANGE"),
    ({None:"extra"},"MALFORMED_ROW")])
def test_validation_scenarios(changes,code):
    assert code in {x["reason_code"] for x in contract.validation_errors({**row(),**changes},RECEIVED)}

@pytest.mark.parametrize("seconds,valid",[(299,True),(300,True),(300.000001,False)])
def test_future_tolerance_edges(seconds,valid):
    timestamp=(RECEIVED+timedelta(seconds=seconds)).isoformat()
    assert (not contract.validation_errors(row(tx_date=timestamp),RECEIVED)) is valid

def test_normal_unknown_account_and_missing_internal_id():
    assert contract.validation_errors(row(),RECEIVED)==[] # upstream reference permits generated tx_id
    assert contract.validation_errors(row(),RECEIVED,known_account=False)[0]["reason_code"]=="UNKNOWN_ACCOUNT"
    assert contract.validation_errors(row(source_transaction_id="",tx_date=""),RECEIVED)

@pytest.mark.parametrize("amount,score",[("49999.99",0),("50000.00",0),("50000.01",30),("200000",30),("200000.01",55)])
def test_amount_edges(amount,score):
    assert rules.evaluate(row(amount=amount))["score"]==score

def test_cross_border_combination_and_similar_charge():
    assert rules.evaluate(row(country="US"))["score"]==15
    assert rules.evaluate(row(country="US"))["risk_level"]=="Low"
    assert rules.evaluate(row(amount="200000.01",country="US"),velocity=6)["score"]==100
    result=rules.evaluate(row(),duplicate_matches=[str(uuid.uuid4())])
    assert result["score"]==40 and result["risk_level"]=="Medium"
    first=jobs.make_job(row(),"bucket","a.csv","a",2)
    other=jobs.make_job(row(source_transaction_id="REF-002"),"bucket","b.csv","b",2)
    assert jobs.identity_key(first)!=jobs.identity_key(other)

@pytest.mark.parametrize("count,present",[(4,False),(5,False),(6,True)])
def test_velocity_count_edges(count,present):
    assert ("HIGH_VELOCITY" in {x["rule"] for x in rules.evaluate(row(),velocity=count)["triggered_rules"]}) is present

def test_twelve_spread_over_hour_does_not_imply_five_minute_velocity():
    times=[RECEIVED+timedelta(minutes=5*i) for i in range(12)]
    counts=[sum(when-timedelta(seconds=300)<=t<=when for t in times[:i+1]) for i,when in enumerate(times)]
    assert max(counts)==2
    assert all("HIGH_VELOCITY" not in {x["rule"] for x in rules.evaluate(row(),velocity=n)["triggered_rules"]} for n in counts)

def test_review_rbac_and_transitions():
    assert contract.review_transition("OPEN","UNDER_REVIEW",role="Risk/Compliance Analyst",notes="Assigned")=="UNDER_REVIEW"
    assert contract.review_transition("UNDER_REVIEW","CLEARED",role="Risk/Compliance Analyst",notes="Verified",resolution_code="VALID_ACTIVITY")=="CLEARED"
    with pytest.raises(PermissionError): contract.review_transition("OPEN","UNDER_REVIEW",role="Read-only/Auditor",notes="Assigned")
    with pytest.raises(PermissionError): contract.review_transition("CLEARED","UNDER_REVIEW",role="Risk/Compliance Analyst",notes="Reopen")
    assert contract.review_transition("CLEARED","UNDER_REVIEW",role="Admin",notes="New evidence")=="UNDER_REVIEW"
    with pytest.raises(ValueError): contract.review_transition("OPEN","CLEARED",role="Admin",notes="skip",resolution_code="VALID_ACTIVITY")
    with pytest.raises(ValueError): contract.review_transition("UNDER_REVIEW","CLEARED",role="Admin",notes="",resolution_code="VALID_ACTIVITY")

def test_reconciliation_pending_technical_and_business_failures():
    mixed=["ACCEPTED","QUARANTINED","DUPLICATE","QUEUED"]
    assert contract.reconcile(mixed,total=4,publication_complete=True)["status"]=="PUBLISHED"
    assert contract.reconcile(mixed[:3],total=3,publication_complete=True)["status"]=="COMPLETED"
    assert contract.reconcile(mixed[:3]+["FAILED_TECHNICAL"],total=4,publication_complete=True)["status"]=="PARTIAL"
    assert contract.reconcile(["FAILED_TECHNICAL"],total=1,publication_complete=False)["status"]=="FAILED"
    assert contract.reconcile([],total=None,publication_complete=False,file_failure=True)["rows_received"] is None

@pytest.fixture
def operational_db():
    dsn=os.getenv("FINTRUST_TEST_DATABASE_URL")
    if not dsn: pytest.skip("Isolated local PostgreSQL required")
    target=parse_dsn(dsn)
    assert target.get("host") in {"127.0.0.1","localhost","::1"}
    assert target.get("dbname") in {"fintrust_local_test","fintrust_test"}
    conn=psycopg2.connect(dsn); name="workflow_"+uuid.uuid4().hex
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(name)))
        cur.execute((ROOT/"sql/schema.sql").read_text().replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;",""))
        cur.execute((ROOT/"sql/seed.sql").read_text())
    conn.commit()
    proposal=(ROOT/"sql/migrations/002_operational_workflows.sql").read_text().replace("public.",name+".")
    with conn.cursor() as cur: cur.execute(proposal)
    conn.commit()
    try: yield conn
    finally:
        conn.rollback()
        with conn.cursor() as cur: cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
        conn.commit();conn.close()

def query(conn,text,args=()):
    with conn.cursor() as cur:
        cur.execute(text,args)
        return cur.fetchall() if cur.description else []

def batch(conn,total=1):
    identifier=str(uuid.uuid4())
    query(conn,"INSERT INTO ingestion_batches(batch_id,source_system,source_bucket,file_sha256,received_at,rows_received) VALUES(%s,'demo','bucket',%s,%s,%s)",(identifier,uuid.uuid4().hex*2,RECEIVED,total))
    query(conn,"INSERT INTO ingestion_attempts(attempt_id,batch_id,source_bucket,source_file,received_at,status) VALUES(%s,%s,'bucket','original.csv',%s,'PROCESSING')",(identifier,identifier,RECEIVED))
    return identifier

def risk(conn):
    return query(conn,"INSERT INTO risk_events(tx_id,risk_score,reason) SELECT tx_id,70,'Test' FROM transactions LIMIT 1 RETURNING risk_event_id")[0][0]

def test_review_schema_audit_and_stale_update(operational_db):
    c=operational_db;event=risk(c)
    query(c,"INSERT INTO risk_reviews(risk_event_id,change_actor) VALUES(%s,'system')",(event,))
    query(c,"UPDATE risk_reviews SET review_status='UNDER_REVIEW',reviewer_subject='analyst-1',change_actor='analyst-1',review_notes='Assigned',change_request_id=gen_random_uuid(),version=2 WHERE risk_event_id=%s AND version=1",(event,))
    query(c,"UPDATE risk_reviews SET review_status='CLEARED',reviewed_by='analyst-1',reviewed_at=NOW(),change_actor='analyst-1',review_notes='Checked',resolution_code='VALID_ACTIVITY',change_request_id=gen_random_uuid(),version=3 WHERE risk_event_id=%s AND version=2",(event,))
    assert query(c,"SELECT after_status FROM risk_review_history WHERE risk_event_id=%s ORDER BY version",(event,))==[("OPEN",),("UNDER_REVIEW",),("CLEARED",)]
    assert query(c,"UPDATE risk_reviews SET version=3 WHERE risk_event_id=%s AND version=2 RETURNING version",(event,))==[]
    c.commit()
    with pytest.raises(psycopg2.Error): query(c,"DELETE FROM risk_review_history WHERE risk_event_id=%s",(event,))
    c.rollback()
    assert query(c,"SELECT count(*) FROM transactions")[0][0]==200

def test_review_invalid_transition_atomic(operational_db):
    c=operational_db;event=risk(c)
    query(c,"INSERT INTO risk_reviews(risk_event_id,change_actor) VALUES(%s,'system')",(event,));c.commit()
    with pytest.raises(psycopg2.Error): query(c,"UPDATE risk_reviews SET review_status='CLEARED',version=2 WHERE risk_event_id=%s",(event,))
    c.rollback()
    assert query(c,"SELECT review_status FROM risk_reviews WHERE risk_event_id=%s",(event,))==[("OPEN",)]

def test_sql_reconciliation_and_terminal_immutability(operational_db):
    c=operational_db;b=batch(c,3);tx=query(c,"SELECT tx_id FROM transactions LIMIT 1")[0][0]
    for number,state,canonical,reason in [(2,"ACCEPTED",tx,None),(3,"QUARANTINED",None,"INVALID_AMOUNT"),(4,"QUEUED",None,None)]:
        query(c,"INSERT INTO ingestion_records(batch_id,source_row,disposition,canonical_tx_id,reason_code,source_attempt_id) VALUES(%s,%s,%s,%s,%s,%s)",(b,number,state,canonical,reason,b))
    query(c,"UPDATE ingestion_batches SET publication_complete=TRUE WHERE batch_id=%s",(b,));c.commit()
    assert query(c,"SELECT status,pending,accepted,quarantined FROM batch_reconciliation WHERE batch_id=%s",(b,))==[("PUBLISHED",1,1,1)]
    query(c,"UPDATE ingestion_records SET disposition='DUPLICATE',canonical_tx_id=%s,reason_code='DUPLICATE_TRANSACTION' WHERE batch_id=%s AND source_row=4",(tx,b));c.commit()
    assert query(c,"SELECT status,pending FROM batch_reconciliation WHERE batch_id=%s",(b,))==[("COMPLETED",0)]
    with pytest.raises(psycopg2.Error): query(c,"UPDATE ingestion_records SET disposition='QUEUED' WHERE batch_id=%s AND source_row=2",(b,))
    c.rollback()

def test_sql_counts_cannot_overflow_and_whole_file_attempt_does_not_add_rows(operational_db):
    c=operational_db;b=batch(c,1);c.commit()
    with pytest.raises(psycopg2.Error):
        query(c,"INSERT INTO ingestion_records(batch_id,source_row,disposition,source_attempt_id) VALUES(%s,2,'QUEUED',%s),(%s,3,'QUEUED',%s)",(b,b,b,b));c.commit()
    c.rollback()
    query(c,"INSERT INTO ingestion_attempts(attempt_id,batch_id,source_bucket,source_file,received_at,status) VALUES(%s,%s,'bucket','renamed.csv',%s,'DUPLICATE_FILE')",(str(uuid.uuid4()),b,RECEIVED))
    assert query(c,"SELECT rows_received,recorded FROM batch_reconciliation WHERE batch_id=%s",(b,))==[(1,0)]

def test_correction_new_occurrence_and_resolution(operational_db):
    c=operational_db;b=batch(c);q=str(uuid.uuid4())
    query(c,"INSERT INTO ingestion_records(batch_id,source_row,disposition,reason_code,source_attempt_id) VALUES(%s,2,'QUARANTINED','INVALID_AMOUNT',%s)",(b,b))
    query(c,"INSERT INTO quarantine_cases(quarantine_id,batch_id,source_row,reason_code,reason_detail,safe_payload_key,safe_payload_version,quarantined_at) VALUES(%s,%s,2,'INVALID_AMOUNT','Not numeric','safe/original','v1',%s)",(q,b,RECEIVED))
    new=batch(c);query(c,"INSERT INTO ingestion_records(batch_id,source_row,disposition,source_attempt_id) VALUES(%s,2,'QUEUED',%s)",(new,new))
    request=str(uuid.uuid4())
    query(c,"INSERT INTO quarantine_corrections(correction_id,quarantine_id,request_id,submitted_by,submitted_at,correction_notes,corrected_payload_key,corrected_payload_version,action,reprocess_batch_id,reprocess_source_row) VALUES(%s,%s,%s,'analyst',%s,'Fixed amount','safe/correction','v2','RESUBMIT',%s,2)",(str(uuid.uuid4()),q,request,RECEIVED,new));c.commit()
    assert query(c,"SELECT workflow_status FROM quarantine_workflow WHERE quarantine_id=%s",(q,))==[("RESUBMITTED",)]
    with pytest.raises(psycopg2.Error): query(c,"DELETE FROM quarantine_cases WHERE quarantine_id=%s",(q,))
    c.rollback()
    tx=query(c,"SELECT tx_id FROM transactions LIMIT 1")[0][0]
    query(c,"UPDATE ingestion_records SET disposition='DUPLICATE',canonical_tx_id=%s,reason_code='DUPLICATE_TRANSACTION' WHERE batch_id=%s AND source_row=2",(tx,new));c.commit()
    assert query(c,"SELECT workflow_status,canonical_tx_id FROM quarantine_workflow WHERE quarantine_id=%s",(q,))==[("RESOLVED",tx)]
    assert query(c,"SELECT disposition FROM ingestion_records WHERE batch_id=%s",(b,))==[("QUARANTINED",)]

def test_schema_does_not_change_001_or_embed_operational_columns_in_transactions():
    import hashlib
    data=(ROOT/"sql/migrations/001_transaction_identity.sql").read_bytes().replace(b"\r\n",b"\n")
    assert hashlib.sha256(data).hexdigest()=="0ff06ca8c43596ac9b8651f4bd851bfb0487343f4c9eccb198849e3e59772bd6"


from tests.data_quality.test_processing import pipeline
from tests.data_quality.test_constraints import prepared_database_url
from fintrust import score

@pytest.mark.parametrize("seconds,expected",[(-120.000001,False),(-120,True),(-119.999999,True),(119.999999,True),(120,True),(120.000001,False)])
def test_duplicate_charge_closed_window_edges(pipeline,seconds,expected):
    make,*_=pipeline
    when=datetime(2024,2,29,12,tzinfo=timezone.utc)
    score.persist_score(make(source_system="demo",source_transaction_id="FIRST",merchant="Exact merchant",tx_date=when.isoformat()))
    result=score.persist_score(make(source_system="demo",source_transaction_id="SECOND",merchant="Exact merchant",tx_date=(when+timedelta(seconds=seconds)).isoformat()))
    assert ("POSSIBLE_DUPLICATE_CHARGE" in {x["rule"] for x in result["triggered_rules"]}) is expected

@pytest.mark.parametrize("value,level",[(39,"Low"),(40,"Medium"),(69,"Medium"),(70,"High")])
def test_risk_level_edges(value,level):
    assert rules.classify_risk(value)==level

def test_sql_record_delete_and_unknown_total_failure(operational_db):
    c=operational_db;b=batch(c,1)
    query(c,"INSERT INTO ingestion_records(batch_id,source_row,source_attempt_id,disposition,reason_code) VALUES(%s,2,%s,'FAILED_TECHNICAL','DATABASE_UNAVAILABLE')",(b,b));c.commit()
    assert query(c,"SELECT status,failed_technical,pending FROM batch_reconciliation WHERE batch_id=%s",(b,))==[("FAILED",1,0)]
    with pytest.raises(psycopg2.Error): query(c,"DELETE FROM ingestion_records WHERE batch_id=%s",(b,))
    c.rollback()
    query(c,"UPDATE ingestion_records SET disposition='QUEUED' WHERE batch_id=%s",(b,));c.commit()
    assert query(c,"SELECT status,pending FROM batch_reconciliation WHERE batch_id=%s",(b,))==[("PROCESSING",1)]
    unknown=batch(c,None)
    query(c,"UPDATE ingestion_batches SET file_failure_code='MALFORMED_FILE' WHERE batch_id=%s",(unknown,))
    assert query(c,"SELECT status,rows_received FROM batch_reconciliation WHERE batch_id=%s",(unknown,))==[("FAILED",None)]

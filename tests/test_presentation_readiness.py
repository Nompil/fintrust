"""Real local PostgreSQL + mocked cloud presentation contracts."""
import json,uuid,os
from pathlib import Path
import pytest
from tests.test_release1_end_to_end import release_db,authenticated_client,feed,run,row,ACCOUNT
from tests.test_release1_candidate import maintainer_headers
from tests.test_frontend_workflows import local_receipts

def user():
    return dict(username="analyst02",display_name="Analyst Two",role="Risk/Compliance Analyst",status="ACTIVE",notes="Controlled local governance")

def test_governance_actor_audit_and_no_credential_issuance(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client
    r=client.post("/v1/administration/users",json=user(),headers=headers("Admin"))
    assert r.status_code==200,r.json
    assert r.json["data"]["credential_provisioned"] is False
    listing=client.get("/v1/administration/users",headers=headers("Admin"))
    assert listing.status_code==200 and "token_sha256" not in str(listing.json)
    events=client.get("/v1/audit-events",headers=headers("Read-only/Auditor")).json["data"]
    assert any(e["action"]=="USER_CREATED" and e["actor"]=="Admin" and e["actor_role"]=="Admin" and e["result"]=="SUCCESS" for e in events)

@pytest.mark.parametrize("role",["Risk/Compliance Analyst","Read-only/Auditor"])
def test_nonadmin_forbidden_even_invalid_body(release_db,authenticated_client,local_receipts,role):
    client,headers=authenticated_client
    assert client.get("/v1/administration/users",headers=headers(role)).status_code==403
    assert client.post("/v1/administration/users",json={},headers=headers(role)).status_code==403

def test_disable_reactivate_and_live_role_reload(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client;name="Risk/Compliance Analyst"
    path=Path(os.environ["FINTRUST_AUTH_FILE"]);registry=json.loads(path.read_text())
    entry=next(p for p in registry["principals"] if p["role"]==name);entry["subject"]="analyst01";digest=entry["token_sha256"];path.write_text(json.dumps(registry))
    body={**user(),"username":"analyst01","role":"Read-only/Auditor","status":"DISABLED"}
    assert client.post("/v1/administration/users",json=body,headers=headers("Admin")).status_code==200
    assert client.get("/v1/session",headers=headers(name)).status_code==401
    assert client.post("/v1/administration/users",json={**body,"status":"ACTIVE"},headers=headers("Admin")).status_code==200
    assert client.get("/v1/session",headers=headers(name)).json["data"]["role"]=="Read-only/Auditor"
    assert next(p for p in json.loads(path.read_text())["principals"] if p["subject"]=="analyst01")["token_sha256"]==digest

def test_invalid_fields_self_protection_and_local_only(release_db,authenticated_client,local_receipts,monkeypatch):
    client,headers=authenticated_client
    for body in ({**user(),"role":[]},{**user(),"status":{}},{**user(),"notes":""},{**user(),"username":"Admin","status":"DISABLED"}):
        assert client.post("/v1/administration/users",json=body,headers=headers("Admin")).status_code==400
    monkeypatch.setenv("FINTRUST_MODE","aws")
    assert client.get("/v1/administration/users",headers=headers("Admin")).status_code==403

def test_admin_auditor_maintainer_no_compliance_mutation(release_db,authenticated_client,maintainer_headers):
    client,headers=authenticated_client
    run(feed([row(amount="200000.01",country="US")]))
    event=release_db[3]("SELECT risk_event_id FROM risk_reviews")[0][0]
    body=dict(request_id=str(uuid.uuid4()),expected_version=1,status="UNDER_REVIEW",notes="No authority",resolution_code=None)
    for auth in (headers("Admin"),headers("Read-only/Auditor"),maintainer_headers):
        assert client.post(f"/v1/reviews/{event}/transition",json=body,headers=auth).status_code==403

def test_insights_real_totals_unscored_exclusion_and_scope(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client;q=release_db[3]
    run(feed([row(),row(source_transaction_id="HIGH",amount="200000.01",country="US"),row(source_transaction_id="BAD",amount="0"),row()]))
    r=client.get("/v1/release1/insights?days=all",headers=headers("Admin"));assert r.status_code==200,r.json
    d=r.json["data"];total=q("SELECT count(*) FROM transactions WHERE account_id=%s",(ACCOUNT,))[0][0]
    assert sum(r["count"] for r in d["activity"])==total
    assert sum(r["count"] for r in d["cross_border"])==total
    assert {r["label"] for r in d["accounts"]}=={ACCOUNT}
    assert sum(r["count"] for r in d["risk"])==2
    assert sum(r["count"] for r in d["quality"])==1
    assert d["batch_reconciliation"]["rows_received"]==4
    assert sum(r["count"] for r in d["batch_outcomes"])==4
    other="20000000-0000-4000-8000-000000000002"
    run(feed([row(account_id=other,source_transaction_id="FOREIGN")],"raw/foreign.csv"))
    scoped=client.get("/v1/release1/insights?days=all&account_id="+ACCOUNT,headers=headers("Admin")).json["data"]
    assert scoped["batch_reconciliation"]["rows_received"]==4
    assert client.get("/v1/release1/insights?account_id="+other,headers=headers("Admin")).status_code==403

@pytest.mark.parametrize("query",["days=2","days=7&days=30","unknown=x"])
def test_insight_filter_validation(release_db,authenticated_client,query):
    client,headers=authenticated_client
    assert client.get("/v1/release1/insights?"+query,headers=headers("Admin")).status_code==400
    if query=="days=2":
        assert client.get("/v1/release1/insights?days=1",headers=headers("Admin")).status_code==200

def test_empty_scored_state_and_maintainer_denied(release_db,authenticated_client,maintainer_headers):
    client,headers=authenticated_client
    d=client.get("/v1/release1/insights?days=7",headers=headers("Read-only/Auditor")).json["data"]
    assert d["risk"]==[] and d["quality"]==[] and d["reviews"]==[]
    assert client.get("/v1/release1/insights",headers=maintainer_headers).status_code==403


def test_governance_foreign_target_and_provisioned_admin_safety(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client
    path=Path(os.environ["FINTRUST_AUTH_FILE"]);registry=json.loads(path.read_text())
    registry["principals"].append(dict(subject="foreign01",role="Read-only/Auditor",accounts=[str(uuid.uuid4())],token_sha256=""))
    path.write_text(json.dumps(registry))
    assert client.post("/v1/administration/users",json={**user(),"username":"foreign01"},headers=headers("Admin")).status_code==403
    assert "foreign01" not in str(client.get("/v1/administration/users",headers=headers("Admin")).json)
    assert client.post("/v1/administration/users",json={**user(),"username":"Admin","role":"Read-only/Auditor"},headers=headers("Admin")).status_code==400

def test_insight_period_totals_match_scoped_underlying_tables(release_db,authenticated_client):
    from datetime import datetime,timedelta,timezone
    client,headers=authenticated_client;q=release_db[3]
    for days in (7,30,90):
        response=client.get("/v1/release1/insights?days="+str(days),headers=headers("Read-only/Auditor"))
        assert response.status_code==200
        d=response.json["data"]
        since=datetime.fromisoformat(d["from_utc"])
        total=q("SELECT count(*) FROM transactions WHERE account_id=%s AND tx_date>=%s",(ACCOUNT,since))[0][0]
        assert sum(r["count"] for r in d["activity"])==total
        assert sum(r["count"] for r in d["accounts"])==total


def test_launcher_named_users_reset_and_unrelated_schema_protection(tmp_path,monkeypatch):
    import shutil,sys,psycopg2
    from psycopg2.extensions import parse_dsn
    from psycopg2 import sql
    from tools import local,serve_release1_demo as launcher
    from fintrust import api,db,ingest,score,dynamo,release_workflow as worker
    dsn=os.environ["FINTRUST_TEST_DATABASE_URL"];settings=parse_dsn(dsn)
    # Exercise the launcher against this disposable fixture, never host defaults.
    monkeypatch.setattr(local,"TEST_DATABASE",settings["dbname"])
    monkeypatch.setattr(local,"ROLE",settings["user"])
    monkeypatch.setattr(local,"local_settings",lambda:{"DB_HOST":settings["host"],"DB_PORT":settings.get("port","5432"),"DB_PASSWORD":settings["password"]})
    root=Path(__file__).resolve().parents[1]
    (tmp_path/"sql").mkdir()
    for name in ("schema.sql","seed.sql"):shutil.copyfile(root/"sql"/name,tmp_path/"sql"/name)
    monkeypatch.setattr(launcher,"ROOT",tmp_path)
    schema="presentation_reset_"+uuid.uuid4().hex
    monkeypatch.setattr(launcher,"SCHEMA",schema)
    monkeypatch.setattr(launcher,"getpass",lambda prompt:"controlled-test-token-never-log-"+"x"*32)
    import subprocess
    monkeypatch.setattr(subprocess,"check_output",lambda *a,**k:"0"*40)
    monkeypatch.setattr(api.app,"run",lambda **kwargs:None)
    for module in (api,db,ingest,score,worker):monkeypatch.setattr(module,"get_connection",module.get_connection)
    for module in (score,ingest):monkeypatch.setattr(module,"s3",module.s3)
    monkeypatch.setattr(dynamo,"dynamodb",dynamo.dynamodb)
    # Restore environment modified by the launcher as well as injected module clients.
    for key in ("FINTRUST_AUTH_FILE","FINTRUST_MODE","FINTRUST_LOCAL_DEMO","FINTRUST_RELEASE1","FINTRUST_RELEASE1_UPLOAD","INPUT_BUCKET","FINTRUST_ACCOUNT_ID","DYNAMODB_TABLE","QUARANTINE_BUCKET","AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY","AWS_SESSION_TOKEN","AWS_DEFAULT_REGION","AWS_EC2_METADATA_DISABLED","AWS_IGNORE_CONFIGURED_ENDPOINT_URLS","FINTRUST_RELEASE_COMMIT"):
        monkeypatch.setenv(key,os.environ.get(key,""))
    conn=psycopg2.connect(dsn)
    try:
        monkeypatch.setattr(sys,"argv",["serve_release1.py","--role","Admin","--username","admin01"])
        assert launcher.main()==0
        registry=json.loads((tmp_path/".env.release1-auth.json").read_text())
        assert {p["subject"] for p in registry["principals"]}=={"admin01","analyst01","analyst02","auditor01","maintainer01"}
        assert sum(bool(p["token_sha256"]) for p in registry["principals"])==1
        with conn:
            with conn.cursor() as cur:cur.execute(sql.SQL("COMMENT ON SCHEMA {} IS 'unrelated schema'").format(sql.Identifier(schema)))
        monkeypatch.setattr(sys,"argv",["serve_release1.py","--role","Admin","--reset"])
        with pytest.raises(ValueError,match="unrelated"):launcher.main()
        with conn:
            with conn.cursor() as cur:cur.execute(sql.SQL("COMMENT ON SCHEMA {} IS 'FinTrust isolated synthetic Release1 candidate'").format(sql.Identifier(schema)))
        assert launcher.main()==0
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT count(*) FROM {}.transactions").format(sql.Identifier(schema)))
            assert cur.fetchone()==(200,)
    finally:
        conn.rollback()
        with conn:
            with conn.cursor() as cur:cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        conn.close()

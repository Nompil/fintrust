import io
import json

import pytest
from moto import mock_aws

from fintrust import api, ingest, query

ACCOUNT = "20000000-0000-4000-8000-000000000001"


def test_dashboard_and_static_assets_are_available():
    client = api.app.test_client()
    assert b"Imbokodo Bank | Risk &amp; Compliance Workbench" in client.get("/").data
    assert client.get("/").data == client.get("/release1").data
    assert b"earlier learning interface" not in client.get("/").data
    assert client.get("/assets/js/app.js").status_code == 200
    assert client.get("/assets/css/styles.css").status_code == 200


def test_cors_blocks_unknown_origin_before_upload(monkeypatch):
    monkeypatch.setenv("FINTRUST_LOCAL_DEMO", "1")
    response = api.app.test_client().post("/v1/upload", headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_preflight_is_explicit(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    response = api.app.test_client().options("/v1/upload", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"})
    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["Vary"] == "Origin"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_upload_is_disabled_outside_local_demo(monkeypatch):
    monkeypatch.delenv("FINTRUST_LOCAL_DEMO", raising=False)
    assert api.app.test_client().post("/v1/upload").status_code == 404


@mock_aws
def test_custom_csv_upload_quarantines_invalid_rows(monkeypatch):
    import boto3
    monkeypatch.setenv("FINTRUST_LOCAL_DEMO", "1")
    client = boto3.client("s3", region_name="af-south-1")
    client.create_bucket(Bucket="fintrust-local-practice", CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
    monkeypatch.setattr(ingest, "s3", client)
    loaded = []
    monkeypatch.setattr(ingest, "_load_rows", lambda rows: loaded.extend(rows) or [])
    contents = f"account_id,amount,tx_date,tx_type\n{ACCOUNT},12.50,2026-09-30,debit\n{ACCOUNT},-1,2026-09-30,debit\n".encode()
    def upload(name):
        return api.app.test_client().post("/v1/upload", data={"file": (io.BytesIO(contents), name)})
    response = upload("my-export.csv")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["rows_valid"] == 1 and data["rows_quarantined"] == 1
    assert data["quarantine"][0]["source_row"] == 3
    replay = upload("renamed-export.csv").get_json()["data"]
    assert replay["upload_id"] == data["upload_id"]
    assert replay["reason_code"] == "DUPLICATE_FILE" and replay["rows_valid"] == 0
    assert len(loaded) == 1


def test_oversized_and_invalid_uploads_return_json(monkeypatch):
    monkeypatch.setenv("FINTRUST_LOCAL_DEMO", "1")
    client = api.app.test_client()
    assert client.post("/v1/upload").status_code == 400
    assert client.post("/v1/upload", data={"file": (io.BytesIO(b"hello"), "a.exe")}).status_code == 400
    response = client.post("/v1/upload", data={"file": (io.BytesIO(b"a" * (2 * 1024 * 1024)), "big.csv")})
    assert response.status_code == 413 and response.is_json


def test_row_limit_prevents_partial_database_load(monkeypatch):
    monkeypatch.setattr(ingest, "MAX_FILE_ROWS", 1)
    monkeypatch.setattr(ingest, "_load_rows", lambda rows: pytest.fail("must not write partial oversized file"))
    text = f"account_id,amount,tx_date,tx_type\n{ACCOUNT},1,2026-09-30,debit\n" + f"{ACCOUNT},2,2026-09-30,debit\n"
    with pytest.raises(ValueError, match="5000-row"):
        ingest.process_csv("bucket", "raw/test.csv", text)


def test_duplicate_headers_are_rejected():
    with pytest.raises(ValueError, match="duplicate column"):
        ingest.process_csv("bucket", "raw/test.csv", "account_id,amount,tx_date,tx_type,amount\n")


def test_errors_have_correlation_ids_without_exception_details(monkeypatch):
    monkeypatch.setattr(query, "get_accounts", lambda: (_ for _ in ()).throw(RuntimeError("secret-detail")))
    response = api.app.test_client().get("/v1/accounts")
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == response.get_json()["request_id"]
    assert b"secret-detail" not in response.data


def test_request_log_has_status_duration_and_request_id(caplog):
    api.logger.addHandler(caplog.handler)
    try:
        response = api.app.test_client().get("/missing-route")
    finally:
        api.logger.removeHandler(caplog.handler)
    records = [json.loads(record.message) for record in caplog.records if record.message.startswith('{"event": "api_request"')]
    assert records[-1]["status"] == 404
    assert records[-1]["request_id"] == response.headers["X-Request-ID"]
    assert records[-1]["duration_ms"] >= 0


@pytest.fixture(autouse=True)
def authenticated_test_caller(monkeypatch):
    from fintrust import auth
    accounts=tuple("20000000-0000-4000-8000-00000000000"+str(i) for i in range(1,6))
    monkeypatch.setattr(auth,"authenticate",lambda:auth.Principal("test-analyst","Risk/Compliance Analyst",accounts))

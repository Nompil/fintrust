import io

import psycopg2
import pytest

from fintrust import api, ingest, alert, report, score, validators

ACCOUNT = "20000000-0000-4000-8000-000000000001"


def test_short_and_extra_csv_rows_are_quarantined(monkeypatch):
    monkeypatch.setattr(ingest, "_load_rows", lambda rows: [])
    writes = []
    monkeypatch.setattr(ingest.s3, "put_object", lambda **kw: writes.append(kw))
    result = ingest.process_csv("bucket", "raw/test.csv",
        "account_id,amount,tx_date,tx_type\n"
        f"{ACCOUNT},10\n{ACCOUNT},10,2026-09-30,debit,extra\n"
        f"{ACCOUNT},10,2026-09-30,debit\n")
    assert result["rows_valid"] == 1
    assert result["rows_quarantined"] == 2
    assert len(writes) == 1


def test_quarantine_keeps_different_source_versions_separate(monkeypatch):
    keys = []
    monkeypatch.setattr(ingest.s3, "put_object", lambda **kw: keys.append(kw["Key"]))
    csv = "account_id,amount,tx_date,tx_type\ninvalid,-1,2026-09-30,debit\n"
    for identity in ["bucket:raw/a.csv:v1", "bucket:raw/a.csv:v2"]:
        ingest.process_csv("bucket", "raw/a.csv", csv, identity)
    assert len(set(keys)) == 2


def test_handler_processes_all_records_without_decoding_version_id(monkeypatch):
    requests = []
    def get_object(**kw):
        requests.append(kw)
        return {"Body": io.BytesIO(b"data")}
    monkeypatch.setattr(ingest.s3, "get_object", get_object)
    monkeypatch.setattr(ingest, "process_csv", lambda *args: {"rows_valid": 1})
    record = {"s3": {"bucket": {"name": "bucket"},
        "object": {"key": "raw/a+b.csv", "versionId": "version+id"}}}
    result = ingest.lambda_handler({"Records": [record, record]}, None)
    assert result["files_processed"] == 2
    assert requests[0] == {"Bucket": "bucket", "Key": "raw/a b.csv", "VersionId": "version+id"}


def test_database_failure_during_row_retry_rolls_back(monkeypatch):
    class Connection:
        rollbacks = 0
        closed = False
        def cursor(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def executemany(self, *args): raise psycopg2.IntegrityError()
        def execute(self, *args): raise psycopg2.OperationalError()
        def rollback(self): self.rollbacks += 1
        def close(self): self.closed = True
    conn = Connection()
    monkeypatch.setattr(ingest, "get_connection", lambda: conn)
    with pytest.raises(psycopg2.OperationalError):
        ingest._load_rows([("row",)])
    assert conn.rollbacks == 2
    assert conn.closed


@pytest.mark.parametrize("offset", ["-1", "hello"])
def test_invalid_page_offset(offset):
    response = api.app.test_client().get(f"/v1/transactions?account_id={ACCOUNT}&offset={offset}")
    assert response.status_code == 400


def test_page_offset_reaches_query(monkeypatch):
    seen = []
    monkeypatch.setattr(api, "get_transactions", lambda *args: seen.append(args) or [])
    response = api.app.test_client().get(f"/v1/transactions?account_id={ACCOUNT}&limit=10&offset=10")
    assert response.status_code == 200
    assert seen[0][-2:] == (10, 10)


def test_unimplemented_features_do_not_report_success():
    with pytest.raises(NotImplementedError):
        alert.send_alert(ACCOUNT, 75, "High")
    with pytest.raises(NotImplementedError):
        report.generate_monthly_report()
    with pytest.raises(NotImplementedError):
        score.lambda_handler({"Records": [{"body": "{}"}]}, None)


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_shared_validator_rejects_nonfinite_money(amount):
    valid, reason = validators.validate_transaction_record({
        "account_id": ACCOUNT, "amount": amount, "tx_date": "2026-09-30", "tx_type": "debit",
    })
    assert not valid
    assert reason == "amount must be greater than zero"

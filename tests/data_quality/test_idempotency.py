"""Authoritative PostgreSQL identity tests with only mocked external effects."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg2
import pytest
from fintrust import ingest, jobs, score
from fintrust.ledger import IdentityConflict
from .test_processing import pipeline
from .test_constraints import prepared_database_url


def test_same_upstream_reference_different_internal_uuid_returns_canonical_result(pipeline):
    make, query, _, _, _, _ = pipeline
    reference = str(uuid.uuid4())
    a = make(source_system="bank-test", source_transaction_id=reference)
    b = make(source_system="bank-test", source_transaction_id=reference)
    b["source"]["key"] = "raw/another.csv"
    first = score.process_job(a)
    assert score.process_job(a) == first
    assert score.process_job(b) == first
    assert query("SELECT count(*) FROM transactions WHERE source_system='bank-test' AND source_transaction_id=%s", (reference,)) == [(1,)]
    assert query("SELECT count(*) FROM risk_events WHERE tx_id=%s", (a["transaction_id"],)) == [(1,)]


def test_concurrent_different_uuids_same_reference_insert_once(pipeline):
    make, query, _, _, _, _ = pipeline
    reference = str(uuid.uuid4())
    messages = [make(source_system="bank-test", source_transaction_id=reference) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(score.persist_score, messages))
    assert len({r["transaction_id"] for r in results}) == 1
    assert query("SELECT count(*) FROM transactions WHERE source_transaction_id=%s", (reference,)) == [(1,)]


def test_reused_reference_changed_financial_data_is_conflict(pipeline):
    make, query, _, _, _, _ = pipeline
    reference = str(uuid.uuid4())
    a = make(source_system="bank-test", source_transaction_id=reference)
    b = make(source_system="bank-test", source_transaction_id=reference, amount="11.00")
    score.persist_score(a)
    with pytest.raises(IdentityConflict):
        score.persist_score(b)
    assert query("SELECT amount FROM transactions WHERE tx_id=%s", (a["transaction_id"],))[0][0] == 10
    assert query("SELECT count(*) FROM transactions WHERE tx_id=%s", (b["transaction_id"],)) == [(0,)]


def test_similar_distinct_references_one_second_apart_preserve_both_and_flag(pipeline):
    make, query, _, _, _, _ = pipeline
    a = make(source_system="bank-test", source_transaction_id=str(uuid.uuid4()),
             merchant="Shop", tx_date="2024-02-29T12:00:00.123456Z")
    b = make(source_system="bank-test", source_transaction_id=str(uuid.uuid4()),
             merchant="Shop", tx_date="2024-02-29T12:00:01.123456Z")
    first = score.persist_score(a)
    second = score.persist_score(b)
    assert not any(r["rule"] == "POSSIBLE_DUPLICATE_CHARGE" for r in first["triggered_rules"])
    duplicate = next(r for r in second["triggered_rules"] if r["rule"] == "POSSIBLE_DUPLICATE_CHARGE")
    assert duplicate["matching_transaction_ids"] == [a["transaction_id"]]
    stored = query("SELECT tx_date FROM transactions WHERE tx_id=ANY(%s::uuid[]) ORDER BY tx_date",
                   ([a["transaction_id"], b["transaction_id"]],))
    assert len(stored) == 2 and stored[0][0].microsecond == 123456
    assert (stored[1][0] - stored[0][0]).total_seconds() == 1


@pytest.mark.parametrize("changes", [{"currency": "USD"}, {"merchant": "Other shop"},
    {"tx_date": "2024-02-29T12:03:00Z"}, {"source_system": "other-bank"}, {"tx_type": "credit"}])
def test_duplicate_charge_comparison_requires_all_business_conditions(pipeline, changes):
    make, _, _, _, _, _ = pipeline
    a = make(source_system="bank-test", source_transaction_id=str(uuid.uuid4()), merchant="Shop")
    b = make(**{**dict(source_system="bank-test", source_transaction_id=str(uuid.uuid4()), merchant="Shop"), **changes})
    score.persist_score(a)
    result = score.persist_score(b)
    assert not any(r["rule"] == "POSSIBLE_DUPLICATE_CHARGE" for r in result["triggered_rules"])


def test_no_reference_similar_events_are_not_collapsed(pipeline):
    make, query, _, _, _, _ = pipeline
    a, b = make(), make(tx_date="2024-02-29T12:00:01Z")
    score.persist_score(a)
    score.persist_score(b)
    assert query("SELECT count(*) FROM transactions WHERE tx_id=ANY(%s::uuid[])",
                 ([a["transaction_id"], b["transaction_id"]],)) == [(2,)]


def test_sql_unique_source_reference_defends_nonpipeline_writers(pipeline):
    make, query, _, _, _, _ = pipeline
    reference = str(uuid.uuid4())
    a, b = [make(source_system="bank-test", source_transaction_id=reference) for _ in range(2)]
    score.persist_score(a)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        query("""INSERT INTO transactions(tx_id,account_id,amount,tx_date,tx_type,raw_file,source_system,source_transaction_id)
                 VALUES(%s,%s,10,NOW(),'debit','test','bank-test',%s)""", (b["transaction_id"], b["account_id"], reference))


def test_local_loader_upstream_replay_and_conflict_are_audited(pipeline):
    make, query, _, _, _, _ = pipeline
    a = make(source_system="bank-test", source_transaction_id=str(uuid.uuid4()))
    b = make(source_system="bank-test", source_transaction_id=a["source_transaction_id"])
    def text(j, amount="10.00"):
        return ("transaction_id,account_id,source_system,source_transaction_id,amount,tx_date,tx_type\n"
                f"{j['transaction_id']},{j['account_id']},bank-test,{j['source_transaction_id']},{amount},2024-02-29T12:00:00Z,debit\n")
    assert ingest.process_csv("fintrust-test-raw", "raw/first.csv", text(a))["rows_valid"] == 1
    replay = ingest.process_csv("fintrust-test-raw", "raw/second.csv", text(b))
    assert replay["rows_valid"] == 0 and replay["rows_duplicate"] == 1
    conflict = ingest.process_csv("fintrust-test-raw", "raw/third.csv", text(b, "11.00"))
    assert conflict["rows_valid"] == 0 and conflict["rows_quarantined"] == 1
    assert query("SELECT count(*) FROM transactions WHERE source_transaction_id=%s", (a["source_transaction_id"],)) == [(1,)]


def test_stream_replay_with_new_uuid_publishes_only_canonical_projection(pipeline, monkeypatch):
    from fintrust import dynamo
    make, _, s3, _, _, _ = pipeline
    monkeypatch.setenv("ALERT_DELIVERY_MODE", "stream")
    monkeypatch.setenv("QUARANTINE_BUCKET", "fintrust-test-raw")
    reference = str(uuid.uuid4())
    a, b = [make(source_system="bank-test", source_transaction_id=reference) for _ in range(2)]
    assert score.process_job(b) == score.process_job(a)
    # b arrived first, so its UUID is the canonical ledger/projection identity.
    table = dynamo.dynamodb.Table("risk_scores")
    items = table.scan()["Items"]
    assert len(items) == 1 and items[0]["score_date"] == "TX#" + b["transaction_id"]
    receipts = s3.list_objects_v2(Bucket="fintrust-test-raw", Prefix="quarantine/accounts/duplicates/")["Contents"]
    assert len(receipts) == 1


def test_historical_version_one_frozen_digest_remains_replayable(pipeline):
    make, query, _, _, _, _ = pipeline
    a = make()
    original = score.persist_score(a)
    query("UPDATE transactions SET transaction_fingerprint=NULL, country=NULL WHERE tx_id=%s", (a["transaction_id"],))
    assert score.persist_score(a) == original
    assert score.persist_score({**a, "source": {**a["source"], "key": "raw/renamed.csv"}}) == original


def test_schema_and_additive_migration_can_be_reapplied(prepared_database_url):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    with psycopg2.connect(prepared_database_url) as conn:
        with conn.cursor() as cur:
            cur.execute((root / "sql/migrations/001_transaction_identity.sql").read_text())
            cur.execute((root / "sql/schema.sql").read_text())
            cur.execute("SELECT count(*) FROM transactions WHERE source_transaction_id IS NULL")
            assert cur.fetchone()[0] >= 200

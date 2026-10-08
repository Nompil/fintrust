"""Real PostgreSQL transactions with mocked AWS boundaries; no cloud resources."""
import csv
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import psycopg2
import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from moto import mock_aws

from .test_constraints import prepared_database_url
from fintrust import alert, db, dynamo, ingest, jobs, report, score

ACCOUNT = "20000000-0000-4000-8000-000000000001"


@pytest.fixture
def pipeline(monkeypatch, prepared_database_url):
    connect = lambda: psycopg2.connect(prepared_database_url)
    for module in (ingest, score, alert, db):
        monkeypatch.setattr(module, "get_connection", connect)
    monkeypatch.setenv("DYNAMODB_TABLE", "risk_scores")
    monkeypatch.setenv("ALERT_FUNCTION_ARN", "fintrust-alert-dev")
    monkeypatch.setenv("SES_SENDER", "sender@example.com")
    monkeypatch.setenv("SES_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("S3_REPORT_BUCKET", "fintrust-test-reports")
    # Isolate the scoring contract from a developer's provisional configuration.
    for name in list(__import__('os').environ):
        if name.startswith("RISK_"):
            monkeypatch.delenv(name)
    identities = []
    def make(**changes):
        identity = str(uuid.uuid4())
        identities.append(identity)
        row = {"transaction_id": identity, "account_id": ACCOUNT, "amount": "10.00",
               "currency": "ZAR", "country": "ZA", "tx_date": "2024-02-29T12:00:00Z", "tx_type": "debit"}
        row.update(changes)
        return jobs.make_job(row, "fintrust-test-raw", "raw/input.csv", "version1", 2, "version1", "etag")
    def query(sql, params=()):
        connection = connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchall() if cursor.description else []
        finally:
            connection.close()
    with mock_aws():
        s3 = boto3.client("s3", region_name="af-south-1")
        for bucket in ("fintrust-test-raw", "fintrust-test-reports"):
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
        sqs = boto3.client("sqs", region_name="af-south-1")
        queue = sqs.create_queue(QueueName="transactions.fifo", Attributes={"FifoQueue": "true"})["QueueUrl"]
        monkeypatch.setenv("TRANSACTION_QUEUE_URL", queue)
        monkeypatch.setattr(ingest, "s3", s3)
        monkeypatch.setattr(ingest, "sqs", sqs)
        monkeypatch.setattr(report, "s3", s3)
        monkeypatch.setattr(score, "s3", s3)
        resource = boto3.resource("dynamodb", region_name="af-south-1")
        resource.create_table(TableName="risk_scores", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("account_id", "score_date")],
            KeySchema=[{"AttributeName": "account_id", "KeyType": "HASH"}, {"AttributeName": "score_date", "KeyType": "RANGE"}])
        monkeypatch.setattr(dynamo, "dynamodb", resource)
        mail = MagicMock(return_value={"MessageId": "ses-message"})
        monkeypatch.setattr(alert.ses, "send_email", mail)
        def invoke(**kw):
            assert kw["InvocationType"] == "RequestResponse"
            reply = alert.lambda_handler(json.loads(kw["Payload"]), None)
            return {"Payload": io.BytesIO(json.dumps(reply).encode())}
        monkeypatch.setattr(score.lambda_client, "invoke", invoke)
        try:
            yield make, query, s3, sqs, queue, mail
        finally:
            query("DELETE FROM alerts WHERE risk_event_id IN (SELECT risk_event_id FROM risk_events WHERE tx_id=ANY(%s::uuid[]))", (identities,))
            query("DELETE FROM processed_transactions WHERE tx_id=ANY(%s::uuid[])", (identities,))
            query("DELETE FROM risk_events WHERE tx_id=ANY(%s::uuid[])", (identities,))
            query("DELETE FROM transactions WHERE tx_id=ANY(%s::uuid[])", (identities,))


def test_full_csv_fifo_score_alert_projection_and_replay(pipeline):
    make, query, s3, sqs, queue, mail = pipeline
    high = make(amount="250001", country="US", tx_type="transfer")
    low = make(tx_date="2024-02-29T13:00:00Z")
    text = "transaction_id,account_id,amount,tx_date,tx_type,country,email\n"
    text += f"{high['transaction_id']},{ACCOUNT},250001,2024-02-29T12:00:00Z,transfer,US,private@example.com\n"
    text += f"{low['transaction_id']},{ACCOUNT},10,2024-02-29T13:00:00Z,debit,ZA,private@example.com\n"
    text += f"{uuid.uuid4()},{ACCOUNT},-1,2024-02-29,debit,ZA,private@example.com\n"
    s3.put_object(Bucket="fintrust-test-raw", Key="raw/input.csv", Body=text.encode())
    event = {"Records": [{"s3": {"bucket": {"name": "fintrust-test-raw"}, "object": {"key": "raw/input.csv"}}}]}
    counts = ingest.lambda_handler(event, None)
    assert counts["rows_valid"] == 2 and counts["rows_quarantined"] == 1
    replay = ingest.lambda_handler(event, None)
    assert replay["rows_valid"] == 0 and replay["reason_code"] == "DUPLICATE_FILE"
    messages = sqs.receive_message(QueueUrl=queue, MaxNumberOfMessages=10, MessageSystemAttributeNames=["All"])["Messages"]
    assert len(messages) == 2
    assert all(m["Attributes"]["MessageGroupId"] == ACCOUNT for m in messages)
    assert query("SELECT count(*) FROM transactions WHERE tx_id=%s", (high["transaction_id"],))[0][0] == 0
    quarantine = s3.list_objects_v2(Bucket="fintrust-test-raw", Prefix="quarantine/")["Contents"]
    rejected_key = next(item["Key"] for item in quarantine if item["Key"].endswith(".jsonl"))
    rejected = json.loads(s3.get_object(Bucket="fintrust-test-raw", Key=rejected_key)["Body"].read())
    assert rejected["source_row"] == 4 and rejected["source_etag"] and rejected["quarantined_at"]
    assert "email" not in rejected["record"]
    batch = {"Records": [{"messageId": m["MessageId"], "body": m["Body"]} for m in messages]}
    assert score.lambda_handler(batch, None) == {"batchItemFailures": []}
    assert score.lambda_handler(batch, None) == {"batchItemFailures": []}
    assert mail.call_count == 1
    assert query("SELECT count(*) FROM risk_events WHERE tx_id=%s", (high["transaction_id"],))[0][0] == 1
    record = dynamo.get_transaction_score("risk_scores", ACCOUNT, high["transaction_id"])
    assert record["risk_level"] == "High" and record["risk_score"] == 90
    delivery = query("SELECT delivery_state,sent_at,provider_message_id FROM alerts WHERE risk_event_id=%s", (record["risk_event_id"],))[0]
    assert delivery[0] == "SENT" and delivery[1] is not None and delivery[2] == "ses-message"
    assert dynamo.get_transaction_score("risk_scores", ACCOUNT, low["transaction_id"])["risk_level"] == "Low"


def test_duplicate_other_file_freezes_score_and_rejects_conflict(pipeline, monkeypatch):
    make, query, *_ = pipeline
    original = make()
    first = score.persist_score(original)
    monkeypatch.setenv("RISK_HIGH_AMOUNT", "1")
    second = score.persist_score({**original, "source": {**original["source"], "key": "raw/another.csv"}})
    assert first == second and first["score"] == 0
    with pytest.raises(ValueError, match="conflicts"):
        score.persist_score({**original, "amount": "11.00"})
    assert query("SELECT amount FROM transactions WHERE tx_id=%s", (original["transaction_id"],))[0][0] == 10


def test_dynamo_failure_then_retry_completes_without_duplicate_sql(pipeline, monkeypatch):
    make, query, *_ = pipeline
    payload = make()
    put = score.put_item
    monkeypatch.setattr(score, "put_item", MagicMock(side_effect=RuntimeError("DynamoDB offline")))
    with pytest.raises(RuntimeError):
        score.process_job(payload)
    assert query("SELECT count(*) FROM transactions WHERE tx_id=%s", (payload["transaction_id"],))[0][0] == 1
    monkeypatch.setattr(score, "put_item", put)
    score.process_job(payload)
    assert query("SELECT count(*) FROM risk_events WHERE tx_id=%s", (payload["transaction_id"],))[0][0] == 1
    assert dynamo.get_transaction_score("risk_scores", ACCOUNT, payload["transaction_id"])


def test_failed_scoring_rolls_back_ledger(pipeline, monkeypatch):
    make, query, *_ = pipeline
    payload = make()
    monkeypatch.setenv("RISK_VELOCITY_SECONDS", "0")
    with pytest.raises(ValueError):
        score.persist_score(payload)
    assert query("SELECT count(*) FROM transactions WHERE tx_id=%s", (payload["transaction_id"],))[0][0] == 0
    assert query("SELECT count(*) FROM processed_transactions WHERE tx_id=%s", (payload["transaction_id"],))[0][0] == 0


def test_velocity_counts_current_and_inclusive_window_not_future(pipeline):
    make, _, *_ = pipeline
    # Three inside, one at the lower bound, one just outside, one in the future.
    for when in ["11:55:00", "11:54:59", "11:59:00", "11:59:01", "11:59:02", "12:00:01"]:
        score.persist_score(make(tx_date=f"2024-02-29T{when}Z"))
    at_limit = score.persist_score(make())
    assert "HIGH_VELOCITY" not in {r["rule"] for r in at_limit["triggered_rules"]}
    above = score.persist_score(make())
    assert "HIGH_VELOCITY" in {r["rule"] for r in above["triggered_rules"]}


def test_ses_rejection_is_retryable_and_never_marked_sent(pipeline):
    make, query, _, _, _, mail = pipeline
    payload = make(amount="250001", country="US")
    mail.side_effect = ClientError({"Error": {"Code": "MessageRejected"}, "ResponseMetadata": {"HTTPStatusCode": 400}}, "SendEmail")
    with pytest.raises(ClientError):
        score.process_job(payload)
    assert query("SELECT delivery_state,sent_at FROM alerts WHERE risk_event_id=(SELECT (result->>'risk_event_id')::bigint FROM processed_transactions WHERE tx_id=%s)", (payload["transaction_id"],))[0] == ("FAILED", None)
    mail.side_effect = None
    score.process_job(payload)
    score.process_job(payload)
    assert mail.call_count == 2


def test_uncertain_ses_response_blocks_duplicate_delivery(pipeline):
    make, query, _, _, _, mail = pipeline
    payload = make(amount="250001", country="US")
    mail.side_effect = ReadTimeoutError(endpoint_url="https://email.example")
    with pytest.raises(ReadTimeoutError):
        score.process_job(payload)
    mail.side_effect = None
    with pytest.raises(RuntimeError, match="reconciliation"):
        score.process_job(payload)
    assert mail.call_count == 1
    assert query("SELECT delivery_state,sent_at FROM alerts WHERE risk_event_id=(SELECT (result->>'risk_event_id')::bigint FROM processed_transactions WHERE tx_id=%s)", (payload["transaction_id"],))[0] == ("UNKNOWN", None)


def test_report_uses_prior_history_separate_currencies_and_utc_boundaries(pipeline):
    make, _, s3, *_ = pipeline
    for amount, currency, when, kind in [("100", "ZAR", "2024-01-31T23:59:59Z", "credit"),
        ("25", "ZAR", "2024-02-01T02:00:00+02:00", "debit"),
        ("9", "USD", "2024-02-29T23:59:59Z", "credit"),
        ("1", "USD", "2024-03-01T00:00:00Z", "credit")]:
        score.persist_score(make(amount=amount, currency=currency, tx_date=when, tx_type=kind))
    result = report.generate_monthly_report("2024-02")
    payload = json.loads(s3.get_object(Bucket=result["bucket"], Key=result["keys"][1])["Body"].read())
    assert payload["count"] == 2
    assert {(r["currency"], r["running_balance"]) for r in payload["transactions"]} == {("ZAR", "75.00"), ("USD", "9.00")}
    csv_text = s3.get_object(Bucket=result["bucket"], Key=result["keys"][0])["Body"].read().decode()
    assert len(list(csv.DictReader(io.StringIO(csv_text)))) == 2
    assert payload["start_inclusive"] == "2024-02-01T00:00:00+00:00"


def test_unknown_account_quarantine_and_publish_failure_retry(pipeline, monkeypatch):
    make, query, s3, sqs, queue, _ = pipeline
    payload = make()
    unknown = str(uuid.uuid4())
    text = ("transaction_id,account_id,amount,tx_date,tx_type\n"
            f"{payload['transaction_id']},{ACCOUNT},10,2024-02-29,debit\n"
            f"{uuid.uuid4()},{unknown},10,2024-02-29,debit\n")
    send = sqs.send_message_batch
    monkeypatch.setattr(sqs, "send_message_batch", MagicMock(side_effect=RuntimeError("SQS unavailable")))
    with pytest.raises(RuntimeError):
        ingest.process_csv("fintrust-test-raw", "raw/input.csv", text, queue_url=queue)
    assert query("SELECT count(*) FROM transactions WHERE tx_id=%s", (payload["transaction_id"],))[0][0] == 0
    monkeypatch.setattr(sqs, "send_message_batch", send)
    result = ingest.process_csv("fintrust-test-raw", "raw/input.csv", text, queue_url=queue)
    assert result["rows_valid"] == 1 and result["rows_quarantined"] == 1
    assert len(sqs.receive_message(QueueUrl=queue, MaxNumberOfMessages=10)["Messages"]) == 1


def test_concurrent_duplicates_produce_one_ledger_event(pipeline):
    make, query, *_ = pipeline
    payload = make()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(score.persist_score, [payload] * 4))
    assert all(result == results[0] for result in results)
    assert query("SELECT count(*) FROM risk_events WHERE tx_id=%s", (payload["transaction_id"],))[0][0] == 1


def test_ses_success_followed_by_sql_failure_never_blindly_resends(pipeline, monkeypatch):
    make, _, _, _, _, mail = pipeline
    payload = make(amount="250001", country="US")
    update = alert._update
    monkeypatch.setattr(alert, "_update", MagicMock(side_effect=psycopg2.OperationalError("database unavailable")))
    with pytest.raises(psycopg2.OperationalError):
        score.process_job(payload)
    monkeypatch.setattr(alert, "_update", update)
    with pytest.raises(RuntimeError, match="reconciliation"):
        score.process_job(payload)
    assert mail.call_count == 1


def test_database_roles_can_execute_pipeline_without_owner_privileges(pipeline, prepared_database_url, monkeypatch):
    make, _, _, _, queue, _ = pipeline
    payload = make(amount="250001", country="US")
    connection = psycopg2.connect(prepared_database_url)
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
        can_manage_roles = cursor.fetchone()[0]
    if not can_manage_roles:
        connection.close()
        pytest.skip("Service-role execution check requires a disposable test database administrator")
    class ScopedConnection:
        # Keep schema grants and test data in one rollback-only transaction.
        def cursor(self): return connection.cursor()
        def commit(self): pass
        def close(self): pass
        def rollback(self): connection.rollback()
    for module in (ingest, score, alert, db):
        monkeypatch.setattr(module, "get_connection", ScopedConnection)
    try:
        with connection.cursor() as cur:
            permissions = Path("infrastructure/rds/permissions.sql").read_text()
            cur.execute(permissions.replace("BEGIN;", "").replace("COMMIT;", ""))
            cur.execute("SET LOCAL ROLE fintrust_ingest")
            cur.execute("SELECT has_table_privilege(current_user,'transactions','INSERT')")
            assert cur.fetchone() == (False,)
            assert ingest.process_csv("fintrust-test-raw", "raw/roles.csv",
                f"account_id,amount,tx_date,tx_type\n{ACCOUNT},10,2024-02-29,debit\n",
                queue_url=queue)["rows_valid"] == 1
            cur.execute("RESET ROLE")
            cur.execute("SET LOCAL ROLE fintrust_scoring")
            result = score.persist_score(payload)
            cur.execute("RESET ROLE")
            cur.execute("SET LOCAL ROLE fintrust_alert")
            assert alert.send_alert(jobs.high_risk_event(result))["status"] == "SENT"
            cur.execute("RESET ROLE")
            cur.execute("SET LOCAL ROLE fintrust_report")
            assert report.generate_monthly_report("2024-02")["rows"] == 1
            cur.execute("RESET ROLE")
            cur.execute("SET LOCAL ROLE fintrust_api")
            cur.execute("SELECT tx_id FROM transactions WHERE tx_id=%s", (payload["transaction_id"],))
            assert str(cur.fetchone()[0]) == payload["transaction_id"]
    finally:
        connection.rollback()
        connection.close()

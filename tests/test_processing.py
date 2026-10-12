"""Contract and failure checks that do not need PostgreSQL or live AWS."""
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import boto3
import psycopg2
import pytest
from moto import mock_aws

from fintrust import alert, api, config, db, dynamo, ingest, jobs, query, report, rules, score
from infrastructure.iam.create_roles import build_policies
from infrastructure.processing import build_template

ACCOUNT = "20000000-0000-4000-8000-000000000001"
TX = "30000000-0000-4000-8000-000000000001"


def row(**changes):
    return {**dict(transaction_id=TX, account_id=ACCOUNT, amount="10.00", currency="ZAR",
                  tx_date="2024-02-29T12:00:00+02:00", tx_type="debit", country="ZA"), **changes}


def job():
    return jobs.make_job(row(), "raw-bucket", "raw/a.csv", "v1", 2, "v1", "etag")


def test_canonical_identity_across_uploads_and_conflicts():
    first = job()
    other = jobs.make_job(row(), "raw-bucket", "raw/b.csv", "v2", 17, "v2")
    assert first["transaction_id"] == TX == other["transaction_id"]
    assert first["transaction_timestamp"] == "2024-02-29T10:00:00+00:00"
    assert jobs.parse_job(json.dumps(first)) == first
    assert jobs.business_fingerprint(first) == jobs.business_fingerprint(other)
    assert jobs.business_fingerprint(first) != jobs.business_fingerprint({**first, "amount": "11.00"})
    legacy = row()
    del legacy["transaction_id"]
    assert jobs.transaction_id(legacy, "a:v1", 2) == jobs.transaction_id(legacy, "a:v1", 2)
    assert jobs.transaction_id(legacy, "a:v1", 2) != jobs.transaction_id(legacy, "a:v2", 2)


@pytest.mark.parametrize("value", ["", "not-a-uuid", "TXN-001"])
def test_supplied_invalid_identity_is_never_replaced(value):
    with pytest.raises(ValueError, match="UUID"):
        jobs.make_job({**row(), "transaction_id": value}, "bucket", "raw/a.csv", "v1", 2)


@pytest.mark.parametrize("field,value", [("schema_version", 2), ("amount", 1.1),
                                         ("correlation_id", "bad"), ("source", {})])
def test_reject_malformed_queue_contract(field, value):
    with pytest.raises((ValueError, KeyError)):
        jobs.parse_job({**job(), field: value})


@pytest.mark.parametrize("threshold,rule", [("high_amount", "HIGH_AMOUNT"), ("very_high_amount", "VERY_HIGH_AMOUNT")])
@pytest.mark.parametrize("delta,present", [("-0.01", False), ("0", False), ("0.01", True)])
def test_amount_boundaries(threshold, rule, delta, present):
    cfg = rules.ScoringConfig(high_amount=Decimal("100"), very_high_amount=Decimal("200"))
    result = rules.evaluate({"amount": str(getattr(cfg, threshold) + Decimal(delta))}, config=cfg)
    assert (rule in {r["rule"] for r in result["triggered_rules"]}) is present


@pytest.mark.parametrize("value,expected", [(39, "Low"), (40, "Medium"), (41, "Medium"),
                                            (69, "Medium"), (70, "High"), (71, "High")])
def test_classification_boundaries(value, expected):
    assert rules.classify_risk(value, rules.ScoringConfig()) == expected


@pytest.mark.parametrize("count,expected", [(4, False), (5, False), (6, True)])
def test_velocity_boundaries(count, expected):
    result = rules.evaluate({"amount": "1"}, count, rules.ScoringConfig())
    assert ("HIGH_VELOCITY" in {r["rule"] for r in result["triggered_rules"]}) is expected


def test_multiple_rules_and_configurable_classification(monkeypatch):
    monkeypatch.setenv("RISK_HIGH", "80")
    cfg = rules.ScoringConfig.from_env()
    result = rules.evaluate({"amount": "200001", "country": "US", "transaction_type": "transfer",
                             "merchant": "HighRisk Shop"}, 6, cfg)
    assert result["score"] == 100 and result["risk_level"] == "High"
    assert len(result["triggered_rules"]) == 6
    assert all(set(r) == {"rule", "points", "reason", "triggered_value", "threshold", "context"} for r in result["triggered_rules"])
    assert rules.classify_risk(79, cfg) == "Medium"


@pytest.mark.parametrize("changes", [{"velocity_count": 0}, {"high": 40}, {"cross_border_points": -1},
                                      {"high_amount": Decimal("NaN")}])
def test_invalid_rule_configuration(changes):
    with pytest.raises(ValueError):
        rules.ScoringConfig(**changes)


def test_fifo_stops_at_failure_and_returns_unprocessed_ids(monkeypatch):
    processed = []
    def process(body):
        processed.append(body)
        if body == "bad":
            raise RuntimeError("dependency unavailable")
    monkeypatch.setattr(score, "process_job", process)
    messages = [{"messageId": str(i), "body": body} for i, body in enumerate(["ok", "bad", "later"])]
    assert score.lambda_handler({"Records": messages}, None) == {
        "batchItemFailures": [{"itemIdentifier": "1"}, {"itemIdentifier": "2"}]}
    assert processed == ["ok", "bad"]


@pytest.mark.parametrize("module,operation", [
    (score, lambda: score.persist_score(job())),
    (alert, lambda: alert.send_alert(jobs.high_risk_event({**job(), "score": 75, "risk_level": "High"}))),
    (alert, lambda: alert._update(1, "FAILED")),
    (ingest, lambda: ingest.process_csv("bucket", "raw/a.csv",
        f"account_id,amount,tx_date,tx_type\n{ACCOUNT},1,2024-01-01,debit\n", queue_url="jobs.fifo")),
    (db, lambda: db.run_query("SELECT 1"))])
def test_database_errors_rollback_and_close(monkeypatch, module, operation):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.execute.side_effect = psycopg2.OperationalError("offline")
    monkeypatch.setattr(module, "get_connection", lambda: conn)
    monkeypatch.setenv("SES_SENDER", "sender@example.com")
    monkeypatch.setenv("SES_RECIPIENT", "recipient@example.com")
    with pytest.raises(psycopg2.OperationalError):
        operation()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()
    conn.commit.assert_not_called()


def test_dynamo_reads_all_pages(monkeypatch):
    table = MagicMock()
    table.query.side_effect = [{"Items": [{"n": 1}], "LastEvaluatedKey": {"account_id": ACCOUNT}},
                               {"Items": [{"n": 2}]}]
    monkeypatch.setattr(dynamo.dynamodb, "Table", lambda _: table)
    assert dynamo.query_by_account("scores", ACCOUNT) == [{"n": 1}, {"n": 2}]
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == {"account_id": ACCOUNT}


@pytest.mark.parametrize("month,days", [("2024-02", 29), ("2023-02", 28), ("2024-12", 31)])
def test_month_boundaries(month, days):
    start, end = report.month_bounds(month)
    assert (end - start).days == days and start.tzinfo == timezone.utc
    assert report.month_bounds(now=datetime(2025, 1, 1, tzinfo=timezone.utc))[0].month == 12


def test_report_empty_month_and_upload_retry(monkeypatch):
    monkeypatch.setattr(report, "run_query", lambda *args: [])
    monkeypatch.setenv("S3_REPORT_BUCKET", "reports")
    writes = []
    def put(**kw):
        writes.append(kw)
        if len(writes) == 2:
            raise RuntimeError("S3 unavailable")
    monkeypatch.setattr(report.s3, "put_object", put)
    event = {"time": "2025-01-01T02:00:00Z"}
    with pytest.raises(RuntimeError):
        report.lambda_handler(event, None)
    result = report.lambda_handler(event, None)
    assert result["month"] == "2024-12" and result["rows"] == 0
    assert writes[0]["Key"] == writes[2]["Key"]
    assert json.loads(writes[-1]["Body"])["transactions"] == []
    assert writes[-2]["Body"].decode().splitlines() == ["account_id,currency,tx_date,tx_id,signed_amount,running_balance"]


def test_service_configuration_uses_only_three_canonical_parameters(monkeypatch):
    config.load_settings.cache_clear()
    for name in ("DB_HOST", "DB_USER", "DB_NAME", "DB_PASSWORD", "SSM_DB_PREFIX", "FINTRUST_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_EXECUTION_ENV", "AWS_Lambda_python3.12")
    monkeypatch.setenv("DB_AUTH_MODE", "iam")
    monkeypatch.setenv("FINTRUST_SERVICE", "scoring")
    monkeypatch.setenv("FINTRUST_STAGE", "dev")
    calls = []
    def parameter(**kw):
        calls.append(kw["Name"])
        return {"Parameter": {"Value": "value"}}
    monkeypatch.setattr(config.ssm, "get_parameter", parameter)
    try:
        settings = config.load_settings()
        assert settings["db_password"] is None
        assert set(calls) == {f"/fintrust/dev/scoring/db_{n}" for n in ("host", "name", "user")}
    finally:
        config.load_settings.cache_clear()


def test_iam_database_connection_verifies_certificate(monkeypatch):
    monkeypatch.setattr(db, "load_settings", lambda: dict(db_password=None, db_auth_mode="iam",
        db_host="database.example", db_port=5432, db_name="fintrust", db_user="fintrust_scoring_dev"))
    monkeypatch.setenv("DB_SSLROOTCERT", "/cert.pem")
    token = MagicMock(return_value="temporary-token")
    connect = MagicMock()
    monkeypatch.setattr(db.rds, "generate_db_auth_token", token)
    monkeypatch.setattr(db.psycopg2, "connect", connect)
    db.get_connection()
    assert connect.call_args.kwargs["sslmode"] == "verify-full"
    assert connect.call_args.kwargs["password"] == "temporary-token"
    assert token.call_args.kwargs["DBUsername"] == "fintrust_scoring_dev"


def test_infrastructure_failure_contract_and_role_separation():
    resources = build_template()["Resources"]
    queue = resources["Transactions"]["Properties"]
    mapping = resources["ScoringMapping"]["Properties"]
    assert queue["FifoQueue"] and resources["TransactionDLQ"]["Properties"]["FifoQueue"]
    assert queue["VisibilityTimeout"] >= 6 * resources["ScoringFunction"]["Properties"]["Timeout"]
    assert queue["RedrivePolicy"]["maxReceiveCount"] == 5
    assert mapping["FunctionResponseTypes"] == ["ReportBatchItemFailures"] and mapping["BatchSize"] <= 10
    assert "DestinationConfig" in resources["ReportAsync"]["Properties"]
    assert "DeadLetterConfig" in resources["MonthlySchedule"]["Properties"]["Targets"][0]
    policies = build_policies("123456789012", "af-south-1", "dev", "raw-bucket", "scores", "db-example",
                             "sender@example.com", reports_bucket="reports-bucket", recipient="recipient@example.com")
    assert set(policies) == {"ingest", "scoring", "alert", "api", "report"}
    for service, policy in policies.items():
        allows = [s for s in policy["Statement"] if s["Effect"] == "Allow"]
        assert all('*' not in action for s in allows for action in s["Action"])
        assert any("ses:SendEmail" in s["Action"] for s in allows) == (service == "alert")
        assert all(all(a.startswith("ec2:") for a in s["Action"]) for s in allows if s["Resource"] == "*")


@mock_aws
def test_fifo_exhausted_retries_move_to_dlq():
    sqs = boto3.client("sqs", region_name="af-south-1")
    dlq = sqs.create_queue(QueueName="dead.fifo", Attributes={"FifoQueue": "true"})["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    queue = sqs.create_queue(QueueName="jobs.fifo", Attributes={"FifoQueue": "true", "VisibilityTimeout": "0",
        "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": 5})})["QueueUrl"]
    sqs.send_message(QueueUrl=queue, MessageBody="bad-job", MessageGroupId=ACCOUNT, MessageDeduplicationId=TX)
    for _ in range(5):
        assert sqs.receive_message(QueueUrl=queue).get("Messages")
    assert not sqs.receive_message(QueueUrl=queue).get("Messages")
    assert sqs.receive_message(QueueUrl=dlq)["Messages"][0]["Body"] == "bad-job"


def test_transaction_insights_access_pattern_and_route(monkeypatch):
    get = MagicMock(return_value={"transaction_id": TX, "risk_level": "High"})
    monkeypatch.setattr(query, "get_item", get)
    response = api.app.test_client().get(f"/v1/insights?account_id={ACCOUNT}&transaction_id={TX}")
    assert response.status_code == 200 and response.json["data"]["transaction_id"] == TX
    assert get.call_args.args[1] == {"account_id": ACCOUNT, "score_date": "TX#" + TX}
    for extra in ("transaction_id=bad", f"transaction_id={TX}&date=2024-02-29", "transaction_id="):
        assert api.app.test_client().get(f"/v1/insights?account_id={ACCOUNT}&{extra}").status_code == 400


def test_alert_function_failure_is_not_acknowledged(monkeypatch):
    monkeypatch.setattr(score, "persist_score", lambda _: {**job(), "risk_level": "High", "score": 75})
    monkeypatch.setattr(score, "put_item", lambda *args: None)
    monkeypatch.setenv("DYNAMODB_TABLE", "scores")
    monkeypatch.setenv("ALERT_FUNCTION_ARN", "alert-function")
    monkeypatch.setattr(score.lambda_client, "invoke", lambda **kw: {
        "FunctionError": "Unhandled", "Payload": io.BytesIO(b'{"errorMessage":"failed"}')})
    assert score.lambda_handler({"Records": [{"messageId": "retry", "body": json.dumps(job())}]}, None) == {
        "batchItemFailures": [{"itemIdentifier": "retry"}]}


def test_partial_fifo_publish_failure_is_not_success(monkeypatch):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [(ACCOUNT,)]
    monkeypatch.setattr(ingest, "get_connection", lambda: conn)
    monkeypatch.setattr(ingest.sqs, "send_message_batch", lambda **kw: {
        "Successful": [], "Failed": [{"Id": "0", "Code": "ServiceUnavailable"}]})
    with pytest.raises(RuntimeError, match="publish batch"):
        ingest.process_csv("bucket", "raw/a.csv",
            f"account_id,amount,tx_date,tx_type\n{ACCOUNT},10,2024-02-29,debit\n", queue_url="jobs.fifo")


def test_unversioned_object_replacement_changes_legacy_identity(monkeypatch):
    sources = []
    monkeypatch.setenv("TRANSACTION_QUEUE_URL", "jobs.fifo")
    monkeypatch.setattr(ingest, "process_csv", lambda *args, **kw: sources.append(args[3]) or {})
    for etag in ('"a"', '"a"', '"b"'):
        monkeypatch.setattr(ingest.s3, "get_object", lambda **kw: {"Body": io.BytesIO(b"data"), "ETag": etag})
        ingest.lambda_handler({"Records": [{"s3": {"bucket": {"name": "bucket"}, "object": {"key": "raw/a.csv"}}}]}, None)
    assert sources[0] == sources[1] and sources[0] != sources[2]


@pytest.fixture(autouse=True)
def authenticated_test_caller(monkeypatch):
    from fintrust import auth
    accounts=tuple("20000000-0000-4000-8000-00000000000"+str(i) for i in range(1,6))
    monkeypatch.setattr(auth,"authenticate",lambda:auth.Principal("test-admin","Admin",accounts))

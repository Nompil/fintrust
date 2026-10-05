"""Offline production-path retry and security boundary checks."""
import io
import json
from unittest.mock import MagicMock

import boto3
import psycopg2
import pytest
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError, ReadTimeoutError
from moto import mock_aws

from fintrust import alert_delivery, config, dynamo, ingest, jobs, score
from infrastructure.foundation import build_template as foundation
from infrastructure.processing import build_template as processing
from infrastructure.iam.create_roles import build_policies

ACCOUNT = "20000000-0000-4000-8000-000000000001"
TX = "30000000-0000-4000-8000-000000000001"


def job():
    return jobs.make_job(dict(transaction_id=TX, account_id=ACCOUNT, amount="250001",
        tx_date="2024-02-29", tx_type="transfer", country="US", merchant="private merchant"),
        "raw-bucket", "raw/input.csv", "v1", 2, "v1", "etag")


@pytest.fixture
def delivery(monkeypatch):
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="af-south-1")
        table = resource.create_table(TableName="scores", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in ("account_id", "score_date")],
            KeySchema=[{"AttributeName": "account_id", "KeyType": "HASH"}, {"AttributeName": "score_date", "KeyType": "RANGE"}])
        monkeypatch.setattr(dynamo, "dynamodb", resource)
        monkeypatch.setattr(alert_delivery, "dynamodb", resource)
        monkeypatch.setenv("DYNAMODB_TABLE", "scores")
        monkeypatch.setenv("ALERT_DELIVERY_MODE", "stream")
        monkeypatch.setenv("SES_SENDER", "sender@example.com")
        monkeypatch.setenv("SES_RECIPIENT", "recipient@example.com")
        mail = MagicMock(return_value={"MessageId": "ses-id"})
        monkeypatch.setattr(alert_delivery.ses, "send_email", mail)
        result = {"account_id": ACCOUNT, "transaction_id": TX, "score_date": "TX#" + TX,
                  "risk_level": "High", "score": 75, "risk_event_id": 1}
        dynamo.publish_score("scores", result)
        yield table, mail, result


def state(table):
    return table.get_item(Key={"account_id": ACCOUNT, "score_date": "ALERT#" + TX}, ConsistentRead=True).get("Item", {})


def test_projection_is_immutable(delivery):
    table, _, item = delivery
    dynamo.publish_score("scores", item)
    with pytest.raises(ValueError, match="conflicts"):
        dynamo.publish_score("scores", {**item, "score": 99})
    assert table.get_item(Key={"account_id": ACCOUNT, "score_date": "TX#" + TX})["Item"] == item


def test_delivery_replay_and_concurrent_claim(delivery):
    table, mail, _ = delivery
    def send_with_contenders(**kwargs):
        # Moto is not thread-safe. Interleave contenders at the external send
        # boundary, after the winner's atomic claim and before its completion.
        claimed = state(table)
        assert claimed["delivery_state"] == "SENDING"
        for _ in range(3):
            with pytest.raises(RuntimeError, match="reconciliation") as rejected:
                alert_delivery.deliver(ACCOUNT, TX)
            assert isinstance(rejected.value.__cause__, ClientError)
            assert rejected.value.__cause__.response["Error"]["Code"] == "ConditionalCheckFailedException"
            assert state(table) == claimed
        return {"MessageId": "ses-id"}

    mail.side_effect = send_with_contenders
    assert alert_delivery.deliver(ACCOUNT, TX)["status"] == "SENT"
    assert alert_delivery.deliver(ACCOUNT, TX)["status"] == "SENT"
    assert state(table)["delivery_state"] == "SENT"
    assert state(table)["provider_message_id"] == "ses-id"
    mail.assert_called_once()


def test_completion_rejects_changed_claim_owner(delivery):
    table, mail, _ = delivery
    def change_owner(**kwargs):
        table.update_item(Key={"account_id": ACCOUNT, "score_date": "ALERT#" + TX},
            UpdateExpression="SET attempt_id=:attempt",
            ExpressionAttributeValues={":attempt": "another-attempt"})
        return {"MessageId": "ses-id"}

    mail.side_effect = change_owner
    with pytest.raises(ClientError) as rejected:
        alert_delivery.deliver(ACCOUNT, TX)
    assert rejected.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
    assert state(table)["attempt_id"] == "another-attempt"
    assert state(table)["delivery_state"] == "SENDING"
    with pytest.raises(RuntimeError, match="reconciliation"):
        alert_delivery.deliver(ACCOUNT, TX)
    mail.assert_called_once()


@pytest.mark.parametrize("http_status,expected,retry", [(400, "FAILED", True), (503, "UNKNOWN", False)])
def test_ses_failure_states(delivery, http_status, expected, retry):
    table, mail, _ = delivery
    mail.side_effect = ClientError({"Error": {"Code": "Rejected"},
        "ResponseMetadata": {"HTTPStatusCode": http_status}}, "SendEmail")
    with pytest.raises(ClientError):
        alert_delivery.deliver(ACCOUNT, TX)
    assert state(table)["delivery_state"] == expected
    mail.side_effect = None
    if retry:
        alert_delivery.deliver(ACCOUNT, TX)
        assert mail.call_count == 2
    else:
        with pytest.raises(RuntimeError, match="reconciliation"):
            alert_delivery.deliver(ACCOUNT, TX)
        assert mail.call_count == 1


def test_timeout_never_resends(delivery):
    table, mail, _ = delivery
    mail.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid")
    with pytest.raises(ReadTimeoutError):
        alert_delivery.deliver(ACCOUNT, TX)
    assert state(table)["delivery_state"] == "UNKNOWN"
    with pytest.raises(RuntimeError):
        alert_delivery.deliver(ACCOUNT, TX)
    assert mail.call_count == 1


def test_post_send_state_write_failure_keeps_claim(delivery, monkeypatch):
    table, mail, _ = delivery
    original = table.update_item
    def update(**kwargs):
        if ":message" in kwargs["ExpressionAttributeValues"]:
            raise RuntimeError("DynamoDB unavailable")
        return original(**kwargs)
    monkeypatch.setattr(table, "update_item", update)
    monkeypatch.setattr(alert_delivery.dynamodb, "Table", lambda _: table)
    with pytest.raises(RuntimeError):
        alert_delivery.deliver(ACCOUNT, TX)
    assert state(table)["delivery_state"] == "SENDING"
    with pytest.raises(RuntimeError, match="reconciliation"):
        alert_delivery.deliver(ACCOUNT, TX)
    mail.assert_called_once()


def test_stream_ignores_delivery_items_and_checkpoints_first_failure(delivery, monkeypatch):
    _, mail, item = delivery
    serializer = TypeSerializer()
    def record(number, value):
        return {"eventName": "INSERT", "dynamodb": {"SequenceNumber": str(number),
            "NewImage": {k: serializer.serialize(v) for k, v in value.items()}}}
    event = {"Records": [record(1, {"score_date": "ALERT#" + TX}), record(2, item), record(3, item)]}
    mail.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid")
    assert alert_delivery.lambda_handler(event, None) == {"batchItemFailures": [{"itemIdentifier": "2"}]}
    mail.assert_called_once()


def test_stream_rechecks_projection_before_send(delivery):
    table, mail, _ = delivery
    table.delete_item(Key={"account_id": ACCOUNT, "score_date": "TX#" + TX})
    with pytest.raises(ValueError):
        alert_delivery.deliver(ACCOUNT, TX)
    assert not state(table)
    mail.assert_not_called()


def test_ingest_handler_does_not_open_database(monkeypatch):
    connect = MagicMock(side_effect=AssertionError("ingest must not connect"))
    monkeypatch.setattr(ingest, "get_connection", connect)
    monkeypatch.setenv("TRANSACTION_QUEUE_URL", "jobs.fifo")
    csv = f"account_id,amount,tx_date,tx_type\n{ACCOUNT},1,2024-02-29,debit\n"
    monkeypatch.setattr(ingest.s3, "get_object", lambda **kw: {"Body": io.BytesIO(csv.encode())})
    monkeypatch.setattr(ingest.sqs, "send_message_batch", lambda **kw: {"Successful": [{"Id": "0"}]})
    result = ingest.lambda_handler({"Records": [{"s3": {"bucket": {"name": "raw-bucket"},
        "object": {"key": "raw/input.csv"}}}]}, None)
    assert result["rows_valid"] == 1
    connect.assert_not_called()


def test_unknown_account_requires_durable_sanitized_quarantine(monkeypatch):
    monkeypatch.setenv("ALERT_DELIVERY_MODE", "stream")
    monkeypatch.setenv("QUARANTINE_BUCKET", "rejected-bucket")
    persist = MagicMock(side_effect=score.UnknownAccount("missing"))
    monkeypatch.setattr(score, "persist_score", persist)
    write = MagicMock(side_effect=RuntimeError("S3 offline"))
    monkeypatch.setattr(score.s3, "put_object", write)
    with pytest.raises(RuntimeError):
        score.process_job(job())
    write.side_effect = None
    assert score.process_job(job())["status"] == "QUARANTINED"
    saved = json.loads(write.call_args.kwargs["Body"])
    assert "merchant" not in saved and saved["source"]["version"] == "v1"
    assert write.call_args.kwargs["Bucket"] == "rejected-bucket"
    persist.side_effect = psycopg2.OperationalError("database offline")
    with pytest.raises(psycopg2.OperationalError):
        score.process_job(job())
    assert write.call_count == 2


def test_stream_scoring_never_invokes_lambda(delivery, monkeypatch):
    _, _, result = delivery
    monkeypatch.setattr(score, "persist_score", lambda _: result)
    invoke = MagicMock(side_effect=AssertionError("private Lambda API call"))
    monkeypatch.setattr(score.lambda_client, "invoke", invoke)
    # Use a fresh projection because process_job also records risk_score.
    dynamo.dynamodb.Table("scores").delete_item(Key={"account_id": ACCOUNT, "score_date": "TX#" + TX})
    score.process_job(job())
    score.process_job(job())
    invoke.assert_not_called()


def test_environment_database_settings_never_fall_back_to_ssm(monkeypatch):
    config.load_settings.cache_clear()
    monkeypatch.setenv("DB_CONFIG_SOURCE", "environment")
    monkeypatch.setenv("DB_AUTH_MODE", "iam")
    monkeypatch.setenv("FINTRUST_SERVICE", "scoring")
    monkeypatch.setenv("FINTRUST_STAGE", "dev")
    monkeypatch.delenv("DB_HOST", raising=False)
    get = MagicMock(side_effect=AssertionError("runtime SSM call"))
    monkeypatch.setattr(config.ssm, "get_parameter", get)
    try:
        with pytest.raises(RuntimeError, match="deployment-resolved"):
            config.load_settings()
        monkeypatch.setenv("DB_HOST", "db.example")
        monkeypatch.setenv("DB_NAME", "fintrust")
        monkeypatch.setenv("DB_USER", "fintrust_scoring_dev")
        assert config.load_settings()["db_user"] == "fintrust_scoring_dev"
        get.assert_not_called()
    finally:
        config.load_settings.cache_clear()


def test_no_nat_or_interface_endpoints_and_private_service_placement():
    template = foundation()
    resources = template["Resources"]
    types = {r["Type"] for r in resources.values()}
    assert not types & {"AWS::EC2::NatGateway", "AWS::EC2::InternetGateway", "AWS::EC2::NetworkAcl"}
    endpoints = [r["Properties"] for r in resources.values() if r["Type"] == "AWS::EC2::VPCEndpoint"]
    assert len(endpoints) == 2 and all(e["VpcEndpointType"] == "Gateway" for e in endpoints)
    assert resources["DatabaseIngress"]["Properties"]["SourceSecurityGroupId"] == {"Ref": "LambdaGroup"}
    deployment = processing()
    assert deployment["Parameters"]["EnableConsumers"]["Default"] == "false"
    for name in ("Ingest", "Alert", "Scoring", "Api", "Report"):
        function = deployment["Resources"][name + "Function"]["Properties"]
        assert ("VpcConfig" in function) == (name in {"Scoring", "Api", "Report"})
    assert deployment["Resources"]["AlertMapping"]["Properties"]["DestinationConfig"]


def test_storage_retains_data_and_uses_one_key():
    resources = foundation()["Resources"]
    assert sum(r["Type"] == "AWS::KMS::Key" for r in resources.values()) == 1
    for label in ("Raw", "Quarantine", "Reports"):
        bucket = resources[label + "Bucket"]
        props = bucket["Properties"]
        assert bucket["DeletionPolicy"] == "Retain"
        assert all(props["PublicAccessBlockConfiguration"].values())
        assert props["VersioningConfiguration"]["Status"] == "Enabled"
        assert props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
        assert all("ExpirationInDays" not in rule for rule in props["LifecycleConfiguration"]["Rules"])
        policies = resources[label + "BucketPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        by_id = {statement["Sid"]: statement for statement in policies}
        assert by_id["RejectKmsWithoutKey"]["Condition"] == {
            "StringEquals": {"s3:x-amz-server-side-encryption": "aws:kms"},
            "Null": {"s3:x-amz-server-side-encryption-aws-kms-key-id": "true"}}
        assert by_id["RejectCustomerProvidedKeys"]["Condition"]["Null"] == {
            "s3:x-amz-server-side-encryption-customer-algorithm": "false"}
    assert resources["ReportsBucket"]["Properties"]["LifecycleConfiguration"]["Rules"][1]["Transitions"][0]["TransitionInDays"] == 1095


def test_runtime_roles_have_no_ssm_or_private_ses_dependencies():
    policies = build_policies("123456789012", "af-south-1", "dev", "raw", "risk", "db-example",
        "sender@example.com", quarantine_bucket="quarantine", kms_key_arn="arn:aws:kms:af-south-1:123456789012:key/example")
    for service, policy in policies.items():
        actions = {a for s in policy["Statement"] for a in s["Action"]}
        assert "ssm:GetParameter" not in actions and "lambda:InvokeFunction" not in actions
        if service in {"ingest", "alert"}:
            assert not any(a.startswith(("rds-db:", "ec2:")) for a in actions)
        if service in {"scoring", "api", "report"}:
            assert "ses:SendEmail" not in actions

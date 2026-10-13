"""File completion, source identity, structured rejection and risk admission."""
import io
import json
import uuid
from datetime import timezone
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from fintrust import batches, ingest, jobs, rules, validators

ACCOUNT = "20000000-0000-4000-8000-000000000001"


def row(**changes):
    return {**dict(account_id=ACCOUNT, amount="10.00", currency="ZAR",
                  tx_date="2026-10-08T10:00:00.123456+02:00", tx_type="debit", merchant="Shop",
                  source_system="bank-demo", source_transaction_id="REF-A"), **changes}


def job(**changes):
    return jobs.make_job(row(**changes), "raw-bucket", "raw/a.csv", "content", 2)


def csv_text(rows):
    import csv
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


@pytest.fixture
def transport(monkeypatch):
    with mock_aws():
        client = boto3.client("s3", region_name="af-south-1")
        client.create_bucket(Bucket="batch-test", CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
        monkeypatch.setattr(ingest, "s3", client)
        monkeypatch.setenv("QUARANTINE_BUCKET", "batch-test")
        messages = []
        def send(**kw):
            messages.extend(kw["Entries"])
            return {"Successful": [{"Id": e["Id"]} for e in kw["Entries"]]}
        monkeypatch.setattr(ingest.sqs, "send_message_batch", send)
        yield client, messages


def publish(text, key="raw/a.csv", **kwargs):
    return ingest.process_csv("batch-test", key, text, queue_url="jobs.fifo",
                              check_accounts=False, track_batches=True, **kwargs)


def records(client, prefix="quarantine/"):
    result = []
    for item in client.list_objects_v2(Bucket="batch-test", Prefix=prefix).get("Contents", []):
        body = client.get_object(Bucket="batch-test", Key=item["Key"])["Body"]
        try:
            result.extend(json.loads(line) for line in body.read().decode().splitlines())
        finally:
            body.close()
    return result


def test_exact_file_replay_renamed_or_new_version_is_audited_without_republication(transport):
    client, messages = transport
    text = csv_text([row()])
    assert publish(text, version="one")["rows_valid"] == 1
    replay = publish(text, key="raw/renamed.csv", version="two")
    assert replay["reason_code"] == "DUPLICATE_FILE" and replay["rows_valid"] == 0
    assert len(messages) == 1
    audits = records(client, "quarantine/batches/")
    assert any(a["status"] == "DUPLICATE_FILE" and a["source_file"] == "raw/renamed.csv" for a in audits)
    assert any(a["status"] == "QUEUED" and a["counts"]["rows_received"] == 1 for a in audits)


def test_repeated_identity_within_file_has_structured_reason(transport):
    client, messages = transport
    result = publish(csv_text([row(), row()]))
    assert result["rows_valid"] == 1 and result["rows_duplicate"] == 1
    assert len(messages) == 1
    rejection = next(r for r in records(client) if r.get("reason_code") == "DUPLICATE_ROW_IN_FILE")
    assert rejection["source_row"] == 3 and rejection["source_transaction_id"] == "REF-A"
    assert rejection["batch_id"] and rejection["ingested_at"] and rejection["raw_row"]["amount"] == "10.00"


def test_conflicting_same_reference_in_file_is_not_silently_discarded(transport):
    client, messages = transport
    result = publish(csv_text([row(), row(amount="11.00")]))
    assert result["rows_valid"] == 1 and result["rows_quarantined"] == 1
    assert any(r.get("reason_code") == "TRANSACTION_IDENTITY_CONFLICT" for r in records(client))


def test_ambiguous_equal_rows_without_reference_remain_distinct(transport):
    _, messages = transport
    r = row(source_transaction_id="")
    assert publish(csv_text([r, r]))["rows_valid"] == 2
    assert len({m["MessageDeduplicationId"] for m in messages}) == 2
    assert len({json.loads(m["MessageBody"])["transaction_id"] for m in messages}) == 2


def test_partial_publish_never_marks_complete_and_retry_reuses_ids(transport, monkeypatch):
    client, messages = transport
    actual = ingest.sqs.send_message_batch
    captured = []
    def fail(**kw):
        captured.extend(kw["Entries"])
        return {"Failed": [{"Id": "0"}]}
    monkeypatch.setattr(ingest.sqs, "send_message_batch", fail)
    text = csv_text([row()])
    with pytest.raises(RuntimeError, match="publish"):
        publish(text)
    assert not any(r.get("status") == "QUEUED" for r in records(client, "quarantine/batches/"))
    monkeypatch.setattr(ingest.sqs, "send_message_batch", actual)
    publish(text)
    assert captured[0]["MessageDeduplicationId"] == messages[0]["MessageDeduplicationId"]


def test_batch_access_denied_is_never_treated_as_missing():
    client = Mock()
    client.list_objects_v2.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "ListObjectsV2")
    audit = batches.BatchAudit(client, "audit", "raw", "file", batches.metadata("raw", b"file"))
    with pytest.raises(ClientError):
        audit.completed()
    client.put_object.assert_not_called()


@pytest.mark.parametrize("code", ["ConditionalRequestConflict", "AccessDenied"])
def test_marker_failure_retries_instead_of_claiming_completion(code):
    client = Mock()
    client.put_object.side_effect = [{}, ClientError({"Error": {"Code": code}}, "PutObject")]
    audit = batches.BatchAudit(client, "audit", "raw", "file", batches.metadata("raw", b"file"))
    with pytest.raises(ClientError):
        audit.complete({"rows_received": 1, "rows_valid": 1, "rows_quarantined": 0})
    assert client.put_object.call_args.kwargs["IfNoneMatch"] == "*"


def test_source_reference_fingerprint_excludes_internal_uuid_and_source_file():
    a = job(transaction_id=str(uuid.uuid4()))
    b = job(transaction_id=str(uuid.uuid4()))
    b["source"]["key"] = "raw/other.csv"
    assert jobs.business_fingerprint(a) == jobs.business_fingerprint(b)
    assert jobs.queue_deduplication_id(a) == jobs.queue_deduplication_id(b)
    assert jobs.business_fingerprint(a) != jobs.business_fingerprint(job(amount="11.00"))
    assert jobs.business_fingerprint(a) != jobs.business_fingerprint(job(source_transaction_id="REF-B"))
    assert jobs.parse_job(json.dumps(a)) == a


def test_timestamp_normalizes_offset_preserving_microseconds():
    value = job()["transaction_timestamp"]
    assert value == "2026-10-08T08:00:00.123456+00:00"
    assert validators.parse_transaction_date(value).microsecond == 123456
    assert validators.parse_transaction_date(value).tzinfo == timezone.utc
    assert validators.validate_row(row(tx_date="2026-10-08T10:00:00.1234567Z")) is not None
    assert jobs.business_fingerprint(job()) == jobs.business_fingerprint(job(tx_date=value))


@pytest.mark.parametrize("changes,code", [({"amount": "-1"}, "INVALID_AMOUNT"),
    ({"tx_date": "bad"}, "INVALID_TIMESTAMP"), ({"account_id": ""}, "MISSING_REQUIRED_FIELD")])
def test_invalid_rows_have_reason_and_raw_admission_metadata(transport, changes, code):
    client, messages = transport
    result = publish(csv_text([row(**changes)]))
    assert result["rows_valid"] == 0 and result["rows_quarantined"] == 1 and not messages
    rejected = next(r for r in records(client) if r.get("reason_code") == code)
    assert rejected["raw_row"] and rejected["validation_errors"] and rejected["source_file"]


def test_valid_high_risk_is_queued_not_quarantined(transport):
    client, messages = transport
    assert publish(csv_text([row(amount="250000.00", tx_type="transfer", country="US")]))["rows_valid"] == 1
    assert len(messages) == 1 and rules.evaluate(json.loads(messages[0]["MessageBody"]))["risk_level"] == "High"
    assert not any(r.get("validation_errors") for r in records(client))


def test_duplicate_charge_rule_keeps_explicit_matching_metadata(monkeypatch):
    monkeypatch.setenv("RISK_DUPLICATE_CHARGE_SECONDS", "3")
    result = rules.evaluate(job(), duplicate_matches=["other-transaction"])
    assert result["score"] == 20
    rule = result["triggered_rules"][0]
    assert rule["rule"] == "POSSIBLE_DUPLICATE_CHARGE" and rule["window_seconds"] == 3
    assert rule["matching_transaction_ids"] == ["other-transaction"]


def test_interleaved_publishers_share_one_completion_marker_and_stable_ids(transport, monkeypatch):
    client, messages = transport
    original = ingest.sqs.send_message_batch
    calls = []
    text = csv_text([row()])
    def interleave(**kwargs):
        calls.append(kwargs["Entries"][0]["MessageDeduplicationId"])
        monkeypatch.setattr(ingest.sqs, "send_message_batch", original)
        assert publish(text)["rows_valid"] == 1
        return original(**kwargs)
    monkeypatch.setattr(ingest.sqs, "send_message_batch", interleave)
    assert publish(text)["rows_valid"] == 1
    assert len(messages) == 2 and len({m["MessageDeduplicationId"] for m in messages}) == 1
    keys = client.list_objects_v2(Bucket="batch-test", Prefix="quarantine/batches/")["Contents"]
    assert sum(k["Key"].endswith("complete.json") for k in keys) == 1
    assert publish(text)["reason_code"] == "DUPLICATE_FILE"


def test_quarantine_redacts_unknown_columns_and_keeps_raw_source_pointer(transport):
    client, _ = transport
    publish(csv_text([row(amount="bad", national_id="private-identity", email="private@example.com")]))
    rejected = next(r for r in records(client) if r.get("reason_code") == "INVALID_AMOUNT")
    assert rejected["raw_row_redacted"] is True
    assert "national_id" not in rejected["raw_row"] and "email" not in rejected["record"]
    assert rejected["source"]["key"] == "raw/a.csv" and rejected["source_row"] == 2


def test_blank_optional_namespace_uses_stable_bucket_default():
    value = job(source_system="  ")
    assert value["source_system"] == "raw-bucket"
    assert jobs.parse_job(value) == value


@pytest.mark.parametrize("value", ["20261008T100000.1234567Z", "2026-10-08T10:00.1234567Z"])
def test_alternative_iso_forms_do_not_silently_truncate_precision(value):
    with pytest.raises(ValueError, match="precision"):
        validators.parse_transaction_date(value)

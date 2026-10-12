"""Durable content-addressed S3 batch audit, independent of the ledger network.

Only completed publication is skippable. Partial/concurrent publication can
repeat messages; PostgreSQL remains the final idempotency boundary.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from botocore.exceptions import ClientError


def metadata(bucket, payload):
    digest = hashlib.sha256(payload).hexdigest()
    return {"batch_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"fintrust-batch:{bucket}:{digest}")),
            "file_sha256": digest, "ingested_at": datetime.now(timezone.utc).isoformat()}


class BatchAudit:
    def __init__(self, client, bucket, source_bucket, key, batch, version=None, etag=None):
        self.client, self.bucket = client, bucket
        self.batch = batch
        self.prefix = "quarantine/batches/" + batch["batch_id"] + "/"
        self.key = self.prefix + "complete.json"
        self.attempt_key = self.prefix + "attempts/" + str(uuid.uuid4()) + ".json"
        self.source = {"source_bucket": source_bucket, "source_file": key,
                       "source_version": version, "source_etag": etag}

    def first_receipt(self):
        """Freeze the receipt clock before validation, including failed retries."""
        key=self.prefix+"receipt.json"
        try:
            self.client.put_object(Bucket=self.bucket,Key=key,IfNoneMatch="*",
                Body=json.dumps(self.batch).encode(),ContentType="application/json")
        except ClientError as error:
            if error.response["Error"]["Code"]!="PreconditionFailed": raise
            body=self.client.get_object(Bucket=self.bucket,Key=key)["Body"]
            try: saved=json.loads(body.read())
            finally: body.close()
            if saved.get("batch_id")!=self.batch["batch_id"] or saved.get("file_sha256")!=self.batch["file_sha256"]:
                raise ValueError("Receipt identity mismatch")
            self.batch.update(saved)
        return self.batch

    def completed(self):
        # List only the exact marker prefix; a Get on an absent object can be 403
        # without unrestricted ListBucket. Never interpret AccessDenied as absent.
        found = self.client.list_objects_v2(Bucket=self.bucket, Prefix=self.key, MaxKeys=1)
        if not any(item["Key"] == self.key for item in found.get("Contents", [])):
            return None
        body = self.client.get_object(Bucket=self.bucket, Key=self.key)["Body"]
        try:
            result = json.loads(body.read())
        finally:
            body.close()
        if result["batch_id"] != self.batch["batch_id"] or result["file_sha256"] != self.batch["file_sha256"]:
            raise ValueError("Batch marker identity mismatch")
        if (result.get("status") not in {"PUBLISHED", "QUEUED"} or not isinstance(result.get("counts"), dict)
                or any(type(result["counts"].get(k)) is not int or result["counts"][k] < 0
                       for k in ("rows_received", "rows_valid", "rows_quarantined"))):
            raise ValueError("Invalid batch completion marker")
        return result

    def record(self, status, counts=None, reason=None):
        summary = {} if counts is None else {
            "total_rows": counts["rows_received"], "queued_rows": counts["rows_valid"],
            "duplicate_rows": counts.get("rows_duplicate", 0),
            "rejected_rows": max(0, counts["rows_quarantined"] - counts.get("rows_duplicate", 0))}
        value = {**self.batch, **self.source, **summary, "status": status, "counts": counts,
                 "reason_code": reason, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.client.put_object(Bucket=self.bucket, Key=self.attempt_key,
                               Body=json.dumps(value).encode(), ContentType="application/json")
        return value

    def complete(self, counts):
        value = self.record("QUEUED", counts)
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.key, IfNoneMatch="*",
                                   Body=json.dumps(value).encode(), ContentType="application/json")
        except ClientError as error:
            if error.response["Error"]["Code"] != "PreconditionFailed":
                raise  # 409 and infrastructure failures retry; no false completion.
            if self.completed() is None:
                raise RuntimeError("Batch completion race has no committed marker")

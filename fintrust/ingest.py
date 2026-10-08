import csv
import io
import json
import uuid
from decimal import Decimal
import os

from .jobs import business_fingerprint, identity_key, make_job, queue_deduplication_id, transaction_id
from .batches import BatchAudit, metadata
from .ledger import IdentityConflict, existing_transaction, insert_transaction
from .quarantine import rejection, validation_code
from time import perf_counter
from typing import Any
from urllib.parse import unquote_plus

import boto3
import psycopg2

from .db import get_connection
from .config import AWS_REGION
from .validators import REQUIRED_COLUMNS, validate_row, parse_transaction_date

from src.shared.logger import get_logger

logger = get_logger("ingest")
s3 = boto3.client("s3", region_name=AWS_REGION)
sqs = boto3.client("sqs", region_name=AWS_REGION)
MAX_FILE_BYTES = 1024 * 1024
MAX_FILE_ROWS = 5000


def transform_row(
    row: dict[str, str],
    raw_file: str,
    source_row: int = 1,
    source_identity: str | None = None,
) -> tuple[Any, ...]:
    currency = (row.get("currency") or "ZAR").strip().upper() or "ZAR"
    country = (row.get("country") or "ZA").strip().upper() or "ZA"
    return (
        transaction_id(row, source_identity or raw_file, source_row),
        str(uuid.UUID(row["account_id"].strip())),
        Decimal(row["amount"]),
        currency,
        (row.get("merchant") or "").strip() or None,
        parse_transaction_date(row["tx_date"]),
        row["tx_type"].strip().lower(),
        country != "ZA",
        raw_file,
    )


def _load_rows(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """Local teaching loader shares SQL identity checks; never silently drops conflicts."""
    if not rows:
        return []
    connection = get_connection()
    failed_rows = []
    try:
        with connection.cursor() as cursor:
            for index, values in enumerate(rows):
                savepoint = f"row_{index}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                try:
                    if len(values) != 10:
                        raise ValueError("Local loader requires normalized transaction metadata")
                    job = json.loads(values[9])
                    cursor.execute("SELECT account_id FROM accounts WHERE account_id=%s FOR UPDATE", (job["account_id"],))
                    if not cursor.fetchone():
                        failed_rows.append((values, "unknown account"))
                    elif existing_transaction(cursor, job):
                        failed_rows.append((values, "DUPLICATE_TRANSACTION"))
                    else:
                        insert_transaction(cursor, job)
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                except (psycopg2.IntegrityError, psycopg2.DataError, IdentityConflict) as error:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                    failed_rows.append((values, str(error) if isinstance(error, IdentityConflict) else type(error).__name__))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return failed_rows


def process_csv(bucket, key, raw_text, source_identity=None, *, queue_url=None, version=None,
                etag=None, check_accounts=True, track_batches=False, file_bytes=None, source_filename=None):
    payload = file_bytes if file_bytes is not None else raw_text.encode("utf-8")
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("CSV exceeds the 1 MiB file limit")
    if file_bytes is not None and payload.decode("utf-8-sig") != raw_text:
        raise ValueError("File hash input differs from decoded CSV")
    batch = metadata(bucket, payload)
    audit = BatchAudit(s3, os.getenv("QUARANTINE_BUCKET", bucket), bucket, key, batch, version, etag) if track_batches else None
    if audit:
        audit.source["original_filename"] = source_filename or key.rsplit("/", 1)[-1]
        completed = audit.completed()
        if completed:
            original = completed["counts"]
            replay = {"rows_received": original["rows_received"], "rows_valid": 0,
                    "rows_quarantined": 0, "quarantine_rate_percent": 0,
                    "rows_duplicate": original["rows_received"], "reason_code": "DUPLICATE_FILE",
                    "batch_id": batch["batch_id"]}
            audit.record("DUPLICATE_FILE", replay, "DUPLICATE_FILE")
            return replay
        audit.record("STARTED")
    try:
        counts = _process_csv(bucket, key, raw_text, source_identity, queue_url=queue_url,
                              version=version, etag=etag, check_accounts=check_accounts, batch=batch)
        if audit:
            audit.complete(counts)
        return counts
    except Exception as error:
        if audit:
            audit.record("FAILED", reason=type(error).__name__)
        raise


def _process_csv(
    bucket: str,
    key: str,
    raw_text: str,
    source_identity: str | None = None,
    *, queue_url: str | None = None, version: str | None = None, etag: str | None = None,
    check_accounts: bool = True, batch=None,
) -> dict[str, Any]:
    # Direct loading is retained only for the existing local teaching workflow.
    # The S3 Lambda entry point always supplies its required FIFO queue URL.
    if len(raw_text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("CSV exceeds the 1 MiB file limit")
    reader = csv.DictReader(io.StringIO(raw_text), strict=True)
    if reader.fieldnames and len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV contains duplicate column names")
    headers = set(reader.fieldnames or [])
    missing_headers = sorted(REQUIRED_COLUMNS - headers)
    if missing_headers:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_headers)}")

    valid_rows: list[tuple[Any, ...]] = []
    quarantine_rows: list[dict[str, Any]] = []
    source_rows = {}
    source_lines = {}
    queued_jobs = []
    rows_received = 0
    seen = {}
    duplicate_rows = 0
    for row_number, row in enumerate(reader, start=2):
        rows_received += 1
        if rows_received > MAX_FILE_ROWS:
            raise ValueError("CSV exceeds the 5000-row limit; no rows from this file were loaded")
        error = validate_row(row)
        if error:
            quarantine_rows.append(rejection(validation_code(error), error, row, bucket=bucket,
                key=key, row_number=row_number, batch=batch, version=version, etag=etag))
            continue
        source = "batch:" + batch["batch_id"]
        job = make_job(row, bucket, key, source, row_number, version, etag, batch=batch)
        token, digest = identity_key(job), business_fingerprint(job)
        if token in seen:
            code = "DUPLICATE_ROW_IN_FILE" if seen[token] == digest else "TRANSACTION_IDENTITY_CONFLICT"
            duplicate_rows += code == "DUPLICATE_ROW_IN_FILE"
            quarantine_rows.append(rejection(code, "Repeated identity in file" if seen[token] == digest
                else "Repeated identity has conflicting financial data", row, bucket=bucket,
                key=key, row_number=row_number, batch=batch, version=version, etag=etag))
            continue
        seen[token] = digest
        values = transform_row(row, key, row_number, source) + (json.dumps(job),)
        valid_rows.append(values)
        source_rows[values] = row
        source_lines[values] = row_number
        if queue_url:
            queued_jobs.append((values, job))

    if queue_url and check_accounts:
        # Local compatibility: resolve accounts before publishing.
        # while unknown business accounts are rejected into quarantine.
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT account_id::text FROM accounts WHERE account_id = ANY(%s::uuid[])",
                               ([v[1] for v in valid_rows],))
                accounts = {r[0] for r in cursor.fetchall()}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        failed_rows = [(v, "unknown account") for v in valid_rows if v[1] not in accounts]
    elif queue_url:
        failed_rows = []  # Scoring validates accounts under the ledger lock.
    else:
        failed_rows = _load_rows(valid_rows)
    for values, error in failed_rows:
        code = "DUPLICATE_TRANSACTION" if error == "DUPLICATE_TRANSACTION" else (
            "UNKNOWN_ACCOUNT" if error == "unknown account" else "TRANSACTION_IDENTITY_CONFLICT")
        duplicate_rows += code == "DUPLICATE_TRANSACTION"
        quarantine_rows.append(rejection(code, f"database constraint rejected row: {error}",
            source_rows.get(values), bucket=bucket, key=key, row_number=source_lines.get(values),
            batch=batch, version=version, etag=etag))

    if quarantine_rows:
        source_id = uuid.uuid5(uuid.NAMESPACE_URL, source_identity or f"{bucket}:{key}")
        quarantine_key = f"quarantine/{source_id}.jsonl"
        body = "".join(json.dumps(item, default=str) + "\n" for item in quarantine_rows)
        s3.put_object(Bucket=os.getenv("QUARANTINE_BUCKET", bucket), Key=quarantine_key,
                      Body=body.encode("utf-8"), ContentType="application/x-ndjson")

    if queue_url:
        rejected = {v for v, _ in failed_rows}
        entries = []
        for values, job in queued_jobs:
            if values in rejected:
                continue
            # Includes the business UUID and canonical financial fields. Conflicting
            # reuse of an ID must reach SQL for rejection, not be hidden by FIFO.
            entries.append({"Id": str(len(entries)), "MessageBody": json.dumps(job),
                            "MessageGroupId": job["account_id"],
                            "MessageDeduplicationId": queue_deduplication_id(job)})
        for start in range(0, len(entries), 10):
            entries_batch = entries[start:start + 10]
            response = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries_batch)
            # A batch can return HTTP 200 and still reject individual messages.
            # Fail the S3 invocation; replay safely republishes successful entries.
            if response.get("Failed") or len(response.get("Successful", [])) != len(entries_batch):
                raise RuntimeError("FIFO publish batch did not complete")

    quarantine_rate_percent = round(
        len(quarantine_rows) / rows_received * 100, 2
    ) if rows_received else 0
    counts = {
        "rows_received": rows_received,
        "rows_valid": len(valid_rows) - len(failed_rows),
        "rows_quarantined": len(quarantine_rows),
        "quarantine_rate_percent": quarantine_rate_percent,
    }

    if duplicate_rows:
        counts["rows_duplicate"] = duplicate_rows
    return counts


def _process_record(record):
    started = perf_counter()
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    encoded_version_id = record["s3"]["object"].get("versionId")
    version_id = encoded_version_id
    request = {"Bucket": bucket, "Key": key}
    if version_id:
        request["VersionId"] = version_id
    try:
        response = s3.get_object(**request)
        body = response["Body"]
        try:
            raw_bytes = body.read(MAX_FILE_BYTES + 1)
        finally:
            body.close()
        if len(raw_bytes) > MAX_FILE_BYTES:
            raise ValueError("CSV exceeds the 1 MiB file limit")
        raw_text = raw_bytes.decode("utf-8-sig")
        source_identity = f"{bucket}:{key}:{version_id or response.get('ETag') or 'unversioned'}"
        queue_url = os.environ["TRANSACTION_QUEUE_URL"]
        if not queue_url.endswith(".fifo"):
            raise ValueError("TRANSACTION_QUEUE_URL must identify a FIFO queue")
        counts = process_csv(bucket, key, raw_text, source_identity, queue_url=queue_url,
                             version=version_id, etag=response.get("ETag"), check_accounts=False,
                             track_batches=True, file_bytes=raw_bytes)
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(json.dumps({
            "event": "ingest_complete",
            "bucket": bucket,
            "s3_key": key,
            **counts,
            "duration_ms": duration_ms,
        }))
        return {"statusCode": 200, **counts}
    except Exception as error:
        logger.exception(json.dumps({
            "event": "ingest_failed",
            "bucket": bucket,
            "s3_key": key,
            "error_type": type(error).__name__,
        }))
        raise


def lambda_handler(event, context):
    records = event.get("Records", [])
    if not records:
        raise ValueError("S3 event must contain at least one record")
    results = [_process_record(record) for record in records]
    if len(results) == 1:
        return results[0]
    return {"statusCode": 200, "files_processed": len(results), "results": results}

import csv
import io
import json
import logging
import uuid
from decimal import Decimal
from time import perf_counter
from typing import Any
from urllib.parse import unquote_plus

import boto3
import psycopg2

from .db import get_connection
from .validators import REQUIRED_COLUMNS, validate_row, parse_transaction_date

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client("s3")
MAX_FILE_BYTES = 1024 * 1024
MAX_FILE_ROWS = 5000

INSERT_TRANSACTION = """
    INSERT INTO transactions
        (tx_id, account_id, amount, currency, merchant, tx_date, tx_type, cross_border, raw_file)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (tx_id) DO NOTHING
"""


def transform_row(
    row: dict[str, str],
    raw_file: str,
    source_row: int = 1,
    source_identity: str | None = None,
) -> tuple[Any, ...]:
    currency = (row.get("currency") or "ZAR").strip().upper() or "ZAR"
    country = (row.get("country") or "ZA").strip().upper() or "ZA"
    return (
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"fintrust:{source_identity or raw_file}:{source_row}")),
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
    if not rows:
        return []

    connection = get_connection()
    failed_rows = []
    try:
        with connection.cursor() as cursor:
            cursor.executemany(INSERT_TRANSACTION, rows)
        connection.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        connection.rollback()
        raise
    except (psycopg2.IntegrityError, psycopg2.DataError):
        connection.rollback()
        try:
            with connection.cursor() as cursor:
                for index, values in enumerate(rows):
                    savepoint = f"row_{index}"
                    cursor.execute(f"SAVEPOINT {savepoint}")
                    try:
                        cursor.execute(INSERT_TRANSACTION, values)
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                    except (psycopg2.IntegrityError, psycopg2.DataError) as exc:
                        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                        failed_rows.append((values, type(exc).__name__))
                connection.commit()
        except Exception:
            connection.rollback()
            raise
    except psycopg2.Error:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return failed_rows


def process_csv(
    bucket: str,
    key: str,
    raw_text: str,
    source_identity: str | None = None,
) -> dict[str, int]:
    if len(raw_text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("CSV exceeds the 1 MiB file limit")
    reader = csv.DictReader(io.StringIO(raw_text))
    if reader.fieldnames and len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV contains duplicate column names")
    headers = set(reader.fieldnames or [])
    missing_headers = sorted(REQUIRED_COLUMNS - headers)
    if missing_headers:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_headers)}")

    valid_rows: list[tuple[Any, ...]] = []
    quarantine_rows: list[dict[str, Any]] = []
    source_rows: dict[str, dict[str, str]] = {}
    source_lines: dict[str, int] = {}
    rows_received = 0
    for row_number, row in enumerate(reader, start=2):
        rows_received += 1
        if rows_received > MAX_FILE_ROWS:
            raise ValueError("CSV exceeds the 5000-row limit; no rows from this file were loaded")
        error = validate_row(row)
        if error:
            quarantine_rows.append({"source_row": row_number, "error": error, "record": row})
            continue
        values = transform_row(row, key, row_number, source_identity)
        valid_rows.append(values)
        source_rows[values[0]] = row
        source_lines[values[0]] = row_number

    failed_rows = _load_rows(valid_rows)
    for values, error in failed_rows:
        quarantine_rows.append({
            "source_row": source_lines.get(values[0]),
            "error": f"database constraint rejected row: {error}",
            "tx_id": values[0],
            "account_id": values[1],
            "record": source_rows.get(values[0]),
        })

    if quarantine_rows:
        source_id = uuid.uuid5(uuid.NAMESPACE_URL, source_identity or f"{bucket}:{key}")
        quarantine_key = f"quarantine/{source_id}.jsonl"
        body = "".join(json.dumps(item, default=str) + "\n" for item in quarantine_rows)
        s3.put_object(Bucket=bucket, Key=quarantine_key, Body=body.encode("utf-8"))

    quarantine_rate_percent = round(
        len(quarantine_rows) / rows_received * 100, 2
    ) if rows_received else 0
    return {
        "rows_received": rows_received,
        "rows_valid": len(valid_rows) - len(failed_rows),
        "rows_quarantined": len(quarantine_rows),
        "quarantine_rate_percent": quarantine_rate_percent,
    }


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
        source_identity = f"{bucket}:{key}:{version_id or 'unversioned'}"
        counts = process_csv(bucket, key, raw_text, source_identity)
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

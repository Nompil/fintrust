import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import unquote_plus

import boto3
import psycopg2

from .db import get_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client("s3")

REQUIRED_COLUMNS = {"account_id", "amount", "tx_date", "tx_type"}
ALLOWED_CURRENCIES = {"ZAR", "USD", "EUR", "GBP", "KES"}
INSERT_TRANSACTION = """
    INSERT INTO transactions
        (tx_id, account_id, amount, currency, merchant, tx_date, tx_type, cross_border, raw_file)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (tx_id) DO NOTHING
"""


def validate_row(row: dict[str, str]) -> str | None:
    missing = [column for column in REQUIRED_COLUMNS if not row.get(column, "").strip()]
    if missing:
        return f"missing required field(s): {', '.join(sorted(missing))}"

    try:
        amount = Decimal(row["amount"])
    except (InvalidOperation, ValueError):
        return "amount must be numeric"
    if not amount.is_finite() or amount <= 0:
        return "amount must be greater than zero"

    currency = row.get("currency", "ZAR").strip().upper() or "ZAR"
    if currency not in ALLOWED_CURRENCIES:
        return f"unsupported currency: {currency}"

    if row["tx_type"].strip().lower() not in {"debit", "credit", "transfer", "fee"}:
        return "unsupported tx_type"

    try:
        parse_transaction_date(row["tx_date"])
    except ValueError:
        return "tx_date must be a valid ISO-8601 date or timestamp"

    try:
        uuid.UUID(row["account_id"].strip())
    except ValueError:
        return "account_id must be a UUID present in the accounts table"

    return None


def parse_transaction_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def transform_row(
    row: dict[str, str],
    raw_file: str,
    source_row: int = 1,
    source_identity: str | None = None,
) -> tuple[Any, ...]:
    currency = row.get("currency", "ZAR").strip().upper() or "ZAR"
    country = row.get("country", "ZA").strip().upper() or "ZA"
    return (
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"fintrust:{source_identity or raw_file}:{source_row}")),
        str(uuid.UUID(row["account_id"].strip())),
        Decimal(row["amount"]),
        currency,
        row.get("merchant", "").strip() or None,
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
    except psycopg2.Error:
        connection.rollback()
        with connection.cursor() as cursor:
            for index, values in enumerate(rows):
                savepoint = f"row_{index}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                try:
                    cursor.execute(INSERT_TRANSACTION, values)
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                except Exception as exc:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                    failed_rows.append((values, str(exc)))
            connection.commit()
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
    reader = csv.DictReader(io.StringIO(raw_text))
    headers = set(reader.fieldnames or [])
    missing_headers = sorted(REQUIRED_COLUMNS - headers)
    if missing_headers:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_headers)}")

    valid_rows: list[tuple[Any, ...]] = []
    quarantine_rows: list[dict[str, Any]] = []
    source_rows: dict[str, dict[str, str]] = {}
    rows_received = 0
    for row_number, row in enumerate(reader, start=2):
        rows_received += 1
        error = validate_row(row)
        if error:
            quarantine_rows.append({"source_row": row_number, "error": error, "record": row})
            continue
        values = transform_row(row, key, row_number, source_identity)
        valid_rows.append(values)
        source_rows[values[0]] = row

    failed_rows = _load_rows(valid_rows)
    for values, error in failed_rows:
        quarantine_rows.append({
            "source_row": None,
            "error": f"database constraint rejected row: {error}",
            "tx_id": values[0],
            "account_id": values[1],
            "record": source_rows.get(values[0]),
        })

    if quarantine_rows:
        quarantine_key = f"quarantine/{key.rsplit('/', 1)[-1]}.jsonl"
        body = "".join(json.dumps(item, default=str) + "\n" for item in quarantine_rows)
        s3.put_object(Bucket=bucket, Key=quarantine_key, Body=body.encode("utf-8"))

    return {
        "rows_received": rows_received,
        "rows_valid": len(valid_rows) - len(failed_rows),
        "rows_quarantined": len(quarantine_rows),
    }


def lambda_handler(event, context):
    started = perf_counter()
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    encoded_version_id = record["s3"]["object"].get("versionId")
    version_id = unquote_plus(encoded_version_id) if encoded_version_id else None
    request = {"Bucket": bucket, "Key": key}
    if version_id:
        request["VersionId"] = version_id
    response = s3.get_object(**request)
    raw_text = response["Body"].read().decode("utf-8-sig")
    source_identity = f"{bucket}:{key}:{version_id or 'unversioned'}"
    counts = process_csv(bucket, key, raw_text, source_identity)
    duration_ms = round((perf_counter() - started) * 1000, 2)
    logger.info(json.dumps({
        "event": "ingest_complete",
        "s3_key": key,
        **counts,
        "duration_ms": duration_ms,
    }))
    return {"statusCode": 200, **counts}

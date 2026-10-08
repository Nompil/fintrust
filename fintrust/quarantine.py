"""Structured rejection metadata. Unknown columns/PII do not leave the raw bucket."""
from datetime import datetime, timezone

FIELDS = {"transaction_id", "tx_id", "account_id", "amount", "currency", "tx_date",
          "tx_type", "country", "merchant", "source_system", "source_transaction_id", "source_reference"}


def validation_code(error):
    if error.startswith("missing required"):
        return "MISSING_REQUIRED_FIELD"
    if error.startswith("amount"):
        return "INVALID_AMOUNT"
    if error.startswith("tx_date"):
        return "INVALID_TIMESTAMP"
    return "INVALID_ROW"


def rejection(code, detail, row, *, bucket, key, row_number, batch=None, version=None, etag=None):
    raw = {k: v for k, v in (row or {}).items() if k in FIELDS}
    now = datetime.now(timezone.utc).isoformat()
    return {"reason_code": code, "reason_detail": detail, "error": detail,
            "validation_errors": [detail], "record": raw, "raw_row": raw,
            "raw_row_redacted": any(k not in FIELDS for k in (row or {})),
            "source_bucket": bucket, "source_file": key, "source_version": version,
            "source_etag": etag, "source_row": row_number,
            "source": {"bucket": bucket, "key": key, "version": version, "etag": etag, "row": row_number},
            "batch_id": (batch or {}).get("batch_id"),
            "ingested_at": (batch or {}).get("ingested_at", now), "quarantined_at": now,
            "source_transaction_id": raw.get("source_transaction_id") or raw.get("source_reference"),
            "transaction_id": raw.get("transaction_id") or raw.get("tx_id")}

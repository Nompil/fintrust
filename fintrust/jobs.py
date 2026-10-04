"""Version 1 queue contracts. Amounts are decimal strings; timestamps are UTC.

No customer names or identity numbers travel through the processing queue.
Supplied UUIDs identify business transactions independently of upload location.
Legacy CSVs without IDs retain source/version/row identity; they cannot guarantee
business deduplication across different files and should not be used for that case.
"""
import hashlib
import json
import uuid
from datetime import timezone

from .validators import parse_transaction_date, validate_row


def transaction_id(row, source_identity, source_row):
    supplied = row.get("transaction_id") or row.get("tx_id")
    return str(uuid.UUID(supplied.strip())) if supplied else str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"fintrust:{source_identity}:{source_row}"))


def make_job(row, bucket, key, source_identity, source_row, version=None, etag=None):
    from decimal import Decimal
    error = validate_row(row)
    if error:
        raise ValueError(error)
    identity = transaction_id(row, source_identity, source_row)
    return {
        "schema_version": 1, "transaction_id": identity,
        "account_id": str(uuid.UUID(row["account_id"].strip())),
        "amount": format(Decimal(row["amount"]), ".2f"),
        "currency": (row.get("currency") or "ZAR").strip().upper() or "ZAR",
        "transaction_type": row["tx_type"].strip().lower(),
        "country": (row.get("country") or "ZA").strip().upper() or "ZA",
        "transaction_timestamp": parse_transaction_date(row["tx_date"]).astimezone(timezone.utc).isoformat(),
        "merchant": (row.get("merchant") or "").strip(),
        "source": {"bucket": bucket, "key": key, "version": version,
                   "etag": etag, "row": source_row},
        "correlation_id": identity,
    }


def parse_job(payload):
    job = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(job, dict) or type(job.get("schema_version")) is not int or job["schema_version"] != 1:
        raise ValueError("Unsupported transaction job version")
    source = job["source"]
    if (not isinstance(source, dict) or not isinstance(source.get("row"), int)
            or isinstance(source["row"], bool) or source["row"] < 2
            or not isinstance(source.get("key"), str) or not source["key"]
            or not isinstance(source.get("bucket"), str) or not source["bucket"]):
        raise ValueError("Invalid transaction source")
    if any(source.get(field) is not None and not isinstance(source[field], str) for field in ("version", "etag")):
        raise ValueError("Invalid transaction source version")
    uuid.UUID(job["correlation_id"])
    row = {"transaction_id": job["transaction_id"], "account_id": job["account_id"],
           "amount": job["amount"], "currency": job["currency"],
           "tx_type": job["transaction_type"], "tx_date": job["transaction_timestamp"],
           "country": job["country"], "merchant": job.get("merchant", "")}
    if not all(isinstance(v, str) for v in row.values()):
        raise ValueError("Transaction fields must be strings")
    normalized = make_job(row, source["bucket"], source["key"], "", source["row"],
                          source.get("version"), source.get("etag"))
    normalized["correlation_id"] = job["correlation_id"]
    return normalized


def business_fingerprint(job):
    fields = {k: v for k, v in job.items() if k not in {"source", "correlation_id"}}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def high_risk_event(result):
    return {"schema_version": 1, "event_type": "HIGH_RISK", "transaction_id": result["transaction_id"],
            "account_id": result["account_id"], "score": result["score"],
            "risk_level": result["risk_level"], "correlation_id": result["correlation_id"]}

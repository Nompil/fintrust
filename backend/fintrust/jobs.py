"""Versioned queue contracts: explicit source identity, decimal amounts, UTC microseconds."""
import hashlib
import json
import uuid
from datetime import timezone

from .validators import parse_transaction_date, validate_row


def transaction_id(row, source_identity, source_row):
    supplied = row.get("transaction_id") or row.get("tx_id")
    return str(uuid.UUID(supplied.strip())) if supplied else str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"fintrust:{source_identity}:{source_row}"))


def make_job(row, bucket, key, source_identity, source_row, version=None, etag=None, *, batch=None):
    from decimal import Decimal
    error = validate_row(row)
    if error:
        raise ValueError(error)
    identity = transaction_id(row, source_identity, source_row)
    job = {
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
    reference = (row.get("source_transaction_id") or row.get("source_reference") or "").strip()
    if reference or batch:
        job["schema_version"] = 2
        job["source_system"] = (row.get("source_system") or "").strip() or bucket
        job["source_transaction_id"] = reference or None
        if batch:
            job["batch"] = batch
    return job


def parse_job(payload):
    job = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(job, dict) or type(job.get("schema_version")) is not int or job["schema_version"] not in {1, 2}:
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
    if job["schema_version"] == 2:
        if not isinstance(job.get("source_system"), str) or not job["source_system"].strip():
            raise ValueError("Invalid source system")
        reference = job.get("source_transaction_id")
        if reference is not None and (not isinstance(reference, str) or not reference.strip()):
            raise ValueError("Invalid source transaction reference")
        row.update(source_system=job["source_system"], source_transaction_id=reference)
        batch = job.get("batch")
        if reference is None and batch is None:
            raise ValueError("Version 2 requires source reference or batch metadata")
        if batch is not None:
            if not isinstance(batch, dict) or set(batch) != {"batch_id", "file_sha256", "ingested_at"}:
                raise ValueError("Invalid batch metadata")
            uuid.UUID(batch["batch_id"])
            if (not isinstance(batch["file_sha256"], str) or len(batch["file_sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in batch["file_sha256"])):
                raise ValueError("Invalid file hash")
            parse_transaction_date(batch["ingested_at"])
    else:
        batch = None
    normalized = make_job(row, source["bucket"], source["key"], "", source["row"],
                          source.get("version"), source.get("etag"), batch=batch)
    normalized["correlation_id"] = job["correlation_id"]
    return normalized


def business_fingerprint(job):
    # Preserve historical v1 frozen-result digests. V2 excludes internal identity
    # and upload metadata; the reference namespace is part of business content.
    excluded = {"source", "correlation_id"}
    if job["schema_version"] == 2:
        excluded |= {"transaction_id", "batch"}
    fields = {k: v for k, v in job.items() if k not in excluded}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def identity_key(job):
    reference = job.get("source_transaction_id")
    return (job["source_system"], job["account_id"], reference) if reference else (job["transaction_id"],)


def queue_deduplication_id(job):
    # Similar rows without a reference remain separate events, even at equal times.
    value = [identity_key(job), business_fingerprint(job)]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def high_risk_event(result):
    return {"schema_version": 1, "event_type": "HIGH_RISK", "transaction_id": result["transaction_id"],
            "account_id": result["account_id"], "score": result["score"],
            "risk_level": result["risk_level"], "correlation_id": result["correlation_id"]}

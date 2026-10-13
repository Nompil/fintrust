"""FIFO consumer: SQL is authoritative; external effects are replayable."""
import json
import hashlib
import os
from datetime import timedelta, datetime, timezone
import boto3
from psycopg2.extras import Json
from .db import get_connection
from .config import AWS_REGION
from .dynamo import put_item, publish_score
from .jobs import business_fingerprint, high_risk_event, parse_job
from .ledger import IdentityConflict, existing_transaction, insert_transaction
from .quarantine import rejection
from .rules import ScoringConfig, evaluate
from .validators import parse_transaction_date
from src.shared.logger import get_logger

logger = get_logger("scoring")
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)


class UnknownAccount(ValueError):
    """A valid job references an account absent from the authoritative ledger."""


class InactiveAccount(UnknownAccount):
    """Account exists but is not active/monitoring."""


def score_transaction(record, velocity=1, config=None, *, duplicate_matches=(), duplicate_evidence=(), velocity_evidence=None, evaluated_at=None):
    result = evaluate(record, velocity, config, duplicate_matches=duplicate_matches,
                      duplicate_evidence=duplicate_evidence, velocity_evidence=velocity_evidence, evaluated_at=evaluated_at)
    return {"account_id": record.get("account_id"),
            "transaction_id": record.get("transaction_id", record.get("tx_id")),
            "tx_id": record.get("transaction_id", record.get("tx_id")), **result,
            "decision": "hold" if result["risk_level"] in {"High", "Medium"} else "approve"}


def persist_score(job, *, commit_hook=None):
    """Serialize per account; commit ledger, risk event and frozen result together.

    Retries use the original result, never rescore against changed configuration
    or history. External writes afterwards can safely repeat without SQL duplicates.
    """
    conn = get_connection()
    digest = business_fingerprint(job)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT account_id FROM accounts WHERE account_id=%s FOR UPDATE", (job["account_id"],))
            if not cur.fetchone():
                raise UnknownAccount("Account no longer exists")
            existing = existing_transaction(cur, job)
            if existing:
                if existing[3] is None:
                    raise IdentityConflict("Transaction ID already exists outside the scoring pipeline")
                if commit_hook:
                    commit_hook(cur, existing[3], True)
                conn.commit()
                return existing[3]
            if commit_hook:
                cur.execute("SELECT status FROM accounts WHERE account_id=%s", (job["account_id"],))
                if cur.fetchone()[0] not in {"active", "monitoring"}:
                    raise InactiveAccount("Account is not open for ingestion")
            insert_transaction(cur, job)
            cfg = ScoringConfig.from_env()
            if commit_hook and cfg != ScoringConfig():
                raise ValueError("Release 1 scoring configuration differs from the frozen rule version")
            when = parse_transaction_date(job["transaction_timestamp"])
            cur.execute("SELECT count(*),min(tx_date),max(tx_date) FROM transactions WHERE account_id=%s AND tx_date BETWEEN %s AND %s",
                        (job["account_id"], when - timedelta(seconds=cfg.velocity_seconds), when))
            velocity, first_seen, last_seen = cur.fetchone()
            velocity_evidence = {"observed_window_start": first_seen.astimezone(timezone.utc).isoformat(), "observed_window_end": last_seen.astimezone(timezone.utc).isoformat()}
            matches = []
            duplicate_evidence = []
            if job.get("source_transaction_id") and job["merchant"] and job["transaction_type"] == "debit":
                cur.execute("""SELECT tx_id::text,tx_date,source_transaction_id FROM transactions
                    WHERE account_id=%s AND merchant=%s AND amount=%s AND currency=%s
                      AND tx_type='debit' AND tx_id<>%s AND source_system=%s
                      AND source_transaction_id IS NOT NULL AND source_transaction_id<>%s
                      AND tx_date BETWEEN %s AND %s ORDER BY tx_date,tx_id LIMIT 20""",
                    (job["account_id"], job["merchant"], job["amount"], job["currency"],
                     job["transaction_id"], job["source_system"], job["source_transaction_id"],
                     when - timedelta(seconds=cfg.duplicate_charge_seconds),
                     when + timedelta(seconds=cfg.duplicate_charge_seconds)))
                matching_rows = cur.fetchall()
                matches = [r[0] for r in matching_rows]
                duplicate_evidence = [{"tx_id": r[0], "tx_date": r[1].astimezone(timezone.utc).isoformat(),
                    "source_transaction_id": r[2], "seconds_apart": str(abs((when-r[1]).total_seconds()))} for r in matching_rows]
            result = score_transaction(job, velocity, cfg, duplicate_matches=matches,
                duplicate_evidence=duplicate_evidence, velocity_evidence=velocity_evidence,
                evaluated_at=datetime.now(timezone.utc).isoformat())
            result.update(source=job["source"], batch=job.get("batch"),
                          correlation_id=job["correlation_id"],
                          transaction_timestamp=job["transaction_timestamp"],
                          scoring_config={k: str(v) for k, v in cfg.__dict__.items()})
            cur.execute("INSERT INTO risk_events(tx_id,risk_score,reason) VALUES(%s,%s,%s) RETURNING risk_event_id",
                        (job["transaction_id"], result["score"],
                         ", ".join(r["rule"] for r in result["triggered_rules"]) or "No rules triggered"))
            result["risk_event_id"] = cur.fetchone()[0]
            cur.execute("INSERT INTO processed_transactions(tx_id,fingerprint,result) VALUES(%s,%s,%s)",
                        (job["transaction_id"], digest, Json(result)))
            if commit_hook:
                commit_hook(cur, result, False)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_job(payload):
    candidate = json.loads(payload) if isinstance(payload, str) else payload
    if isinstance(candidate, dict) and candidate.get("schema_version") == 3:
        from .release_workflow import process_envelope
        return process_envelope(candidate)
    job = parse_job(payload)
    delivery = os.getenv("ALERT_DELIVERY_MODE", "direct")
    if delivery not in {"direct", "stream"}:
        raise ValueError("Invalid ALERT_DELIVERY_MODE")
    if os.getenv("AWS_EXECUTION_ENV") and delivery != "stream":
        raise RuntimeError("AWS scoring requires stream alert delivery")
    try:
        result = persist_score(job)
    except (UnknownAccount, IdentityConflict) as error:
        if delivery != "stream":
            raise
        source = job["source"]
        row = {"transaction_id": job["transaction_id"], "account_id": job["account_id"],
               "amount": job["amount"], "currency": job["currency"],
               "tx_date": job["transaction_timestamp"], "tx_type": job["transaction_type"],
               "country": job["country"], "merchant": job["merchant"],
               "source_transaction_id": job.get("source_transaction_id"),
               "source_system": job.get("source_system")}
        code = "UNKNOWN_ACCOUNT" if isinstance(error, UnknownAccount) else "TRANSACTION_IDENTITY_CONFLICT"
        rejected = rejection(code, "unknown account" if code == "UNKNOWN_ACCOUNT" else str(error), row,
                             bucket=source["bucket"], key=source["key"], row_number=source["row"],
                             batch=job.get("batch"), version=source.get("version"), etag=source.get("etag"))
        s3.put_object(Bucket=os.environ["QUARANTINE_BUCKET"],
                      Key="quarantine/accounts/" + job["transaction_id"] + "-" + business_fingerprint(job) + ".jsonl",
                      Body=(json.dumps(rejected) + "\n").encode(), ContentType="application/x-ndjson")
        return {"status": "QUARANTINED", "transaction_id": job["transaction_id"]}
    if (result["transaction_id"] != job["transaction_id"] or
            (result.get("source") is not None and result["source"] != job["source"])):
        source = job["source"]
        row = {"transaction_id": job["transaction_id"], "source_transaction_id": job.get("source_transaction_id"),
               "source_system": job.get("source_system"), "account_id": job["account_id"]}
        duplicate = rejection("DUPLICATE_TRANSACTION", "Reused canonical ledger result", row,
            bucket=source["bucket"], key=source["key"], row_number=source["row"],
            batch=job.get("batch"), version=source.get("version"), etag=source.get("etag"))
        duplicate["canonical_transaction_id"] = result["transaction_id"]
        receipt = hashlib.sha256(json.dumps([job["transaction_id"], source], sort_keys=True).encode()).hexdigest()
        s3.put_object(Bucket=os.getenv("QUARANTINE_BUCKET", source["bucket"]),
                      Key="quarantine/accounts/duplicates/" + receipt + ".jsonl",
                      Body=(json.dumps(duplicate) + "\n").encode(), ContentType="application/x-ndjson")
    # TX#UUID keys coexist with legacy YYYY-MM-DD summaries, without overwriting
    # them. Each event item is a rebuildable projection of the immutable SQL result.
    (publish_score if delivery == "stream" else put_item)(os.environ["DYNAMODB_TABLE"], {
        **result, "score_date": "TX#" + result["transaction_id"], "risk_score": result["score"]})
    if result["risk_level"] == "High" and delivery == "direct":
        response = lambda_client.invoke(FunctionName=os.environ["ALERT_FUNCTION_ARN"],
            InvocationType="RequestResponse", Payload=json.dumps(high_risk_event(result)).encode())
        stream = response["Payload"]
        try:
            reply = json.loads(stream.read())
        finally:
            stream.close()
        if response.get("FunctionError") or reply.get("status") != "SENT":
            raise RuntimeError("Alert delivery has not completed")
    logger.info(json.dumps({"event": "transaction_processed", "transaction_id": job["transaction_id"],
                            "correlation_id": job["correlation_id"], "risk_level": result["risk_level"]}))
    return result


def lambda_handler(event, context):
    records = event.get("Records", [])
    if not records:
        raise ValueError("SQS event must contain records")
    failures = []
    # Stop at the first FIFO failure and return all unprocessed IDs too.
    for index, record in enumerate(records):
        try:
            process_job(record["body"])
        except Exception as exc:
            logger.error(json.dumps({"event": "scoring_failed", "error_type": type(exc).__name__,
                                    "message_id": record["messageId"]}))
            failures = [{"itemIdentifier": r["messageId"]} for r in records[index:]]
            break
    return {"batchItemFailures": failures}

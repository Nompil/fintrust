"""FIFO consumer: SQL is authoritative; external effects are replayable."""
import json
import os
from datetime import datetime, timedelta, timezone
import boto3
from psycopg2.extras import Json
from .db import get_connection
from .config import AWS_REGION
from .dynamo import put_item, publish_score
from .jobs import business_fingerprint, high_risk_event, parse_job
from .rules import ScoringConfig, evaluate
from .validators import parse_transaction_date
from src.shared.logger import get_logger

logger = get_logger("scoring")
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)


class UnknownAccount(ValueError):
    """A valid job references an account absent from the authoritative ledger."""


def score_transaction(record, velocity=1, config=None):
    result = evaluate(record, velocity, config)
    return {"account_id": record.get("account_id"),
            "transaction_id": record.get("transaction_id", record.get("tx_id")),
            "tx_id": record.get("transaction_id", record.get("tx_id")), **result,
            "decision": "hold" if result["risk_level"] in {"High", "Medium"} else "approve"}


def persist_score(job):
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
            cur.execute("SELECT fingerprint, result FROM processed_transactions WHERE tx_id=%s", (job["transaction_id"],))
            existing = cur.fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError("Transaction ID conflicts with accepted financial data")
                conn.commit()
                return existing[1]
            cur.execute("""INSERT INTO transactions
                (tx_id,account_id,amount,currency,merchant,tx_date,tx_type,cross_border,raw_file)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tx_id) DO NOTHING
                RETURNING tx_id""", (job["transaction_id"], job["account_id"], job["amount"],
                job["currency"], job["merchant"] or None, job["transaction_timestamp"],
                job["transaction_type"], job["country"] != "ZA", job["source"]["key"]))
            if not cur.fetchone():
                raise ValueError("Transaction ID already exists outside the scoring pipeline")
            cfg = ScoringConfig.from_env()
            when = parse_transaction_date(job["transaction_timestamp"])
            cur.execute("SELECT count(*) FROM transactions WHERE account_id=%s AND tx_date BETWEEN %s AND %s",
                        (job["account_id"], when - timedelta(seconds=cfg.velocity_seconds), when))
            result = score_transaction(job, cur.fetchone()[0], cfg)
            result.update(correlation_id=job["correlation_id"],
                          transaction_timestamp=job["transaction_timestamp"],
                          scoring_config={k: str(v) for k, v in cfg.__dict__.items()})
            cur.execute("INSERT INTO risk_events(tx_id,risk_score,reason) VALUES(%s,%s,%s) RETURNING risk_event_id",
                        (job["transaction_id"], result["score"],
                         ", ".join(r["rule"] for r in result["triggered_rules"]) or "No rules triggered"))
            result["risk_event_id"] = cur.fetchone()[0]
            cur.execute("INSERT INTO processed_transactions(tx_id,fingerprint,result) VALUES(%s,%s,%s)",
                        (job["transaction_id"], digest, Json(result)))
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_job(payload):
    job = parse_job(payload)
    delivery = os.getenv("ALERT_DELIVERY_MODE", "direct")
    if delivery not in {"direct", "stream"}:
        raise ValueError("Invalid ALERT_DELIVERY_MODE")
    if os.getenv("AWS_EXECUTION_ENV") and delivery != "stream":
        raise RuntimeError("AWS scoring requires stream alert delivery")
    try:
        result = persist_score(job)
    except UnknownAccount:
        if delivery != "stream":
            raise
        rejected = {k: job[k] for k in ("transaction_id", "account_id", "amount", "currency",
                    "transaction_timestamp", "transaction_type", "country", "source", "correlation_id")}
        rejected.update(error="unknown account", quarantined_at=datetime.now(timezone.utc).isoformat())
        s3.put_object(Bucket=os.environ["QUARANTINE_BUCKET"],
                      Key="quarantine/accounts/" + business_fingerprint(job) + ".jsonl",
                      Body=(json.dumps(rejected) + "\n").encode(), ContentType="application/x-ndjson")
        return {"status": "QUARANTINED", "transaction_id": job["transaction_id"]}
    # TX#UUID keys coexist with legacy YYYY-MM-DD summaries, without overwriting
    # them. Each event item is a rebuildable projection of the immutable SQL result.
    (publish_score if delivery == "stream" else put_item)(os.environ["DYNAMODB_TABLE"], {
        **result, "score_date": "TX#" + job["transaction_id"], "risk_score": result["score"]})
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

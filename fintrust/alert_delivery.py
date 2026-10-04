"""DynamoDB stream consumer with durable, conservative SES delivery claims.

SES cannot guarantee exactly-once sending. Never automatically reclaim SENDING
or UNKNOWN: an operator must reconcile those attempts with provider evidence.
"""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.config import Config
from botocore.exceptions import ClientError
from src.shared.logger import get_logger

dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses", config=Config(retries={"total_max_attempts": 1},
                                      connect_timeout=5, read_timeout=10))
logger = get_logger("alert")


def deliver(account_id, transaction_id):
    account_id, transaction_id = str(uuid.UUID(account_id)), str(uuid.UUID(transaction_id))
    sender, recipient = os.environ["SES_SENDER"], os.environ["SES_RECIPIENT"]
    table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
    result = table.get_item(Key={"account_id": account_id, "score_date": "TX#" + transaction_id},
                            ConsistentRead=True).get("Item")
    if not result or result.get("transaction_id") != transaction_id or result.get("risk_level") != "High":
        raise ValueError("No authoritative high-risk projection")
    key = {"account_id": account_id, "score_date": "ALERT#" + transaction_id}
    attempt = str(uuid.uuid4())
    try:
        table.update_item(Key=key,
            UpdateExpression="SET #state=:sending, attempt_id=:attempt, updated_at=:now, risk_event_id=:risk",
            ConditionExpression="attribute_not_exists(#state) OR #state=:failed",
            ExpressionAttributeNames={"#state": "delivery_state"},
            ExpressionAttributeValues={":sending": "SENDING", ":failed": "FAILED", ":attempt": attempt,
                ":now": datetime.now(timezone.utc).isoformat(), ":risk": result["risk_event_id"]})
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        existing = table.get_item(Key=key, ConsistentRead=True).get("Item", {})
        if existing.get("delivery_state") == "SENT":
            return {"status": "SENT", "transaction_id": transaction_id}
        raise RuntimeError("Alert attempt requires delivery reconciliation") from exc

    def finish(state, message_id=""):
        table.update_item(Key=key,
            UpdateExpression="SET #state=:state, provider_message_id=:message, updated_at=:now",
            ConditionExpression="attempt_id=:attempt AND #state=:sending",
            ExpressionAttributeNames={"#state": "delivery_state"},
            ExpressionAttributeValues={":state": state, ":message": message_id, ":attempt": attempt,
                ":sending": "SENDING", ":now": datetime.now(timezone.utc).isoformat()})

    try:
        response = ses.send_email(Source=sender, Destination={"ToAddresses": [recipient]},
            Message={"Subject": {"Data": "FinTrust high-risk transaction"},
                     "Body": {"Text": {"Data": f"High risk transaction {transaction_id}: score {result['score']}"}}})
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500)
        finish("FAILED" if 400 <= status < 500 else "UNKNOWN")
        raise
    except Exception:
        finish("UNKNOWN")
        raise
    # A failed state write deliberately leaves SENDING; retry must not resend.
    finish("SENT", response["MessageId"])
    return {"status": "SENT", "transaction_id": transaction_id}


def lambda_handler(event, context):
    records = event.get("Records", [])
    if not records:
        raise ValueError("DynamoDB event must contain records")
    decoder = TypeDeserializer()
    for record in records:
        sequence = record["dynamodb"]["SequenceNumber"]
        try:
            if record.get("eventName") not in {"INSERT", "MODIFY"}:
                continue
            item = {k: decoder.deserialize(v) for k, v in record["dynamodb"]["NewImage"].items()}
            if not item.get("score_date", "").startswith("TX#") or item.get("risk_level") != "High":
                continue
            deliver(item["account_id"], item["score_date"][3:])
        except Exception as exc:
            logger.error(json.dumps({"event": "alert_delivery_failed", "sequence_number": sequence,
                                     "error_type": type(exc).__name__}))
            # Lambda checkpoints at this sequence and replays it and later records.
            return {"batchItemFailures": [{"itemIdentifier": sequence}]}
    return {"batchItemFailures": []}

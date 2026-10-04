"""SES delivery with explicit state and conservative ambiguous-outcome handling.

SES has no idempotency token. Commit SENDING before sending; a crash or uncertain
response requires reconciliation instead of blindly resending and duplicating mail.
"""
import json
import os
import uuid
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from .db import get_connection

# SDK retries could duplicate a request whose first response was lost.
ses = boto3.client("ses", config=Config(retries={"total_max_attempts": 1},
                                      connect_timeout=5, read_timeout=10))


def _update(alert_id, state, message_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE alerts SET delivery_state=%s, provider_message_id=%s,
                sent_at=CASE WHEN %s='SENT' THEN NOW() ELSE NULL END WHERE alert_id=%s""",
                (state, message_id, state, alert_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def send_alert(event):
    if event.get("schema_version") != 1 or event.get("event_type") != "HIGH_RISK":
        raise ValueError("Unsupported alert event")
    identity = str(uuid.UUID(event["transaction_id"]))
    # Fail configuration before claiming an attempt.
    sender, recipient = os.environ["SES_SENDER"], os.environ["SES_RECIPIENT"]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Authoritative score/account come from SQL, not the caller.
            cur.execute("SELECT result FROM processed_transactions WHERE tx_id=%s FOR UPDATE", (identity,))
            row = cur.fetchone()
            if not row or row[0]["risk_level"] != "High":
                raise ValueError("No authoritative high-risk result")
            result = row[0]
            cur.execute("""INSERT INTO alerts(risk_event_id,severity,message,delivery_key,delivery_state)
                VALUES(%s,'High',%s,%s,'PENDING') ON CONFLICT (delivery_key) DO NOTHING""",
                (result["risk_event_id"], f"High risk transaction {identity}: score {result['score']}",
                 result["risk_event_id"]))
            cur.execute("SELECT alert_id,delivery_state,message FROM alerts WHERE delivery_key=%s FOR UPDATE",
                        (result["risk_event_id"],))
            alert_id, state, message = cur.fetchone()
            if state == "SENT":
                conn.commit()
                return {"status": "SENT", "alert_id": alert_id}
            if state in {"SENDING", "UNKNOWN"}:
                raise RuntimeError("Ambiguous alert attempt requires delivery reconciliation")
            cur.execute("UPDATE alerts SET delivery_state='SENDING' WHERE alert_id=%s", (alert_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    try:
        response = ses.send_email(Source=sender, Destination={"ToAddresses": [recipient]},
            Message={"Subject": {"Data": "FinTrust high-risk transaction"},
                     "Body": {"Text": {"Data": message}}})
    except ClientError as exc:
        code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500)
        _update(alert_id, "FAILED" if 400 <= code < 500 else "UNKNOWN")
        raise
    except Exception:
        _update(alert_id, "UNKNOWN")
        raise
    _update(alert_id, "SENT", response["MessageId"])
    return {"status": "SENT", "alert_id": alert_id}


def lambda_handler(event, context):
    return send_alert(json.loads(event) if isinstance(event, str) else event)

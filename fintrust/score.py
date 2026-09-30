"""Pure scoring prototype; persistence and SQS integration are not implemented."""
from .validators import classify_risk, compute_risk_score


def score_transaction(record: dict) -> dict:
    score = compute_risk_score(record)
    risk_level = classify_risk(score)
    return {
        "account_id": record.get("account_id"),
        "tx_id": record.get("tx_id"),
        "score": score,
        "risk_level": risk_level,
        "decision": "hold" if risk_level in {"High", "Medium"} else "approve",
    }


def lambda_handler(event, context):
    raise NotImplementedError("FIFO scoring and persistence are a later capstone milestone")

from .validators import classify_risk, compute_risk_score


def score_transaction(record: dict) -> dict:
    score = compute_risk_score(record)
    risk_level = classify_risk(score)
    return {
        "account_id": record.get("account_id"),
        "transaction_id": record.get("transaction_id"),
        "score": score,
        "risk_level": risk_level,
        "decision": "hold" if risk_level in {"High", "Medium"} else "approve",
    }


def lambda_handler(event, context):
    records = event.get("Records", [])
    results = []
    for item in records:
        payload = item.get("body", {}) if isinstance(item.get("body"), dict) else {}
        results.append(score_transaction(payload))
    return {"processed": len(results), "results": results}

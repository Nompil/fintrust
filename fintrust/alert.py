def send_alert(account_id: str, score: int, risk_level: str) -> dict:
    raise NotImplementedError("SES alert delivery is a later capstone milestone")


def lambda_handler(event, context):
    items = event.get("Records", [])
    results = []
    for item in items:
        payload = item.get("body", {}) if isinstance(item.get("body"), dict) else {}
        results.append(send_alert(payload.get("account_id", "unknown"), payload.get("score", 0), payload.get("risk_level", "Low")))
    return {"alerts": results}

from .db import run_query


def get_transactions(account_id: str | None = None):
    if account_id:
        return run_query(
            "SELECT * FROM transactions WHERE account_id = %s ORDER BY tx_date DESC LIMIT 50;",
            (account_id,),
        )
    return run_query("SELECT * FROM transactions ORDER BY tx_date DESC LIMIT 50;")


def get_insights(account_id: str | None = None):
    if account_id:
        return run_query(
            "SELECT account_id, COUNT(*) AS total_transactions, AVG(risk_score) AS avg_risk FROM transactions WHERE account_id = %s GROUP BY account_id;",
            (account_id,),
        )
    return run_query(
        "SELECT account_id, COUNT(*) AS total_transactions, AVG(risk_score) AS avg_risk FROM transactions GROUP BY account_id ORDER BY avg_risk DESC;"
    )


def lambda_handler(event, context):
    account_id = (event or {}).get("queryStringParameters", {}).get("account_id")
    return {"transactions": get_transactions(account_id), "insights": get_insights(account_id)}

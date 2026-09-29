def generate_monthly_report() -> dict:
    return {
        "month": "current",
        "summary": {
            "high_risk_count": 0,
            "total_volume": 0,
            "flagged_accounts": 0,
        },
        "status": "generated",
    }


def lambda_handler(event, context):
    return generate_monthly_report()

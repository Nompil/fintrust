from fintrust.score import score_transaction


def test_score_transaction_returns_risk_information():
    payload = {
        "account_id": "ACC-1001",
        "transaction_id": "TXN-321",
        "amount": "120000",
        "transaction_type": "transfer",
        "channel": "online",
        "country": "US",
        "merchant_name": "HighRisk Shop",
    }

    result = score_transaction(payload)
    assert result["account_id"] == "ACC-1001"
    assert result["transaction_id"] == "TXN-321"
    assert result["decision"] in {"hold", "approve"}
    assert result["score"] >= 0

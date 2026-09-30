from fintrust.score import score_transaction


def test_score_transaction_returns_risk_information():
    payload = {
        "account_id": "20000000-0000-4000-8000-000000000001",
        "tx_id": "TXN-321",
        "amount": "120000",
        "tx_type": "transfer",
        "channel": "online",
        "cross_border": True,
        "merchant": "HighRisk Shop",
    }

    result = score_transaction(payload)
    assert result["account_id"] == "20000000-0000-4000-8000-000000000001"
    assert result["tx_id"] == "TXN-321"
    assert result["decision"] in {"hold", "approve"}
    assert result["score"] >= 0

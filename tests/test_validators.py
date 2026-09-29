from fintrust.validators import classify_risk, compute_risk_score, validate_transaction_record


def test_validate_transaction_record_accepts_valid_record():
    record = {
        "account_id": "ACC-1001",
        "transaction_id": "TXN-010",
        "tx_date": "2026-09-20",
        "amount": "25000",
        "transaction_type": "debit",
        "channel": "mobile",
        "currency": "ZAR",
    }
    valid, error = validate_transaction_record(record)
    assert valid is True
    assert error is None


def test_validate_transaction_record_rejects_negative_amount():
    record = {
        "account_id": "ACC-1001",
        "transaction_id": "TXN-011",
        "tx_date": "2026-09-20",
        "amount": "-1",
        "transaction_type": "debit",
        "channel": "mobile",
    }
    valid, error = validate_transaction_record(record)
    assert valid is False
    assert "greater than zero" in error


def test_compute_risk_score_and_classification():
    record = {
        "amount": "60000",
        "transaction_type": "withdrawal",
        "channel": "online",
        "country": "US",
        "merchant_name": "HighRisk Shop",
    }
    score = compute_risk_score(record)
    assert score >= 60
    assert classify_risk(score) in {"Medium", "High"}

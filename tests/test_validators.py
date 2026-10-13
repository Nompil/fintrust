from fintrust.validators import validate_transaction_record
from fintrust.rules import classify_risk, compute_risk_score


def test_validate_transaction_record_accepts_valid_record():
    record = {
        "account_id": "20000000-0000-4000-8000-000000000001",
        "tx_id": "30000000-0000-4000-8000-000000000010",
        "tx_date": "2026-09-20",
        "amount": "25000",
        "tx_type": "debit",
        "channel": "mobile",
        "currency": "ZAR",
    }
    valid, error = validate_transaction_record(record)
    assert valid is True
    assert error is None


def test_validate_transaction_record_rejects_negative_amount():
    record = {
        "account_id": "20000000-0000-4000-8000-000000000001",
        "tx_id": "30000000-0000-4000-8000-000000000011",
        "tx_date": "2026-09-20",
        "amount": "-1",
        "tx_type": "debit",
        "channel": "mobile",
    }
    valid, error = validate_transaction_record(record)
    assert valid is False
    assert "greater than zero" in error


def test_compute_risk_score_and_classification():
    record = {
        "amount": "60000",
        "tx_type": "transfer",
        "channel": "online",
        "cross_border": True,
        "merchant": "HighRisk Shop",
    }
    score = compute_risk_score(record)
    assert score == 30  # amount band 15 + explicit cross-border 15; retired synthetic signals contribute zero
    assert classify_risk(score) == "Medium"

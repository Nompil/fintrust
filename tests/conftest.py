import pytest


@pytest.fixture
def sample_transaction():
    return {
        "account_id": "ACC-1001",
        "transaction_id": "TXN-001",
        "tx_date": "2026-09-20",
        "amount": "25000",
        "transaction_type": "debit",
        "channel": "mobile",
        "merchant_name": "HighRisk Shop",
        "country": "ZA",
        "currency": "ZAR",
    }

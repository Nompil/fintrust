import os

import pytest

# Test imports must never discover credentials from a developer's AWS profile.
os.environ.update(
    AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
    AWS_SESSION_TOKEN="testing", AWS_DEFAULT_REGION="af-south-1",
    AWS_EC2_METADATA_DISABLED="true", AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true",
)
for _name in list(os.environ):
    if _name.startswith("AWS_ENDPOINT_URL"):
        os.environ.pop(_name)


@pytest.fixture
def sample_transaction():
    return {
        "account_id": "20000000-0000-4000-8000-000000000001",
        "tx_id": "TXN-001",
        "tx_date": "2026-09-20",
        "amount": "25000",
        "tx_type": "debit",
        "channel": "mobile",
        "merchant": "HighRisk Shop",
        "country": "ZA",
        "currency": "ZAR",
    }

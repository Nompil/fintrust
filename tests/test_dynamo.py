import boto3
from moto import mock_aws

from fintrust import dynamo


@mock_aws
def test_risk_scores_put_get_and_query(monkeypatch):
    resource = boto3.resource(
        "dynamodb",
        region_name="af-south-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    client = resource.meta.client
    client.create_table(
        TableName="risk_scores",
        AttributeDefinitions=[
            {"AttributeName": "account_id", "AttributeType": "S"},
            {"AttributeName": "score_date", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "account_id", "KeyType": "HASH"},
            {"AttributeName": "score_date", "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    monkeypatch.setattr(dynamo, "dynamodb", resource)
    item = {
        "account_id": "acc-test-001",
        "score_date": "2026-09-28",
        "risk_score": 75,
        "ttl": 1790553600,
    }

    assert dynamo.put_item("risk_scores", item) == item
    assert dynamo.get_item(
        "risk_scores",
        {"account_id": "acc-test-001", "score_date": "2026-09-28"},
    ) == item
    assert dynamo.query_by_account("risk_scores", "acc-test-001") == [item]

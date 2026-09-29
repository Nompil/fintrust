import os

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "af-south-1")
TABLE_NAME = os.getenv("FINTRUST_DDB_TABLE", "risk_scores")
dynamodb = boto3.client("dynamodb", region_name=REGION)


def ensure_table() -> None:
    try:
        dynamodb.describe_table(TableName=TABLE_NAME)
        print(f"DynamoDB table {TABLE_NAME} already exists")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        dynamodb.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[
                {"AttributeName": "account_id", "AttributeType": "S"},
                {"AttributeName": "score_date", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "account_id", "KeyType": "HASH"},
                {"AttributeName": "score_date", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
            Tags=[
                {"Key": "Project", "Value": "FinTrust"},
                {"Key": "Environment", "Value": "dev"},
            ],
        )
        print(f"Creating DynamoDB table {TABLE_NAME}")

    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=TABLE_NAME)
    ttl = dynamodb.describe_time_to_live(TableName=TABLE_NAME)["TimeToLiveDescription"]
    if ttl["TimeToLiveStatus"] == "DISABLED":
        dynamodb.update_time_to_live(
            TableName=TABLE_NAME,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
    print(f"DynamoDB table {TABLE_NAME} is active with TTL enabled")


if __name__ == "__main__":
    ensure_table()

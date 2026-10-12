import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from .config import AWS_REGION

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def publish_score(table_name, item):
    """Insert once so queue replays cannot emit duplicate stream events."""
    table = dynamodb.Table(table_name)
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(account_id)")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        existing = table.get_item(Key={k: item[k] for k in ("account_id", "score_date")},
                                  ConsistentRead=True).get("Item")
        if existing != item:
            raise ValueError("Score projection conflicts with the immutable ledger result") from exc
    return item


def put_item(table_name: str, item: dict):
    table = dynamodb.Table(table_name)
    table.put_item(Item=item)
    return item


def get_item(table_name: str, key: dict):
    table = dynamodb.Table(table_name)
    return table.get_item(Key=key).get("Item")


def query_by_account(table_name: str, account_id: str, score_date: str | None = None):
    table = dynamodb.Table(table_name)
    condition = Key("account_id").eq(account_id)
    if score_date:
        condition &= Key("score_date").eq(score_date)
    items = []
    request = {"KeyConditionExpression": condition}
    while True:
        response = table.query(**request)
        items.extend(response.get("Items", []))
        if not response.get("LastEvaluatedKey"):
            return items
        request["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def get_transaction_score(table_name, account_id, transaction_id):
    """Exact event lookup; legacy daily summary keys remain separately readable."""
    return get_item(table_name, {"account_id": account_id, "score_date": "TX#" + transaction_id})

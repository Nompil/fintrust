import boto3
from boto3.dynamodb.conditions import Key

from .config import AWS_REGION

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


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
    return table.query(
        KeyConditionExpression=condition
    ).get("Items", [])

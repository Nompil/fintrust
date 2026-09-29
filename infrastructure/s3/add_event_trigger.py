import json
import os

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "af-south-1")
BUCKET = os.getenv("FINTRUST_INGEST_BUCKET", "fintrust-ingest-dev")
FUNCTION_NAME = os.getenv("FINTRUST_INGEST_FUNCTION", "fintrust-ingest")
s3 = boto3.client("s3", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)


def add_s3_trigger() -> None:
    account_id = sts.get_caller_identity()["Account"]
    function = lam.get_function(FunctionName=FUNCTION_NAME)["Configuration"]
    function_arn = function["FunctionArn"]

    try:
        policy = json.loads(lam.get_policy(FunctionName=FUNCTION_NAME)["Policy"])
        permission_exists = any(
            statement.get("Sid") == "s3-ingest-invoke"
            for statement in policy.get("Statement", [])
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        permission_exists = False

    if not permission_exists:
        lam.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="s3-ingest-invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET}",
            SourceAccount=account_id,
        )

    current = s3.get_bucket_notification_configuration(Bucket=BUCKET)
    configurations = current.get("LambdaFunctionConfigurations", [])
    configurations = [
        item for item in configurations
        if item.get("Id") != "fintrust-ingest-csv"
        and item.get("LambdaFunctionArn") != function_arn
    ]
    configurations.append({
        "Id": "fintrust-ingest-csv",
        "LambdaFunctionArn": function_arn,
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {"Key": {"FilterRules": [
            {"Name": "prefix", "Value": "raw/"},
            {"Name": "suffix", "Value": ".csv"},
        ]}},
    })

    notification = {"LambdaFunctionConfigurations": configurations}
    for key in ("TopicConfigurations", "QueueConfigurations", "EventBridgeConfiguration"):
        if key in current:
            notification[key] = current[key]
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET,
        NotificationConfiguration=notification,
    )
    print(f"Configured {BUCKET}/raw/*.csv to invoke {FUNCTION_NAME}")


if __name__ == "__main__":
    add_s3_trigger()

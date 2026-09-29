import json
import os

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "af-south-1")
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
iam = boto3.client("iam")
logs = boto3.client("logs", region_name=REGION)
TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}


def logs_policy(function_name: str) -> dict:
    log_group_arn = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:/aws/lambda/{function_name}:*"
    return {
        "Effect": "Allow",
        "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": log_group_arn,
    }


def ensure_role(role_name: str, function_name: str, statements: list[dict]) -> str:
    log_group = f"/aws/lambda/{function_name}"
    try:
        logs.create_log_group(logGroupName=log_group)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
            raise
    logs.put_retention_policy(logGroupName=log_group, retentionInDays=30)

    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description=f"Least-privilege execution role for {function_name}",
            Tags=[{"Key": "Project", "Value": "FinTrust"}],
        )
        arn = response["Role"]["Arn"]
        print(f"Created role {role_name}")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        print(f"Updating existing role {role_name}")

    policy = {
        "Version": "2012-10-17",
        "Statement": statements + [logs_policy(function_name)],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{function_name}-permissions",
        PolicyDocument=json.dumps(policy),
    )
    return arn


def create_roles() -> None:
    bucket = os.getenv("FINTRUST_INGEST_BUCKET", "fintrust-ingest-dev")
    table = os.getenv("FINTRUST_DDB_TABLE", "risk_scores")
    queue_arn = os.getenv("FINTRUST_SCORE_QUEUE_ARN", f"arn:aws:sqs:{REGION}:{ACCOUNT_ID}:fintrust-score.fifo")
    params_arn = f"arn:aws:ssm:{REGION}:{ACCOUNT_ID}:parameter/fintrust/dev/*"
    table_arn = f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/{table}"

    roles = [
        (
            "fintrust-lambda-ingest-role",
            "fintrust-ingest",
            [
                {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"],
                 "Resource": [f"arn:aws:s3:::{bucket}/raw/*", f"arn:aws:s3:::{bucket}/quarantine/*"]},
                {"Effect": "Allow", "Action": ["ssm:GetParameter"], "Resource": params_arn},
            ],
        ),
        (
            "fintrust-lambda-score-role",
            "fintrust-score",
            [
                {"Effect": "Allow", "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], "Resource": queue_arn},
                {"Effect": "Allow", "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"], "Resource": table_arn},
                {"Effect": "Allow", "Action": ["ssm:GetParameter"], "Resource": params_arn},
            ],
        ),
        (
            "fintrust-lambda-alert-role",
            "fintrust-alert",
            [
                {"Effect": "Allow", "Action": ["ses:SendEmail", "ses:SendRawEmail"],
                 "Resource": f"arn:aws:ses:{REGION}:{ACCOUNT_ID}:identity/*"},
            ],
        ),
        (
            "fintrust-lambda-query-role",
            "fintrust-query",
            [
                {"Effect": "Allow", "Action": ["dynamodb:GetItem", "dynamodb:Query"], "Resource": table_arn},
                {"Effect": "Allow", "Action": ["ssm:GetParameter"], "Resource": params_arn},
            ],
        ),
        (
            "fintrust-lambda-report-role",
            "fintrust-report",
            [
                {"Effect": "Allow", "Action": ["s3:PutObject"],
                 "Resource": f"arn:aws:s3:::{os.getenv('FINTRUST_REPORT_BUCKET', bucket)}/reports/*"},
                {"Effect": "Allow", "Action": ["ssm:GetParameter"], "Resource": params_arn},
            ],
        ),
    ]

    for role_name, function_name, statements in roles:
        arn = ensure_role(role_name, function_name, statements)
        print(f"{role_name}: {arn}")


if __name__ == "__main__":
    create_roles()

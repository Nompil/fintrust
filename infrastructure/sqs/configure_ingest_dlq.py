import os

import boto3

REGION = os.getenv("AWS_REGION", "af-south-1")
QUEUE_NAME = os.getenv("FINTRUST_INGEST_DLQ", "fintrust-ingest-dlq")
FUNCTION_NAME = os.getenv("FINTRUST_INGEST_FUNCTION", "fintrust-ingest")
sqs = boto3.client("sqs", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)


def configure_dlq() -> None:
    queue_url = sqs.create_queue(
        QueueName=QUEUE_NAME,
        Attributes={"MessageRetentionPeriod": "1209600"},
        tags={"Project": "FinTrust", "Environment": "dev"},
    )["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["QueueArn"],
    )["Attributes"]["QueueArn"]

    lambda_client.update_function_configuration(
        FunctionName=FUNCTION_NAME,
        DeadLetterConfig={"TargetArn": queue_arn},
    )
    lambda_client.put_function_event_invoke_config(
        FunctionName=FUNCTION_NAME,
        MaximumRetryAttempts=2,
        MaximumEventAgeInSeconds=3600,
    )
    print(f"Configured {QUEUE_NAME} as the failure queue for {FUNCTION_NAME}")


if __name__ == "__main__":
    configure_dlq()

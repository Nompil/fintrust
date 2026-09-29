import json
import os

import boto3

REGION = os.getenv("AWS_REGION", "af-south-1")
QUEUE_NAME = os.getenv("FINTRUST_INGEST_DLQ", "fintrust-ingest-dlq")
FUNCTION_NAME = os.getenv("FINTRUST_INGEST_FUNCTION", "fintrust-ingest")
sqs = boto3.client("sqs", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)


def replay_messages() -> int:
    queue_url = sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
    replayed = 0
    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=10,
            VisibilityTimeout=60,
        )
        messages = response.get("Messages", [])
        if not messages:
            break

        for message in messages:
            event = json.loads(message["Body"])
            result = lambda_client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType="Event",
                Payload=json.dumps(event).encode("utf-8"),
            )
            if result["StatusCode"] != 202:
                print("Lambda did not accept a replay; leaving the DLQ message for later.")
                break
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )
            replayed += 1
    print(f"Re-enqueued {replayed} ingest event(s)")
    return replayed


if __name__ == "__main__":
    replay_messages()

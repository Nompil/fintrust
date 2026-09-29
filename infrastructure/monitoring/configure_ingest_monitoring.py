import os

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "af-south-1")
FUNCTION_NAME = os.getenv("FINTRUST_INGEST_FUNCTION", "fintrust-ingest")
DLQ_NAME = os.getenv("FINTRUST_INGEST_DLQ", "fintrust-ingest-dlq")
LOG_GROUP = f"/aws/lambda/{FUNCTION_NAME}"
NAMESPACE = "FinTrust/ETL"
logs = boto3.client("logs", region_name=REGION)
cloudwatch = boto3.client("cloudwatch", region_name=REGION)


def configure_monitoring() -> None:
    try:
        logs.create_log_group(logGroupName=LOG_GROUP)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
            raise

    logs.put_metric_filter(
        logGroupName=LOG_GROUP,
        filterName="ingest-files-over-quarantine-threshold",
        filterPattern='{ $.event = "ingest_complete" && $.quarantine_rate_percent > 5 }',
        metricTransformations=[{
            "metricName": "FilesOverQuarantineThreshold",
            "metricNamespace": NAMESPACE,
            "metricValue": "1",
            "defaultValue": 0,
        }],
    )
    cloudwatch.put_metric_alarm(
        AlarmName="fintrust-ingest-quarantine-rate-high",
        AlarmDescription="At least one input file had more than 5% quarantined rows.",
        Namespace=NAMESPACE,
        MetricName="FilesOverQuarantineThreshold",
        Statistic="Sum",
        Period=300,
        EvaluationPeriods=1,
        DatapointsToAlarm=1,
        Threshold=0,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )

    boto3.client("sqs", region_name=REGION).get_queue_url(QueueName=DLQ_NAME)
    cloudwatch.put_metric_alarm(
        AlarmName="fintrust-ingest-dlq-not-empty",
        AlarmDescription="Ingest failures are waiting for operator review or replay.",
        Namespace="AWS/SQS",
        MetricName="ApproximateNumberOfMessagesVisible",
        Dimensions=[{"Name": "QueueName", "Value": DLQ_NAME}],
        Statistic="Maximum",
        Period=60,
        EvaluationPeriods=1,
        DatapointsToAlarm=1,
        Threshold=0,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    print(f"Configured CloudWatch quarantine and DLQ alarms for {FUNCTION_NAME}")


if __name__ == "__main__":
    configure_monitoring()

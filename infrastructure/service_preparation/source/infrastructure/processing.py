"""Offline CloudFormation renderer for the five application functions.

Reuses existing IAM roles, raw/report buckets, DynamoDB table, RDS and VPC.
Existing functions with these names must be imported into this stack, not replaced.
The deployment archive must contain fintrust/, src/, sql/monthly_summary.sql,
runtime dependencies and certs/global-bundle.pem (the AWS RDS CA bundle).
SSM String parameters are provisioned with infrastructure/ssm/put_parameters.py.
The existing raw bucket notification must target IngestFunction with raw/*.csv
filters; merge that notification with existing bindings rather than replacing them.
Rendering this module makes no AWS calls and provisions nothing.
"""
import argparse
import json
from pathlib import Path


def ref(name):
    return {"Ref": name}


def sub(value):
    return {"Fn::Sub": value}


def arn(name):
    return {"Fn::GetAtt": [name, "Arn"]}


def build_template():
    parameters = {name: {"Type": "String"} for name in (
        "CodeBucket", "CodeKey", "CodeSha256", "RawBucket", "QuarantineBucket", "ReportsBucket", "RiskTable",
        "RiskStreamArn", "SesSender", "SesRecipient", "CognitoUserPoolId", "CognitoAppClientId",
        "CognitoDomain", "CognitoRedirectUri", "CognitoLogoutUri", "CognitoUserScopeTable",
        "CorsAllowedOrigins")}
    parameters.update(Stage={"Type": "String", "Default": "dev", "AllowedValues": ["dev", "staging", "prod"]},
                      SubnetIds={"Type": "List<AWS::EC2::Subnet::Id>"},
                      SecurityGroupIds={"Type": "List<AWS::EC2::SecurityGroup::Id>"},
                      EnableConsumers={"Type": "String", "Default": "false", "AllowedValues": ["true", "false"]})
    resources = {}
    def add(name, kind, properties, **extra):
        resources[name] = {"Type": "AWS::" + kind, "Properties": properties, **extra}
    for name, queue_name, fifo in (
        ("TransactionDLQ", "transactions-dlq", True),
        ("IngestFailures", "ingest-failures", False),
        ("ReportFailures", "report-failures", False),
        ("AlertFailures", "alert-failures", False)):
        props = {"QueueName": sub("fintrust-" + queue_name + "-${Stage}" + (".fifo" if fifo else "")),
                 "SqsManagedSseEnabled": True, "MessageRetentionPeriod": 1209600}
        if fifo:
            props["FifoQueue"] = True
        add(name, "SQS::Queue", props)
    add("Transactions", "SQS::Queue", {
        "QueueName": sub("fintrust-transactions-${Stage}.fifo"), "FifoQueue": True,
        "ContentBasedDeduplication": False, "SqsManagedSseEnabled": True,
        "VisibilityTimeout": 720, "MessageRetentionPeriod": 345600,
        "RedrivePolicy": {"deadLetterTargetArn": arn("TransactionDLQ"), "maxReceiveCount": 5}})
    for service, module, timeout in (("ingest", "ingest", 120), ("scoring", "score", 120),
                                     ("alert", "alert_delivery", 30), ("report", "report", 120),
                                     ("api", "api", 30)):
        name = service.title() + "Function"
        env = {"FINTRUST_SERVICE": service, "FINTRUST_STAGE": ref("Stage")}
        if service in {"scoring", "api", "report"}:
            env.update(DB_AUTH_MODE="iam", DB_CONFIG_SOURCE="environment",
                       DB_SSLROOTCERT="/var/task/certs/global-bundle.pem")
            for setting in ("host", "name", "user"):
                env["DB_" + setting.upper()] = sub("{{resolve:ssm:/fintrust/${Stage}/" + service + "/db_" + setting + "}}")
        if service == "ingest":
            env["TRANSACTION_QUEUE_URL"] = ref("Transactions")
            env["QUARANTINE_BUCKET"] = ref("QuarantineBucket")
        elif service == "scoring":
            env.update(DYNAMODB_TABLE=ref("RiskTable"), ALERT_DELIVERY_MODE="stream",
                       QUARANTINE_BUCKET=ref("QuarantineBucket"))
        elif service == "alert":
            env.update(SES_SENDER=ref("SesSender"), SES_RECIPIENT=ref("SesRecipient"), DYNAMODB_TABLE=ref("RiskTable"))
        elif service == "report":
            env["S3_REPORT_BUCKET"] = ref("ReportsBucket")
        elif service == "api":
            env.update(DYNAMODB_TABLE=ref("RiskTable"), AUTH_MODE="cognito",
                       COGNITO_USER_POOL_ID=ref("CognitoUserPoolId"),
                       COGNITO_APP_CLIENT_ID=ref("CognitoAppClientId"),
                       COGNITO_DOMAIN=ref("CognitoDomain"),
                       COGNITO_REDIRECT_URI=ref("CognitoRedirectUri"),
                       COGNITO_LOGOUT_URI=ref("CognitoLogoutUri"),
                       COGNITO_USER_SCOPE_TABLE=ref("CognitoUserScopeTable"),
                       CORS_ALLOWED_ORIGINS=ref("CorsAllowedOrigins"))
        add(name, "Lambda::Function", {
            "FunctionName": sub("fintrust-" + service + "-${Stage}"),
            "Role": sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:role/fintrust-" + service + "-${Stage}"),
            "Runtime": "python3.12", "Handler": "fintrust." + module + ".lambda_handler",
            "Code": {"S3Bucket": ref("CodeBucket"), "S3Key": ref("CodeKey")},
            "Timeout": timeout, "MemorySize": 256, "Environment": {"Variables": env},
            **({"VpcConfig": {"SubnetIds": ref("SubnetIds"), "SecurityGroupIds": ref("SecurityGroupIds")}}
               if service in {"scoring", "api", "report"} else {})})
        # Pre-created log groups match IAM policies which omit CreateLogGroup.
        add(service.title() + "Logs", "Logs::LogGroup", {
            "LogGroupName": sub("/aws/lambda/fintrust-" + service + "-${Stage}"), "RetentionInDays": 14})
        resources[name]["DependsOn"] = service.title() + "Logs"
    add("ScoringMapping", "Lambda::EventSourceMapping", {
        "FunctionName": ref("ScoringFunction"), "EventSourceArn": arn("Transactions"),
        "BatchSize": 5, "Enabled": {"Fn::If": ["ConsumersEnabled", True, False]},
        "FunctionResponseTypes": ["ReportBatchItemFailures"]})
    add("AlertMapping", "Lambda::EventSourceMapping", {
        "FunctionName": ref("AlertFunction"), "EventSourceArn": ref("RiskStreamArn"),
        "StartingPosition": "TRIM_HORIZON", "BatchSize": 10,
        "Enabled": {"Fn::If": ["ConsumersEnabled", True, False]},
        "MaximumRetryAttempts": 5, "MaximumRecordAgeInSeconds": 21600,
        "FunctionResponseTypes": ["ReportBatchItemFailures"],
        "DestinationConfig": {"OnFailure": {"Destination": arn("AlertFailures")}},
        "FilterCriteria": {"Filters": [{"Pattern": json.dumps({"eventName": ["INSERT"],
            "dynamodb": {"NewImage": {"score_date": {"S": [{"prefix": "TX#"}]},
                                      "risk_level": {"S": ["High"]}}}})}]}})
    add("ApiVersion", "Lambda::Version", {"FunctionName": ref("ApiFunction"), "CodeSha256": ref("CodeSha256")})
    add("ApiAlias", "Lambda::Alias", {"FunctionName": ref("ApiFunction"), "Name": ref("Stage"),
        "FunctionVersion": {"Fn::GetAtt": ["ApiVersion", "Version"]}})
    add("RawInvoke", "Lambda::Permission", {
        "FunctionName": ref("IngestFunction"), "Action": "lambda:InvokeFunction", "Principal": "s3.amazonaws.com",
        "SourceAccount": ref("AWS::AccountId"), "SourceArn": sub("arn:${AWS::Partition}:s3:::${RawBucket}")})
    # EventBridge delivery failure and Lambda execution failure are different
    # retry domains. Both send to the report failures queue.
    for service, destination in (("Ingest", "IngestFailures"), ("Report", "ReportFailures")):
        add(service + "Async", "Lambda::EventInvokeConfig", {
            "FunctionName": ref(service + "Function"), "Qualifier": "$LATEST",
            "MaximumRetryAttempts": 2, "MaximumEventAgeInSeconds": 21600,
            "DestinationConfig": {"OnFailure": {"Destination": arn(destination)}}})
    add("MonthlySchedule", "Events::Rule", {
        "Name": sub("fintrust-monthly-${Stage}"), "ScheduleExpression": "cron(0 2 1 * ? *)",
        "State": {"Fn::If": ["ConsumersEnabled", "ENABLED", "DISABLED"]},
        "Targets": [{"Id": "MonthlyReport", "Arn": arn("ReportFunction"),
                     "RetryPolicy": {"MaximumRetryAttempts": 5, "MaximumEventAgeInSeconds": 21600},
                     "DeadLetterConfig": {"Arn": arn("ReportFailures")}}]})
    add("ScheduleInvoke", "Lambda::Permission", {
        "FunctionName": ref("ReportFunction"), "Action": "lambda:InvokeFunction", "Principal": "events.amazonaws.com",
        "SourceAccount": ref("AWS::AccountId"), "SourceArn": arn("MonthlySchedule")})
    add("ReportQueuePolicy", "SQS::QueuePolicy", {"Queues": [ref("ReportFailures")], "PolicyDocument": {
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "events.amazonaws.com"},
        "Action": "sqs:SendMessage", "Resource": arn("ReportFailures"),
        "Condition": {"ArnEquals": {"aws:SourceArn": arn("MonthlySchedule")}}}]}})
    return {"AWSTemplateFormatVersion": "2010-09-09", "Description": "FinTrust transaction processing",
            "Parameters": parameters, "Resources": resources,
            "Conditions": {"ConsumersEnabled": {"Fn::Equals": [ref("EnableConsumers"), "true"]}},
            "Metadata": {"RawBucketNotificationToMerge": {"LambdaFunctionConfigurations": [{
                "Id": "fintrust-raw-csv", "LambdaFunctionArn": arn("IngestFunction"), "Events": ["s3:ObjectCreated:*"],
                "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "raw/"},
                                                      {"Name": "suffix", "Value": ".csv"}]}}}]}},
            "Outputs": {"TransactionQueueUrl": {"Value": ref("Transactions")},
                        "IngestFunctionArn": {"Value": arn("IngestFunction")}}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/processing.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print("Rendered processing template only; no AWS resources changed.")

"""Render scoped role policies offline; deployment remains an explicit operator step."""
import argparse
import json
from pathlib import Path

TRUST_POLICY = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}


def build_policies(account, region, stage, bucket, table, db_resource_id, sender, dlq_arn=None, *, queue_arn=None, reports_bucket=None, recipient=None, quarantine_bucket=None, kms_key_arn=None):
    if stage not in {"dev", "staging", "prod"}:
        raise ValueError("stage must be dev, staging or prod")
    if len(account) != 12 or not account.isdigit():
        raise ValueError("account must contain 12 digits")
    if not sender or '*' in sender or '@' not in sender:
        raise ValueError("sender must be a verified email address")
    for value in (region, bucket, table, db_resource_id):
        if not value or any(char in value for char in '*?'):
            raise ValueError("resource identifiers must be explicit and contain no wildcards")
    dlq_arn = dlq_arn or f"arn:aws:sqs:{region}:{account}:fintrust-ingest-failures-{stage}"
    if dlq_arn and (not dlq_arn.startswith(f'arn:aws:sqs:{region}:{account}:') or any(c in dlq_arn for c in '*?')):
        raise ValueError("DLQ must be an explicit queue ARN in the configured region and account")
    queue_arn = queue_arn or f"arn:aws:sqs:{region}:{account}:fintrust-transactions-{stage}.fifo"
    reports_bucket = reports_bucket or f"fintrust-reports-{account}-{stage}"
    quarantine_bucket = quarantine_bucket or bucket
    if any(c in quarantine_bucket for c in '*?'):
        raise ValueError("Quarantine bucket must be explicit")
    if kms_key_arn and (not kms_key_arn.startswith(f"arn:aws:kms:{region}:{account}:key/")
                        or any(c in kms_key_arn for c in '*?')):
        raise ValueError("KMS key must be an explicit regional key ARN")
    if not queue_arn.startswith(f"arn:aws:sqs:{region}:{account}:") or not queue_arn.endswith(".fifo"):
        raise ValueError("Transaction queue must be a FIFO ARN in the configured account and region")
    if any(c in queue_arn + reports_bucket for c in '*?'):
        raise ValueError("Queue and reports bucket must be explicit")
    if recipient and ('@' not in recipient or any(c in recipient for c in '*?')):
        raise ValueError("recipient must be an explicit email address")
    arn = "arn:aws"
    def allow(actions, resource, **extra):
        return dict(Effect="Allow", Action=actions, Resource=resource, **extra)
    result = {}
    for service in ("ingest", "scoring", "alert", "api", "report"):
        # Lambda VPC ENI management requires Resource "*"; the explicit deny
        # prevents function code from using those control-plane permissions.
        statements = [
            allow(["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSubnets",
                   "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"], "*"),
            {"Effect": "Deny", "Action": ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeSubnets", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses",
                "ec2:UnassignPrivateIpAddresses"], "Resource": "*", "Condition": {"ArnEquals": {
                    "lambda:SourceFunctionArn": f"{arn}:lambda:{region}:{account}:function:fintrust-{service}-{stage}"}}},
            allow(["logs:CreateLogStream", "logs:PutLogEvents"],
                  f"{arn}:logs:{region}:{account}:log-group:/aws/lambda/fintrust-{service}-{stage}:*"),
            allow(["rds-db:connect"], f"{arn}:rds-db:{region}:{account}:dbuser:{db_resource_id}/fintrust_{service}_{stage}"),

        ]
        if service in {"ingest", "alert"}:
            statements = [s for s in statements if not any(a.startswith(("ec2:", "rds-db:")) for a in s["Action"])]
        if service == "ingest":
            statements += [allow(["s3:GetObject", "s3:GetObjectVersion"], f"{arn}:s3:::{bucket}/raw/*"),
                           allow(["s3:PutObject"], f"{arn}:s3:::{quarantine_bucket}/quarantine/*")]
            statements += [allow(["s3:GetObject"], f"{arn}:s3:::{quarantine_bucket}/quarantine/batches/*"),
                           allow(["s3:ListBucket"], f"{arn}:s3:::{quarantine_bucket}",
                                 Condition={"StringLike": {"s3:prefix": "quarantine/batches/*"}})]
            statements.append(allow(["sqs:SendMessage"], queue_arn))
            if dlq_arn:
                statements.append(allow(["sqs:SendMessage"], dlq_arn))
        if service == "api":
            statements += [allow(["dynamodb:GetItem", "dynamodb:Query"], f"{arn}:dynamodb:{region}:{account}:table/{table}")]
        if service == "scoring":
            statements += [allow(["dynamodb:PutItem", "dynamodb:GetItem"], f"{arn}:dynamodb:{region}:{account}:table/{table}"),
                           allow(["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], queue_arn),
                           allow(["s3:PutObject"], f"{arn}:s3:::{quarantine_bucket}/quarantine/accounts/*")]
        if service == "alert":
            statements += [allow(["dynamodb:GetItem", "dynamodb:UpdateItem"], f"{arn}:dynamodb:{region}:{account}:table/{table}"),
                allow(["dynamodb:GetRecords", "dynamodb:GetShardIterator", "dynamodb:DescribeStream", "dynamodb:ListStreams"],
                      f"{arn}:dynamodb:{region}:{account}:table/{table}/stream/*"),
                allow(["sqs:SendMessage"], f"{arn}:sqs:{region}:{account}:fintrust-alert-failures-{stage}")]
            conditions = {"StringEquals": {"ses:FromAddress": sender}}
            if recipient:
                conditions["ForAllValues:StringEquals"] = {"ses:Recipients": [recipient]}
            statements.append(allow(["ses:SendEmail"], f"{arn}:ses:{region}:{account}:identity/{sender}",
                                    Condition=conditions))
        if service == "report":
            statements += [allow(["s3:PutObject"], f"{arn}:s3:::{reports_bucket}/monthly/*"),
                           allow(["sqs:SendMessage"], f"{arn}:sqs:{region}:{account}:fintrust-report-failures-{stage}")]
        encrypted_buckets = {"ingest": [bucket, quarantine_bucket], "scoring": [quarantine_bucket],
                             "report": [reports_bucket]}.get(service, [])
        if kms_key_arn and encrypted_buckets:
            statements.append(allow(["kms:GenerateDataKey", "kms:Decrypt"], kms_key_arn,
                Condition={"StringEquals": {"kms:ViaService": f"s3.{region}.amazonaws.com",
                                            "kms:CallerAccount": account},
                    "ArnLike": {"kms:EncryptionContext:aws:s3:arn":
                        [value for b in encrypted_buckets for value in (f"{arn}:s3:::{b}", f"{arn}:s3:::{b}/*")]}}))
        result[service] = {"Version": "2012-10-17", "Statement": statements}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("account", "bucket", "table", "db-resource-id", "sender"):
        parser.add_argument('--' + name, required=True)
    parser.add_argument("--queue-arn", required=True)
    parser.add_argument("--reports-bucket", required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--quarantine-bucket", required=True)
    parser.add_argument("--kms-key-arn", required=True)
    parser.add_argument('--region', default='af-south-1')
    parser.add_argument('--stage', choices=['dev', 'staging', 'prod'], default='dev')
    parser.add_argument('--dlq-arn', required=True, help='Existing ingest failure queue ARN')
    parser.add_argument('--output', type=Path, default=Path('output/iam'))
    args = parser.parse_args()
    policies = build_policies(args.account, args.region, args.stage, args.bucket, args.table,
                              args.db_resource_id, args.sender, args.dlq_arn,
                              queue_arn=args.queue_arn, reports_bucket=args.reports_bucket, recipient=args.recipient,
                              quarantine_bucket=args.quarantine_bucket, kms_key_arn=args.kms_key_arn)
    args.output.mkdir(parents=True, exist_ok=True)
    for service, policy in policies.items():
        (args.output / f'{service}.json').write_text(json.dumps(policy, indent=2) + '\n')
    (args.output / 'trust.json').write_text(json.dumps(TRUST_POLICY, indent=2) + '\n')
    print('Rendered policies only. No AWS resources were changed.')


if __name__ == '__main__':
    main()

"""Render the budget-first network and storage foundation without AWS calls.

Existing resources must be imported or supplied through a reviewed adaptation.
This template intentionally does not create a database instance or NAT gateway.
"""
import argparse
import json
from pathlib import Path
from infrastructure.processing import arn, ref, sub


def build_template():
    parameters = {
        "Stage": {"Type": "String", "Default": "dev", "AllowedValues": ["dev", "staging", "prod"]},
        "AvailabilityZones": {"Type": "List<AWS::EC2::AvailabilityZone::Name>"},
        "S3PrefixListId": {"Type": "String", "AllowedPattern": "pl-[a-f0-9]+"},
        "DynamoPrefixListId": {"Type": "String", "AllowedPattern": "pl-[a-f0-9]+"},
        "DatabaseFamily": {"Type": "String", "Default": "postgres16", "AllowedPattern": "postgres[0-9]+"},
    }
    resources = {}
    def add(name, kind, properties, **extra):
        resources[name] = {"Type": "AWS::" + kind, "Properties": properties, **extra}
    add("Vpc", "EC2::VPC", {"CidrBlock": "10.42.0.0/16", "EnableDnsSupport": True, "EnableDnsHostnames": True})
    add("PrivateRoutes", "EC2::RouteTable", {"VpcId": ref("Vpc")})
    for index in range(2):
        name = "PrivateSubnet" + str(index + 1)
        add(name, "EC2::Subnet", {"VpcId": ref("Vpc"), "CidrBlock": f"10.42.{index}.0/24",
            "AvailabilityZone": {"Fn::Select": [index, ref("AvailabilityZones")]}, "MapPublicIpOnLaunch": False})
        add(name + "Route", "EC2::SubnetRouteTableAssociation", {
            "SubnetId": ref(name), "RouteTableId": ref("PrivateRoutes")})
    add("DatabaseGroup", "EC2::SecurityGroup", {"GroupDescription": "Private PostgreSQL",
        "VpcId": ref("Vpc"), "SecurityGroupEgress": [{"IpProtocol": "-1", "CidrIp": "127.0.0.1/32"}]})
    add("LambdaGroup", "EC2::SecurityGroup", {"GroupDescription": "Ledger functions",
        "VpcId": ref("Vpc"), "SecurityGroupEgress": [
            {"IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432, "DestinationSecurityGroupId": ref("DatabaseGroup")},
            *[{"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "DestinationPrefixListId": ref(name)}
              for name in ("S3PrefixListId", "DynamoPrefixListId")]]})
    add("DatabaseIngress", "EC2::SecurityGroupIngress", {"GroupId": ref("DatabaseGroup"),
        "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432, "SourceSecurityGroupId": ref("LambdaGroup")})
    add("DatabaseSubnets", "RDS::DBSubnetGroup", {"DBSubnetGroupDescription": "Private ledger subnets",
        "SubnetIds": [ref("PrivateSubnet1"), ref("PrivateSubnet2")]})
    add("DatabaseTls", "RDS::DBParameterGroup", {"Description": "Require verified TLS clients",
        "Family": ref("DatabaseFamily"), "Parameters": {"rds.force_ssl": "1"}})
    add("DataKey", "KMS::Key", {"Description": "FinTrust regional data encryption",
        "EnableKeyRotation": True, "PendingWindowInDays": 30,
        "KeyPolicy": {"Version": "2012-10-17", "Statement": [{"Sid": "EnableAccountIamDelegation",
            "Effect": "Allow", "Principal": {"AWS": sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:root")},
            "Action": "kms:*", "Resource": "*"}]}}, DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    add("DataKeyAlias", "KMS::Alias", {"AliasName": sub("alias/fintrust-${Stage}"), "TargetKeyId": ref("DataKey")})
    for label in ("Raw", "Quarantine", "Reports"):
        bucket = label + "Bucket"
        rules = [{"Id": "AbortIncompleteUploads", "Status": "Enabled",
                  "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}}]
        if label == "Reports":
            rules.append({"Id": "ArchiveWarmToCold", "Status": "Enabled", "Prefix": "archive/",
                          "Transitions": [{"TransitionInDays": 1095, "StorageClass": "GLACIER"}]})
        add(bucket, "S3::Bucket", {
            "BucketName": sub("fintrust-" + label.lower() + "-${AWS::AccountId}-${AWS::Region}-${Stage}"),
            "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
            "PublicAccessBlockConfiguration": {k: True for k in ("BlockPublicAcls", "BlockPublicPolicy",
                                                                 "IgnorePublicAcls", "RestrictPublicBuckets")},
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {"ServerSideEncryptionConfiguration": [{"BucketKeyEnabled": True,
                "ServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms", "KMSMasterKeyID": arn("DataKey")}}]},
            "LifecycleConfiguration": {"Rules": rules}}, DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
        add(label + "BucketPolicy", "S3::BucketPolicy", {"Bucket": ref(bucket), "PolicyDocument": {
            "Version": "2012-10-17", "Statement": [
                {"Sid": "RequireTls", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
                 "Resource": [arn(bucket), sub("${" + bucket + ".Arn}/*")],
                 "Condition": {"Bool": {"aws:SecureTransport": "false"}}},
                {"Sid": "RejectExplicitOtherEncryption", "Effect": "Deny", "Principal": "*",
                 "Action": "s3:PutObject", "Resource": sub("${" + bucket + ".Arn}/*"),
                 "Condition": {"Null": {"s3:x-amz-server-side-encryption": "false"},
                               "StringNotEquals": {"s3:x-amz-server-side-encryption": "aws:kms"}}},
                {"Sid": "RejectKmsWithoutKey", "Effect": "Deny", "Principal": "*",
                 "Action": "s3:PutObject", "Resource": sub("${" + bucket + ".Arn}/*"),
                 "Condition": {"StringEquals": {"s3:x-amz-server-side-encryption": "aws:kms"},
                               "Null": {"s3:x-amz-server-side-encryption-aws-kms-key-id": "true"}}},
                {"Sid": "RejectCustomerProvidedKeys", "Effect": "Deny", "Principal": "*",
                 "Action": "s3:PutObject", "Resource": sub("${" + bucket + ".Arn}/*"),
                 "Condition": {"Null": {"s3:x-amz-server-side-encryption-customer-algorithm": "false"}}},
                {"Sid": "RejectExplicitOtherKey", "Effect": "Deny", "Principal": "*",
                 "Action": "s3:PutObject", "Resource": sub("${" + bucket + ".Arn}/*"),
                 "Condition": {"Null": {"s3:x-amz-server-side-encryption-aws-kms-key-id": "false"},
                               "StringNotEquals": {"s3:x-amz-server-side-encryption-aws-kms-key-id": arn("DataKey")}}}
            ]}})
    add("RiskTable", "DynamoDB::Table", {
        "TableName": sub("fintrust-risk-${Stage}"), "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [{"AttributeName": n, "AttributeType": "S"} for n in ("account_id", "score_date")],
        "KeySchema": [{"AttributeName": "account_id", "KeyType": "HASH"}, {"AttributeName": "score_date", "KeyType": "RANGE"}],
        "StreamSpecification": {"StreamViewType": "NEW_IMAGE"},
        "SSESpecification": {"SSEEnabled": False}}, DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    # DynamoDB's default AWS-owned encryption avoids unnecessary CMK request costs.
    for service, actions, targets in (
        ("s3", ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"],
         [sub("${" + label + "Bucket.Arn}/*") for label in ("Raw", "Quarantine", "Reports")]),
        ("dynamodb", ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"], [arn("RiskTable")])):
        add(service.title() + "Endpoint", "EC2::VPCEndpoint", {"VpcId": ref("Vpc"), "VpcEndpointType": "Gateway",
            "ServiceName": sub("com.amazonaws.${AWS::Region}." + service), "RouteTableIds": [ref("PrivateRoutes")],
            "PolicyDocument": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": "*",
                "Action": actions, "Resource": targets,
                "Condition": {"StringEquals": {"aws:PrincipalAccount": ref("AWS::AccountId")}}}]}})
    return {"AWSTemplateFormatVersion": "2010-09-09", "Description": "FinTrust private network and encrypted storage",
        "Parameters": parameters, "Resources": resources,
        "Outputs": {**{n: {"Value": ref(n)} for n in ("Vpc", "PrivateSubnet1", "PrivateSubnet2", "LambdaGroup",
            "DatabaseGroup", "DatabaseSubnets", "DatabaseTls", "RawBucket", "QuarantineBucket", "ReportsBucket", "RiskTable")},
            "DataKeyArn": {"Value": arn("DataKey")}, "RiskStreamArn": {"Value": {"Fn::GetAtt": ["RiskTable", "StreamArn"]}}}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/foundation.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print("Rendered foundation only; no AWS resources changed.")

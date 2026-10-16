"""Render the private Stage 1 network only; never call AWS."""
import argparse
import json
from pathlib import Path

from infrastructure.processing import ref, sub


def build_template():
    resources = {}

    def add(name, kind, properties, tagged=True):
        if tagged:
            properties = dict(properties, Tags=[
                {"Key": "Project", "Value": "FinTrust"},
                {"Key": "Environment", "Value": "dev"},
                {"Key": "Name", "Value": "fintrust-" + name.lower() + "-dev"},
            ])
        resources[name] = {"Type": "AWS::" + kind, "Properties": properties}

    add("Vpc", "EC2::VPC", {"CidrBlock": "10.42.0.0/16",
        "EnableDnsSupport": True, "EnableDnsHostnames": True, "InstanceTenancy": "default"})
    for tier, offset in (("Application", 0), ("Database", 2)):
        add(tier + "Routes", "EC2::RouteTable", {"VpcId": ref("Vpc")})
        for index in range(2):
            name = tier + "Subnet" + str(index + 1)
            add(name, "EC2::Subnet", {"VpcId": ref("Vpc"),
                "CidrBlock": f"10.42.{offset + index}.0/24",
                "AvailabilityZone": ref("AvailabilityZone" + str(index + 1)),
                "MapPublicIpOnLaunch": False})
            add(name + "Route", "EC2::SubnetRouteTableAssociation", {
                "SubnetId": ref(name), "RouteTableId": ref(tier + "Routes")}, tagged=False)
    add("DatabaseGroup", "EC2::SecurityGroup", {"GroupDescription": "Private PostgreSQL",
        "VpcId": ref("Vpc"), "SecurityGroupEgress": [
            {"IpProtocol": "-1", "CidrIp": "127.0.0.1/32"}]})
    add("LambdaGroup", "EC2::SecurityGroup", {"GroupDescription": "Ledger functions",
        "VpcId": ref("Vpc"), "SecurityGroupEgress": [
            {"IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
             "DestinationSecurityGroupId": ref("DatabaseGroup")},
            *[{"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
               "DestinationPrefixListId": ref(key)}
              for key in ("S3PrefixListId", "DynamoPrefixListId")]]})
    add("DatabaseIngress", "EC2::SecurityGroupIngress", {
        "GroupId": ref("DatabaseGroup"), "SourceSecurityGroupId": ref("LambdaGroup"),
        "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432}, tagged=False)
    add("DatabaseSubnets", "RDS::DBSubnetGroup", {
        "DBSubnetGroupName": "fintrust-db-dev",
        "DBSubnetGroupDescription": "Private FinTrust database tier",
        "SubnetIds": [ref("DatabaseSubnet1"), ref("DatabaseSubnet2")]})
    for service, actions, targets in (
        ("s3", ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"], [
            sub("arn:${AWS::Partition}:s3:::fintrust-" + label
                + "-${AWS::AccountId}-${AWS::Region}-dev/*")
            for label in ("raw", "quarantine", "reports")]),
        ("dynamodb", ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"], [
            sub("arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/fintrust-risk-dev")]),
    ):
        add(service.title() + "Endpoint", "EC2::VPCEndpoint", {
            "VpcId": ref("Vpc"), "VpcEndpointType": "Gateway",
            "ServiceName": sub("com.amazonaws.${AWS::Region}." + service),
            "RouteTableIds": [ref("ApplicationRoutes")],
            "PolicyDocument": {"Version": "2012-10-17", "Statement": [{
                "Effect": "Allow", "Principal": "*", "Action": actions, "Resource": targets,
                "Condition": {"StringEquals": {"aws:PrincipalAccount": ref("AWS::AccountId")}},
            }]}})
    # The API's account assignments are separate from the risk projection. Keep
    # this read-only path restricted to the API role rather than widening the
    # existing risk-table statement to every principal/action.
    resources["DynamodbEndpoint"]["Properties"]["PolicyDocument"]["Statement"].append({
        "Sid": "ApiReadAccountScopes",
        "Effect": "Allow", "Principal": "*", "Action": ["dynamodb:GetItem"],
        "Resource": sub("arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/imbokodo-dev-user-account-scopes"),
        "Condition": {"StringEquals": {
            "aws:PrincipalAccount": ref("AWS::AccountId"),
            "aws:PrincipalArn": sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:role/fintrust-api-dev"),
        }},
    })
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "FinTrust private network only; no application or paid endpoint resources",
        "Parameters": {
            **{name: {"Type": "AWS::EC2::AvailabilityZone::Name"}
               for name in ("AvailabilityZone1", "AvailabilityZone2")},
            **{name: {"Type": "String", "AllowedPattern": "pl-[a-f0-9]+"}
               for name in ("S3PrefixListId", "DynamoPrefixListId")},
        },
        "Rules": {"DistinctZones": {"Assertions": [{
            "Assert": {"Fn::Not": [{"Fn::Equals": [ref("AvailabilityZone1"), ref("AvailabilityZone2")]}]},
            "AssertDescription": "Application and database subnet pairs require two distinct AZs",
        }]}},
        "Resources": resources,
        "Outputs": {name: {"Value": ref(name)} for name in (
            "Vpc", "ApplicationSubnet1", "ApplicationSubnet2", "DatabaseSubnet1", "DatabaseSubnet2",
            "ApplicationRoutes", "DatabaseRoutes", "LambdaGroup", "DatabaseGroup", "DatabaseSubnets",
            "S3Endpoint", "DynamodbEndpoint")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

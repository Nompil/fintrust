"""Offline checks for the reviewed network-only deployment boundary."""
import ipaddress
import json
from pathlib import Path

from infrastructure.network import build_template


def test_network_has_only_private_stage1_resources():
    resources = build_template()["Resources"]
    assert {r["Type"] for r in resources.values()} == {
        "AWS::EC2::VPC", "AWS::EC2::Subnet", "AWS::EC2::RouteTable",
        "AWS::EC2::SubnetRouteTableAssociation", "AWS::EC2::SecurityGroup",
        "AWS::EC2::SecurityGroupIngress", "AWS::RDS::DBSubnetGroup", "AWS::EC2::VPCEndpoint",
    }
    subnets = {n: r["Properties"] for n, r in resources.items() if r["Type"] == "AWS::EC2::Subnet"}
    assert len(subnets) == 4
    networks = [ipaddress.ip_network(p["CidrBlock"]) for p in subnets.values()]
    assert all(n.subnet_of(ipaddress.ip_network("10.42.0.0/16")) for n in networks)
    assert all(not a.overlaps(b) for i, a in enumerate(networks) for b in networks[i + 1:])
    assert all(p["MapPublicIpOnLaunch"] is False for p in subnets.values())
    assert resources["DatabaseSubnets"]["Properties"]["SubnetIds"] == [
        {"Ref": "DatabaseSubnet1"}, {"Ref": "DatabaseSubnet2"}]
    for tier in ("Application", "Database"):
        for i in (1, 2):
            assert resources[f"{tier}Subnet{i}Route"]["Properties"] == {
                "SubnetId": {"Ref": f"{tier}Subnet{i}"}, "RouteTableId": {"Ref": tier + "Routes"}}
    assert "DistinctZones" in build_template()["Rules"]


def test_endpoints_and_security_groups_cannot_expose_database():
    resources = build_template()["Resources"]
    endpoints = [r["Properties"] for r in resources.values() if r["Type"] == "AWS::EC2::VPCEndpoint"]
    assert len(endpoints) == 2
    for endpoint in endpoints:
        assert endpoint["VpcEndpointType"] == "Gateway"
        assert endpoint["RouteTableIds"] == [{"Ref": "ApplicationRoutes"}]
        statement = endpoint["PolicyDocument"]["Statement"][0]
        assert statement["Resource"] != "*"
        assert statement["Condition"]["StringEquals"]["aws:PrincipalAccount"] == {"Ref": "AWS::AccountId"}
    ingress = resources["DatabaseIngress"]["Properties"]
    assert ingress == {"GroupId": {"Ref": "DatabaseGroup"}, "SourceSecurityGroupId": {"Ref": "LambdaGroup"},
                       "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432}
    assert "SecurityGroupIngress" not in resources["LambdaGroup"]["Properties"]
    assert "0.0.0.0/0" not in json.dumps(resources)
    for resource in resources.values():
        if resource["Type"] not in ("AWS::EC2::SecurityGroupIngress", "AWS::EC2::SubnetRouteTableAssociation"):
            tags = {t["Key"]: t["Value"] for t in resource["Properties"]["Tags"]}
            assert tags["Project"] == "FinTrust" and tags["Environment"] == "dev"


def test_policy_bundle_stays_inside_stage1_and_role_inline_quota():
    policies = [json.loads(p.read_text()) for p in Path("infrastructure/iam").glob("stage1-*-policy.json")]
    assert len(policies) == 3
    assert sum(len(json.dumps(p, separators=(",", ":"))) for p in policies) < 10240
    for policy in policies:
        for s in policy["Statement"]:
            if s["Effect"] != "Allow":
                continue
            for action in s["Action"]:
                assert "*" not in action
                service, operation = action.split(":")
                assert service in ("ec2", "rds", "cloudformation")
                if service == "rds":
                    assert operation in {"DescribeDBSubnetGroups", "ListTagsForResource", "CreateDBSubnetGroup",
                                         "AddTagsToResource", "ModifyDBSubnetGroup", "DeleteDBSubnetGroup"}
                assert not any(word in operation for word in ("NatGateway", "InternetGateway", "RunInstances",
                                                              "AllocateAddress", "CreateNetworkInterface", "CreateRoute")) or operation == "CreateRouteTable"
            assert s["Condition"]["StringEquals"]["aws:RequestedRegion"] == "af-south-1"
            if s["Resource"] == "*":
                assert all(a.split(":")[1].startswith(("Describe", "GetTemplate", "Validate")) for a in s["Action"])
            if any(a.startswith(("ec2:", "rds:")) and not a.split(":")[1].startswith(("Describe", "List")) for a in s["Action"]):
                assert s["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]


def test_change_set_access_covers_reviewed_arns_without_broadening_stack_scope():
    from fnmatch import fnmatchcase

    policy = json.loads(Path("infrastructure/iam/stage1-cloudformation-policy.json").read_text())
    statements = {s["Sid"]: s for s in policy["Statement"]}
    review = statements["ReviewAndExecuteNetworkChangeSet"]
    stack = "arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-network-dev/*"
    change_set = "arn:aws:cloudformation:af-south-1:966467878406:changeSet/fintrust-network-*/*"
    assert set(review["Resource"]) == {stack, change_set}
    assert set(review["Action"]) == {
        "cloudformation:DescribeChangeSet", "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
    }
    assert review["Condition"] == {
        "StringEquals": {"aws:RequestedRegion": "af-south-1"},
        "StringLike": {"cloudformation:ChangeSetName": "fintrust-network-*"},
    }
    # Resource matching checks scope only; this is not an IAM authorization simulator.
    allowed = "arn:aws:cloudformation:af-south-1:966467878406:changeSet/fintrust-network-stage1-review/id"
    assert any(fnmatchcase(allowed, pattern) for pattern in review["Resource"])
    for denied in (
        allowed.replace("af-south-1", "us-east-1"),
        allowed.replace("966467878406", "111111111111"),
        allowed.replace("fintrust-network-stage1-review", "unrelated-review"),
        stack.replace("fintrust-network-dev", "fintrust-network-prod").replace("*", "id"),
    ):
        assert not any(fnmatchcase(denied, pattern) for pattern in review["Resource"])
    for sid in ("PrepareNetworkChangeSet", "ReadNetworkStack", "RecoverOrRemoveNetworkStack"):
        assert statements[sid]["Resource"] == stack
    creation = statements["PrepareNetworkChangeSet"]["Condition"]
    assert creation["StringEquals"] == {
        "aws:RequestedRegion": "af-south-1", "aws:RequestTag/Project": "FinTrust",
        "aws:RequestTag/Environment": "dev",
    }
    assert creation["Null"] == {
        "cloudformation:ResourceTypes": "false", "cloudformation:RoleArn": "true",
        "cloudformation:ImportResourceTypes": "true",
    }
    assert set(creation["ForAllValues:StringEquals"]["cloudformation:ResourceTypes"]) == {
        r["Type"] for r in build_template()["Resources"].values()
    }
    assert not any(a.startswith("iam:") for s in policy["Statement"] for a in s["Action"])

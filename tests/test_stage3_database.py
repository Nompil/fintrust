"""Offline private-network, budget and permission boundaries for Stage 3."""
import json
from pathlib import Path
from infrastructure.database import build_template


def test_database_scope_and_existing_network_inputs():
    t=build_template()
    assert {r["Type"] for r in t["Resources"].values()} == {"AWS::RDS::DBInstance", "AWS::RDS::DBParameterGroup"}
    assert len(t["Resources"]) == 2
    assert t["Parameters"]["DatabaseSubnetGroup"]["AllowedValues"] == ["fintrust-db-dev"]
    assert t["Parameters"]["DatabaseSecurityGroup"]["AllowedValues"] == ["sg-01644a4c9f2c44162"]
    p=t["Resources"]["LedgerDatabase"]["Properties"]
    assert p["DBSubnetGroupName"] == {"Ref":"DatabaseSubnetGroup"}
    assert p["VPCSecurityGroups"] == [{"Ref":"DatabaseSecurityGroup"}]
    assert p["PubliclyAccessible"] is False and p["MultiAZ"] is False
    assert p["NetworkType"] == "IPV4" and p["Port"] == 5432


def test_micro_budget_storage_and_support_settings():
    p=build_template()["Resources"]["LedgerDatabase"]["Properties"]
    assert (p["Engine"],p["EngineVersion"],p["DBInstanceClass"]) == ("postgres","16.15","db.t4g.micro")
    assert int(p["AllocatedStorage"]) >= 20  # PostgreSQL SSD minimum; orderability metadata alone is insufficient.
    assert p["AllocatedStorage"] == "20" and p["StorageType"] == "gp3"
    assert "MaxAllocatedStorage" not in p and "Iops" not in p
    assert p["EngineLifecycleSupport"] == "open-source-rds-extended-support-disabled"
    assert p["MonitoringInterval"] == 0 and p["EnablePerformanceInsights"] is False
    assert p["AutoMinorVersionUpgrade"] is True and p["AllowMajorVersionUpgrade"] is False


def test_tls_auth_encryption_and_secret_safety():
    t=build_template();p=t["Resources"]["LedgerDatabase"]["Properties"]
    assert p["StorageEncrypted"] is True and "KmsKeyId" not in p
    assert p["EnableIAMDatabaseAuthentication"] is True
    assert p["ManageMasterUserPassword"] is True and "MasterUserPassword" not in p
    assert "MasterUserSecret" not in p  # Default AWS-managed Secrets Manager key.
    group=t["Resources"]["DatabaseTls"]["Properties"]
    assert group["Family"] == "postgres16" and group["Parameters"] == {"rds.force_ssl":"1"}
    assert "MasterUserPassword" not in json.dumps(t["Outputs"])


def test_retention_and_deletion_protection_are_not_silent_cleanup():
    r=build_template()["Resources"]
    assert r["LedgerDatabase"]["Properties"]["DeletionProtection"] is True
    assert r["LedgerDatabase"]["Properties"]["BackupRetentionPeriod"] == 1
    assert r["LedgerDatabase"]["Properties"]["CopyTagsToSnapshot"] is True
    assert r["LedgerDatabase"]["DeletionPolicy"] == r["LedgerDatabase"]["UpdateReplacePolicy"] == "Snapshot"
    assert r["DatabaseTls"]["DeletionPolicy"] == r["DatabaseTls"]["UpdateReplacePolicy"] == "Retain"


def test_rds_permission_creation_constraints_and_no_disposal():
    p=json.loads(Path("infrastructure/iam/stage3-rds-policy.json").read_text())
    create=p["Statement"][0];c=create["Condition"]
    assert create["Resource"] == "arn:aws:rds:af-south-1:966467878406:db:fintrust-ledger-dev"
    assert c["StringEquals"]["rds:DatabaseClass"] == "db.t4g.micro"
    assert c["StringEquals"]["rds:DatabaseEngine"] == "postgres"
    assert c["NumericEquals"] == {"rds:StorageSize":"20"}
    assert c["Bool"] == {"rds:StorageEncrypted":"true","rds:MultiAz":"false","rds:PubliclyAccessible":"false","rds:ManageMasterUserPassword":"true","rds:Vpc":"true"}
    for s in p["Statement"]:
        assert s["Condition"]["StringEquals"]["aws:RequestedRegion"] == "af-south-1"
        assert not any(a in {"rds:ModifyDBInstance","rds:DeleteDBInstance","rds:StopDBInstance","rds:StartDBInstance"} for a in s["Action"])
        assert s["Resource"] != "*"


def test_secret_service_role_and_stack_policies_do_not_grant_data_access():
    for name in ("cloudformation","rds","secret","service-linked-role"):
        p=json.loads(Path("infrastructure/iam/stage3-"+name+"-policy.json").read_text())
        assert len(json.dumps(p,separators=(",",":"))) <= 6144
        actions={a for s in p["Statement"] for a in s["Action"]}
        assert not actions & {"secretsmanager:GetSecretValue","kms:Decrypt","kms:GenerateDataKey","kms:CreateGrant","iam:PassRole"}
    role=json.loads(Path("infrastructure/iam/stage3-service-linked-role-policy.json").read_text())["Statement"][0]
    assert role["Action"] == ["iam:CreateServiceLinkedRole"]
    assert role["Condition"]["StringEquals"] == {"iam:AWSServiceName":"rds.amazonaws.com"}
    p=json.loads(Path("infrastructure/iam/stage3-cloudformation-policy.json").read_text())
    prepare=next(s for s in p["Statement"] if s["Sid"] == "PrepareDatabase")
    assert prepare["Condition"]["ForAllValues:StringEquals"]["cloudformation:ResourceTypes"] == ["AWS::RDS::DBInstance","AWS::RDS::DBParameterGroup"]
    assert prepare["Condition"]["Null"]["cloudformation:RoleArn"] == "true"
    assert "fintrust-database-dev" in prepare["Resource"]

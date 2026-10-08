"""Focused Stage 5 scope, event isolation and package approval tests."""
import json
from pathlib import Path

import pytest
from infrastructure import ingest_deployment as deploy


def policy(name):
    return json.loads(Path(f"infrastructure/iam/stage5-{name}.json").read_text())


def test_only_ingest_is_deployed_without_triggers_or_vpc():
    template = deploy.build_template()
    assert set(template["Resources"]) == {"IngestFunction", "IngestLogs", "IngestAsync"}
    assert {r["Type"] for r in template["Resources"].values()} == {
        "AWS::Lambda::Function", "AWS::Logs::LogGroup", "AWS::Lambda::EventInvokeConfig"}
    function = template["Resources"]["IngestFunction"]
    props = function["Properties"]
    assert function["DependsOn"] == "IngestLogs"
    assert props["FunctionName"] == "fintrust-ingest-dev"
    assert props["Role"] == deploy.ROLE_ARN
    assert (props["Runtime"], props["Handler"], props["Architectures"]) == (
        "python3.12", "fintrust.ingest.lambda_handler", ["x86_64"])
    assert props["MemorySize"] == 256 and props["Timeout"] == 120
    assert props["ReservedConcurrentExecutions"] == 0
    assert "VpcConfig" not in props and "ProvisionedConcurrencyConfig" not in props


def test_existing_destinations_and_bounded_async_retries():
    resources = deploy.build_template()["Resources"]
    env = resources["IngestFunction"]["Properties"]["Environment"]["Variables"]
    assert env == {"FINTRUST_SERVICE": "ingest", "FINTRUST_STAGE": "dev",
        "TRANSACTION_QUEUE_URL": "https://sqs.af-south-1.amazonaws.com/966467878406/fintrust-transactions-dev.fifo",
        "QUARANTINE_BUCKET": "fintrust-quarantine-966467878406-af-south-1-dev"}
    async_props = resources["IngestAsync"]["Properties"]
    assert async_props["Qualifier"] == "$LATEST"
    assert async_props["MaximumRetryAttempts"] == 2
    assert async_props["MaximumEventAgeInSeconds"] == 21600
    assert async_props["DestinationConfig"]["OnFailure"]["Destination"] == "arn:aws:sqs:af-south-1:966467878406:fintrust-ingest-failures-dev"
    assert resources["IngestLogs"]["Properties"]["RetentionInDays"] == 14
    assert resources["IngestLogs"]["DeletionPolicy"] == "Retain"


def test_code_is_reviewed_digest_key_and_requires_real_object_version():
    template = deploy.build_template()
    code = template["Resources"]["IngestFunction"]["Properties"]["Code"]
    assert code == {"S3Bucket": deploy.CODE_BUCKET, "S3Key": deploy.CODE_KEY,
                    "S3ObjectVersion": {"Ref": "CodeObjectVersion"}}
    assert deploy.PACKAGE_SHA256 in deploy.CODE_KEY
    parameter = template["Parameters"]["CodeObjectVersion"]
    assert "Default" not in parameter and parameter["MinLength"] == 1
    assert "null" in parameter["AllowedPattern"]


def test_runtime_permissions_cannot_read_db_secrets_or_manage_resources():
    p = policy("ingest-runtime-policy")
    actions = {a for s in p["Statement"] for a in s["Action"]}
    assert actions == {"logs:CreateLogStream", "logs:PutLogEvents", "s3:GetObject",
                       "s3:GetObjectVersion", "s3:PutObject", "sqs:SendMessage",
                       "kms:Decrypt", "kms:GenerateDataKey"}
    assert all(s["Resource"] != "*" for s in p["Statement"])
    for s in p["Statement"]:
        if any(a.startswith("kms:") for a in s["Action"]):
            assert s["Condition"]["StringEquals"]["kms:ViaService"] == "s3.af-south-1.amazonaws.com"
            assert s["Resource"] == "arn:aws:kms:af-south-1:966467878406:key/598a4158-2cc6-4946-af24-512784a276c8"
    assert policy("ingest-trust")["Statement"] == [{"Effect": "Allow", "Action": ["sts:AssumeRole"],
                                                    "Principal": {"Service": "lambda.amazonaws.com"}}]


def test_deployer_passrole_and_configuration_are_bounded():
    p = policy("deployment-policy")
    assert len(json.dumps(p, separators=(",", ":"))) <= 6144
    statements = {s["Sid"]: s for s in p["Statement"]}
    role = statements["PassOnlyIngestRole"]
    assert role["Resource"] == deploy.ROLE_ARN and role["Action"] == ["iam:PassRole"]
    assert role["Condition"]["StringEquals"]["iam:PassedToService"] == "lambda.amazonaws.com"
    assert role["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]
    forbidden = {"iam:CreateRole", "iam:PutRolePolicy", "iam:AttachRolePolicy", "lambda:InvokeFunction",
                 "lambda:AddPermission", "lambda:CreateEventSourceMapping", "s3:PutObject", "sqs:SendMessage"}
    assert not forbidden & {a for s in p["Statement"] for a in s["Action"]}
    for s in p["Statement"]:
        assert s["Condition"]["StringEquals"]["aws:RequestedRegion"] == "af-south-1"
        assert not any("*" in a for a in s["Action"])
        if s["Resource"] == "*":
            assert s["Sid"] in {"ValidateIngest", "InspectIngestLogGroups"}
    assert statements["PrepareIngest"]["Condition"]["ForAllValues:StringEquals"]["cloudformation:ResourceTypes"] == [
        "AWS::Lambda::Function", "AWS::Lambda::EventInvokeConfig", "AWS::Logs::LogGroup"]


@pytest.mark.parametrize("change,reason", [({"linux_execution_verified": False}, "Linux"),
                                         ({"sha256": "wrong"}, "manifest"),
                                         ({"architecture": "arm64"}, "architecture")])
def test_package_rejects_unverified_or_mismatched_evidence(tmp_path, monkeypatch, change, reason):
    path = tmp_path / "fintrust.zip"
    actual = {"sha256": deploy.PACKAGE_SHA256}
    manifest = {**actual, "runtime": "python3.12", "architecture": "x86_64", "linux_execution_verified": True,
                "linux_verification": {"handlers_imported": list(deploy.HANDLERS.values())}}
    manifest.update(change)
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(deploy, "verify_archive", lambda _: actual)
    with pytest.raises(ValueError, match=reason):
        deploy.verify_package(path)


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
                       "s3:GetObjectVersion", "s3:PutObject", "s3:ListBucket", "sqs:SendMessage",
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
                 "lambda:CreateEventSourceMapping", "s3:PutObject", "sqs:SendMessage"}
    assert not forbidden & {a for s in p["Statement"] for a in s["Action"]}
    for s in p["Statement"]:
        assert s["Condition"]["StringEquals"]["aws:RequestedRegion"] == "af-south-1"
        assert not any("*" in a for a in s["Action"])
        if s["Resource"] == "*":
            assert s["Sid"] in {"ValidateIngest", "InspectIngestLogGroups"}
    assert statements["PrepareIngest"]["Condition"]["ForAllValues:StringEquals"]["cloudformation:ResourceTypes"] == [
        "AWS::Lambda::Function", "AWS::Lambda::EventInvokeConfig", "AWS::Lambda::Permission", "AWS::Logs::LogGroup"]


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

def test_batch_send_uses_documented_sendmessage_permission_on_exact_queues():
    # AWS maps SendMessageBatch to sqs:SendMessage, not a separate IAM action.
    # https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-api-permissions-reference.html
    statements = policy("ingest-runtime-policy")["Statement"]
    sqs_statements = [s for s in statements if any(a.startswith("sqs:") for a in s["Action"])]
    assert len(sqs_statements) == 1
    assert sqs_statements[0]["Effect"] == "Allow"
    assert sqs_statements[0]["Action"] == ["sqs:SendMessage"]
    assert set(sqs_statements[0]["Resource"]) == {
        "arn:aws:sqs:af-south-1:966467878406:fintrust-transactions-dev.fifo",
        "arn:aws:sqs:af-south-1:966467878406:fintrust-ingest-failures-dev",
    }

def test_tagged_log_group_creation_has_separately_scoped_tagresource_grant():
    statements = {s["Sid"]: s for s in policy("deployment-policy")["Statement"]}
    tagging = statements["TagIngestLogGroup"]
    assert tagging["Effect"] == "Allow"
    assert tagging["Action"] == ["logs:TagResource"]
    # TagResource uses the log-group ARN without the :* suffix.
    assert tagging["Resource"] == "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev"
    assert tagging["Condition"] == statements["CreateIngestLogGroup"]["Condition"]
    assert tagging["Condition"]["StringEquals"] == {
        "aws:RequestedRegion": "af-south-1",
        "aws:RequestTag/Project": "FinTrust",
        "aws:RequestTag/Environment": "dev",
    }
    assert tagging["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]
    logs_actions = {a for s in statements.values() for a in s["Action"] if a.startswith("logs:")}
    assert logs_actions == {"logs:CreateLogGroup", "logs:TagResource", "logs:PutRetentionPolicy",
                            "logs:DescribeLogGroups", "logs:ListTagsForResource", "logs:TagLogGroup"}

def test_temporary_diagnostic_changes_only_tagging_calledvia_condition():
    from copy import deepcopy
    original = json.loads(Path("infrastructure/iam/evidence/stage5-tagloggroup-version-baseline.json").read_text())["v2"]["PolicyVersion"]["Document"]
    expected = deepcopy(original)
    tagging = next(s for s in expected["Statement"] if s["Sid"] == "TagIngestLogGroup")
    del tagging["Condition"]["ForAnyValue:StringEquals"]
    candidate = policy("deployment-diagnostic-policy")
    assert candidate == expected
    assert len(json.dumps(candidate, separators=(",", ":"))) <= 6144
    # The canonical policy remains the control/restoration version.
    control = next(s for s in original["Statement"] if s["Sid"] == "TagIngestLogGroup")
    assert control["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]


def test_temporary_diagnostic_retains_exact_resource_and_request_tags():
    tagging = next(s for s in policy("deployment-diagnostic-policy")["Statement"] if s["Sid"] == "TagIngestLogGroup")
    assert tagging["Action"] == ["logs:TagResource"] and tagging["Effect"] == "Allow"
    assert tagging["Resource"] == "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev"
    assert tagging["Condition"] == {"StringEquals": {
        "aws:RequestedRegion": "af-south-1", "aws:RequestTag/Project": "FinTrust",
        "aws:RequestTag/Environment": "dev"}}


def test_batch_audit_reads_are_scoped_to_existing_quarantine_prefix():
    statements = {s.get("Sid"): s for s in policy("ingest-runtime-policy")["Statement"]}
    assert statements["ReadBatchAudit"]["Action"] == ["s3:GetObject"]
    assert statements["ReadBatchAudit"]["Resource"] == "arn:aws:s3:::fintrust-quarantine-966467878406-af-south-1-dev/quarantine/batches/*"
    assert statements["ListBatchMarkers"]["Action"] == ["s3:ListBucket"]
    assert statements["ListBatchMarkers"]["Condition"] == {"StringLike": {"s3:prefix": "quarantine/batches/*"}}
    assert not any(a.startswith("rds:") or a.startswith("dynamodb:") for s in statements.values() for a in s["Action"])


def test_second_diagnostic_changes_only_request_tags_from_first():
    from copy import deepcopy
    first = policy("deployment-diagnostic-policy")
    expected = deepcopy(first)
    tagging = next(s for s in expected["Statement"] if s["Sid"] == "TagIngestLogGroup")
    del tagging["Condition"]["StringEquals"]["aws:RequestTag/Project"]
    del tagging["Condition"]["StringEquals"]["aws:RequestTag/Environment"]
    candidate = policy("deployment-diagnostic2-policy")
    assert candidate == expected
    assert len(json.dumps(candidate, separators=(",", ":"))) <= 6144
    assert tagging == {"Sid": "TagIngestLogGroup", "Effect": "Allow",
        "Action": ["logs:TagResource"],
        "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev",
        "Condition": {"StringEquals": {"aws:RequestedRegion": "af-south-1"}}}


@pytest.mark.parametrize("arn,region,in_scope", [
    ("arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev", "af-south-1", True),
    ("arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-report-dev", "af-south-1", False),
    ("arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev", "us-east-1", False),
    ("arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev:*", "af-south-1", False),
])
def test_second_diagnostic_exact_tagging_scope(arn, region, in_scope):
    # This checks the exact structural gate, not the full AWS authorization engine.
    # Actual read-only SimulateCustomPolicy results are recorded in the diagnostic plan.
    statements = policy("deployment-diagnostic2-policy")["Statement"]
    grants = [s for s in statements if "logs:TagResource" in s["Action"]]
    assert len(grants) == 1
    tagging = grants[0]
    assert "*" not in tagging["Resource"]
    assert tagging["Action"] == ["logs:TagResource"]
    assert tagging["Condition"] == {"StringEquals": {"aws:RequestedRegion": "af-south-1"}}
    matches = arn == tagging["Resource"] and region == tagging["Condition"]["StringEquals"]["aws:RequestedRegion"]
    assert matches is in_scope


def test_second_diagnostic_leaves_canonical_control_and_other_grants_intact():
    from copy import deepcopy
    canonical = json.loads(Path("infrastructure/iam/evidence/stage5-tagloggroup-version-baseline.json").read_text())["v2"]["PolicyVersion"]["Document"]
    expected = deepcopy(canonical)
    tagging = next(s for s in expected["Statement"] if s["Sid"] == "TagIngestLogGroup")
    assert tagging["Condition"] == {
        "StringEquals": {"aws:RequestedRegion": "af-south-1",
                         "aws:RequestTag/Project": "FinTrust", "aws:RequestTag/Environment": "dev"},
        "ForAnyValue:StringEquals": {"aws:CalledVia": ["cloudformation.amazonaws.com"]}}
    tagging["Condition"] = {"StringEquals": {"aws:RequestedRegion": "af-south-1"}}
    assert policy("deployment-diagnostic2-policy") == expected
    # In particular, the create permission still requires tags and CloudFormation.
    create = next(s for s in canonical["Statement"] if s["Sid"] == "CreateIngestLogGroup")
    assert create["Condition"] == next(s for s in canonical["Statement"] if s["Sid"] == "TagIngestLogGroup")["Condition"]


def test_third_diagnostic_changes_only_primary_create_calledvia_from_v4():
    from copy import deepcopy
    original = policy("deployment-diagnostic2-policy")
    expected = deepcopy(original)
    create = next(s for s in expected["Statement"] if s["Sid"] == "CreateIngestLogGroup")
    del create["Condition"]["ForAnyValue:StringEquals"]
    candidate = policy("deployment-diagnostic3-policy")
    assert candidate == expected
    assert create["Action"] == ["logs:CreateLogGroup"]
    assert create["Resource"] == "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev:*"
    assert create["Condition"] == {"StringEquals": {
        "aws:RequestedRegion": "af-south-1", "aws:RequestTag/Project": "FinTrust",
        "aws:RequestTag/Environment": "dev"}}
    assert len(json.dumps(candidate, separators=(",", ":"))) <= 6144
    # TagResource and all other grants remain byte-equivalent as parsed JSON.
    assert next(s for s in candidate["Statement"] if s["Sid"] == "TagIngestLogGroup") == next(
        s for s in original["Statement"] if s["Sid"] == "TagIngestLogGroup")
    canonical = next(s for s in policy("deployment-policy")["Statement"] if s["Sid"] == "CreateIngestLogGroup")
    assert canonical["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]


def test_current_invoke_permissions_are_cloudformation_only_and_exact_function():
    current = policy("deployment-policy")
    grants = [s for s in current["Statement"] if set(s["Action"]) & {"lambda:AddPermission", "lambda:RemovePermission"}]
    assert len(grants) == 1
    grant = grants[0]
    assert grant["Effect"] == "Allow"
    assert grant["Resource"] == "arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev"
    assert grant["Condition"] == {
        "StringEquals": {"aws:RequestedRegion": "af-south-1"},
        "ForAnyValue:StringEquals": {"aws:CalledVia": ["cloudformation.amazonaws.com"]}}
    assert not Path("infrastructure/iam/stage5-invoke-policy.json").exists()
    assert len(json.dumps(current, separators=(",", ":"))) <= 6144

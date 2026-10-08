"""Stage 4 deployment boundaries; no database or AWS account access."""
import json
from pathlib import Path

from infrastructure.foundation import build_template as foundation_template
from infrastructure.messaging import QUEUE_NAMES, build_template
from infrastructure.processing import build_template as processing_template


QUEUE_ARNS = {
    "arn:aws:sqs:af-south-1:966467878406:fintrust-" + suffix
    for suffix in ("transactions-dev.fifo", "transactions-dlq-dev.fifo",
                   "ingest-failures-dev", "report-failures-dev", "alert-failures-dev")
}
TABLE_ARN = "arn:aws:dynamodb:af-south-1:966467878406:table/fintrust-risk-dev"


def policy(name):
    return json.loads(Path(f"infrastructure/iam/stage4-{name}-policy.json").read_text())


def test_stage4_scope_has_no_execution_or_cross_stage_resources():
    template = build_template()
    resources = template["Resources"]
    assert len(resources) == 6
    assert set(resources) == {"RiskTable", *QUEUE_NAMES}
    assert {r["Type"] for r in resources.values()} == {"AWS::DynamoDB::Table", "AWS::SQS::Queue"}
    assert template["Parameters"] == {"Stage": {"Type": "String", "Default": "dev", "AllowedValues": ["dev"]}}
    for resource in resources.values():
        assert resource["DeletionPolicy"] == resource["UpdateReplacePolicy"] == "Retain"
        assert resource["Properties"]["Tags"] == [
            {"Key": "Project", "Value": "FinTrust"}, {"Key": "Environment", "Value": "dev"}]


def test_risk_table_keeps_projection_and_delivery_state_contract():
    props = build_template()["Resources"]["RiskTable"]["Properties"]
    assert props["TableName"] == {"Fn::Sub": "fintrust-risk-${Stage}"}
    assert props["BillingMode"] == "PAY_PER_REQUEST"
    assert props["KeySchema"] == [
        {"AttributeName": "account_id", "KeyType": "HASH"},
        {"AttributeName": "score_date", "KeyType": "RANGE"}]
    assert props["AttributeDefinitions"] == [
        {"AttributeName": "account_id", "AttributeType": "S"},
        {"AttributeName": "score_date", "AttributeType": "S"}]
    assert props["StreamSpecification"] == {"StreamViewType": "NEW_IMAGE"}
    assert props["SSESpecification"] == {"SSEEnabled": False}  # AWS-owned encryption, not plaintext.
    assert not {"TimeToLiveSpecification", "GlobalSecondaryIndexes", "ProvisionedThroughput"} & props.keys()
    assert build_template()["Outputs"]["RiskStreamArn"]["Value"] == {"Fn::GetAtt": ["RiskTable", "StreamArn"]}


def test_queue_contracts_and_dlq_source_are_preserved():
    resources = build_template()["Resources"]
    transactions = resources["Transactions"]["Properties"]
    assert transactions["FifoQueue"] is True
    assert transactions["ContentBasedDeduplication"] is False
    assert transactions["VisibilityTimeout"] == 720
    assert transactions["MessageRetentionPeriod"] == 345600
    assert transactions["RedrivePolicy"] == {
        "deadLetterTargetArn": {"Fn::GetAtt": ["TransactionDLQ", "Arn"]}, "maxReceiveCount": 5}
    dlq = resources["TransactionDLQ"]["Properties"]
    assert dlq["FifoQueue"] is True
    assert dlq["RedriveAllowPolicy"] == {"redrivePermission": "byQueue", "sourceQueueArns": [
        {"Fn::Sub": "arn:${AWS::Partition}:sqs:${AWS::Region}:${AWS::AccountId}:fintrust-transactions-${Stage}.fifo"}]}
    for name in QUEUE_NAMES:
        props = resources[name]["Properties"]
        assert props["SqsManagedSseEnabled"] is True and "KmsMasterKeyId" not in props
        if name != "Transactions":
            assert props["MessageRetentionPeriod"] == 1209600
        if name not in {"TransactionDLQ", "Transactions"}:
            assert not props.get("FifoQueue", False)


def test_extraction_does_not_mutate_legacy_templates_or_leave_dangling_refs():
    original_foundation = foundation_template()
    original_processing = processing_template()
    template = build_template()
    template["Resources"]["Transactions"]["Properties"]["Tags"].clear()
    assert foundation_template() == original_foundation
    assert processing_template() == original_processing
    allowed = set(template["Resources"]) | set(template["Parameters"]) | {"AWS::Partition", "AWS::Region", "AWS::AccountId"}
    def check(node):
        if isinstance(node, dict):
            if "Ref" in node:
                assert node["Ref"] in allowed
            if "Fn::GetAtt" in node:
                assert node["Fn::GetAtt"][0] in template["Resources"]
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(template)


def test_deployer_has_no_data_replay_or_disposal_permissions():
    forbidden = {"sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:PurgeQueue",
                 "sqs:DeleteQueue", "sqs:StartMessageMoveTask", "dynamodb:GetItem", "dynamodb:PutItem",
                 "dynamodb:Query", "dynamodb:Scan", "dynamodb:UpdateItem", "dynamodb:DeleteTable",
                 "iam:PassRole", "kms:Decrypt", "kms:CreateGrant"}
    for name in ("sqs", "dynamodb", "cloudformation"):
        document = policy(name)
        assert len(json.dumps(document, separators=(",", ":"))) <= 6144
        for statement in document["Statement"]:
            assert not forbidden & set(statement["Action"])
            assert all(action.startswith(name + ":") for action in statement["Action"])
            assert statement["Condition"]["StringEquals"]["aws:RequestedRegion"] == "af-south-1"
            assert not any("*" in action for action in statement["Action"])
            if name == "sqs":
                assert set(statement["Resource"]) == QUEUE_ARNS
            elif name == "dynamodb":
                assert statement["Resource"] == TABLE_ARN
            if statement["Sid"].startswith(("Create", "Tag", "Configure")):
                assert statement["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]
                tag_kind = "Resource" if statement["Sid"].startswith("Configure") else "Request"
                assert statement["Condition"]["StringEquals"][f"aws:{tag_kind}Tag/Project"] == "FinTrust"
                assert statement["Condition"]["StringEquals"][f"aws:{tag_kind}Tag/Environment"] == "dev"


def test_cloudformation_scope_and_approved_resource_types():
    statements = {s["Sid"]: s for s in policy("cloudformation")["Statement"]}
    prepare = statements["PrepareMessaging"]["Condition"]
    assert prepare["ForAllValues:StringEquals"]["cloudformation:ResourceTypes"] == ["AWS::DynamoDB::Table", "AWS::SQS::Queue"]
    assert prepare["StringLike"] == {"cloudformation:ChangeSetName": "fintrust-messaging-*"}
    assert prepare["Null"] == {"cloudformation:ResourceTypes": "false", "cloudformation:RoleArn": "true", "cloudformation:ImportResourceTypes": "true"}
    for sid, statement in statements.items():
        assert statement["Resource"] == ("*" if sid == "ValidateMessaging" else
            "arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-messaging-dev/*")
    assert "cloudformation:DescribeStackResource" in statements["ReadMessaging"]["Action"]

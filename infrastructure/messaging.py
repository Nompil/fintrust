"""Render Stage 4 risk storage and queues only; never call AWS."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from infrastructure.foundation import build_template as foundation_template
from infrastructure.processing import build_template as processing_template

QUEUE_NAMES = ("TransactionDLQ", "IngestFailures", "ReportFailures", "AlertFailures", "Transactions")


def build_template():
    resources = {"RiskTable": deepcopy(foundation_template()["Resources"]["RiskTable"])}
    processing = processing_template()["Resources"]
    resources.update({name: deepcopy(processing[name]) for name in QUEUE_NAMES})
    tags = [{"Key": "Project", "Value": "FinTrust"}, {"Key": "Environment", "Value": "dev"}]
    for resource in resources.values():
        resource["Properties"]["Tags"] = deepcopy(tags)
        resource["DeletionPolicy"] = "Retain"
        resource["UpdateReplacePolicy"] = "Retain"
    # Only the intended transaction source may use this queue as its DLQ.
    # A deterministic ARN avoids a circular dependency with Transactions.
    resources["TransactionDLQ"]["Properties"]["RedriveAllowPolicy"] = {
        "redrivePermission": "byQueue",
        "sourceQueueArns": [{"Fn::Sub": "arn:${AWS::Partition}:sqs:${AWS::Region}:${AWS::AccountId}:fintrust-transactions-${Stage}.fifo"}],
    }
    outputs = {
        "RiskTableName": {"Value": {"Ref": "RiskTable"}},
        "RiskTableArn": {"Value": {"Fn::GetAtt": ["RiskTable", "Arn"]}},
        "RiskStreamArn": {"Value": {"Fn::GetAtt": ["RiskTable", "StreamArn"]}},
    }
    for name in QUEUE_NAMES:
        outputs[name + "Url"] = {"Value": {"Ref": name}}
        outputs[name + "Arn"] = {"Value": {"Fn::GetAtt": [name, "Arn"]}}
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "FinTrust Stage 4 risk table and queues; approval required before deployment",
        "Parameters": {"Stage": {"Type": "String", "Default": "dev", "AllowedValues": ["dev"]}},
        "Resources": resources,
        "Outputs": outputs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/stage4-messaging.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print("Rendered Stage 4 messaging only; no AWS resources changed.")


if __name__ == "__main__":
    main()

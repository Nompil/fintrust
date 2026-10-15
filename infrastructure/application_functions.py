"""Render remaining application functions against existing foundation stacks.

Offline only. Keeps the deployed ingest, messaging, storage and database resources
under their existing owners. Functions and event consumers start disabled.
"""
import argparse
import json
from pathlib import Path

from infrastructure.processing import build_template as combined_template


def build_template():
    template = combined_template()
    resources = template["Resources"]
    for name in ("TransactionDLQ", "IngestFailures", "ReportFailures", "AlertFailures",
                 "Transactions", "IngestFunction", "IngestLogs", "IngestAsync", "RawInvoke"):
        del resources[name]
    parameters = template["Parameters"]
    del parameters["RawBucket"]
    for name in ("ExistingTransactionsArn", "ExistingAlertFailuresArn", "ExistingReportFailuresArn"):
        parameters[name] = {"Type": "String", "AllowedPattern": "arn:[^:]+:sqs:[^:]+:[0-9]{12}:.+"}
    parameters["ExistingReportFailuresUrl"] = {"Type": "String", "AllowedPattern": "https://.+"}
    parameters["CodeObjectVersion"] = {
        "Type": "String", "MinLength": 1, "AllowedPattern": "(?!null$)[A-Za-z0-9._+/=-]+"}
    parameters["EnableFunctions"] = {
        "Type": "String", "Default": "false", "AllowedValues": ["true", "false"]}
    template["Conditions"]["FunctionsEnabled"] = {
        "Fn::Equals": [{"Ref": "EnableFunctions"}, "true"]}
    template["Conditions"]["ConsumersEnabled"] = {"Fn::And": [
        {"Condition": "FunctionsEnabled"},
        {"Fn::Equals": [{"Ref": "EnableConsumers"}, "true"]}]}

    external_arns = {"Transactions": "ExistingTransactionsArn",
                     "AlertFailures": "ExistingAlertFailuresArn",
                     "ReportFailures": "ExistingReportFailuresArn"}

    def bind_existing(value):
        if isinstance(value, dict):
            target = value.get("Fn::GetAtt")
            if isinstance(target, list) and len(target) == 2 and target[0] in external_arns:
                if target[1] != "Arn":
                    raise ValueError("Unsupported existing-resource attribute")
                return {"Ref": external_arns[target[0]]}
            if value == {"Ref": "ReportFailures"}:
                return {"Ref": "ExistingReportFailuresUrl"}
            return {key: bind_existing(child) for key, child in value.items()}
        if isinstance(value, list):
            return [bind_existing(child) for child in value]
        return value

    template["Resources"] = bind_existing(resources)
    for resource in template["Resources"].values():
        if resource["Type"] == "AWS::Lambda::Function":
            properties = resource["Properties"]
            properties["Code"]["S3ObjectVersion"] = {"Ref": "CodeObjectVersion"}
            properties["Architectures"] = ["x86_64"]
            properties["ReservedConcurrentExecutions"] = {"Fn::If": ["FunctionsEnabled", 1, 0]}
    template["Description"] = "FinTrust remaining functions; reference existing messaging and ingest stacks"
    template.pop("Metadata", None)
    template["Outputs"] = {
        name + "FunctionArn": {"Value": {"Fn::GetAtt": [name + "Function", "Arn"]}}
        for name in ("Scoring", "Alert", "Report", "Api")}
    template["Outputs"]["ApiAliasArn"] = {"Value": {"Ref": "ApiAlias"}}
    return template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/application-functions.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print("Rendered remaining application functions only; no AWS resources changed.")


if __name__ == "__main__":
    main()

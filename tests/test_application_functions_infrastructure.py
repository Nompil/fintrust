"""Deployment ownership and activation checks; no live AWS or database required."""
import json
import unittest

from infrastructure.application_functions import build_template
from infrastructure.messaging import build_template as messaging_template
from infrastructure.processing import build_template as combined_template


class ApplicationFunctionsTests(unittest.TestCase):
    def test_preserves_existing_resource_owners(self):
        before = json.dumps(messaging_template(), sort_keys=True)
        resources = build_template()["Resources"]
        self.assertEqual({name for name, resource in resources.items()
                          if resource["Type"] == "AWS::Lambda::Function"},
                         {"ScoringFunction", "AlertFunction", "ReportFunction", "ApiFunction"})
        forbidden = {"AWS::SQS::Queue", "AWS::DynamoDB::Table", "AWS::S3::Bucket",
                     "AWS::RDS::DBInstance", "AWS::EC2::SecurityGroup", "AWS::IAM::Role"}
        self.assertFalse(forbidden & {resource["Type"] for resource in resources.values()})
        self.assertFalse({"IngestFunction", "IngestLogs", "IngestAsync", "RawInvoke"} & resources.keys())
        self.assertEqual(before, json.dumps(messaging_template(), sort_keys=True))

    def test_functions_use_immutable_linux_artifact_and_original_handlers(self):
        template = build_template()
        original = combined_template()["Resources"]
        self.assertNotIn("Default", template["Parameters"]["CodeObjectVersion"])
        self.assertIn("null", template["Parameters"]["CodeObjectVersion"]["AllowedPattern"])
        for name, resource in template["Resources"].items():
            if resource["Type"] != "AWS::Lambda::Function":
                continue
            properties = resource["Properties"]
            self.assertEqual(properties["Runtime"], "python3.12")
            self.assertEqual(properties["Architectures"], ["x86_64"])
            self.assertEqual(properties["Code"]["S3ObjectVersion"], {"Ref": "CodeObjectVersion"})
            for field in ("Handler", "Role", "Environment", "Timeout"):
                self.assertEqual(properties[field], original[name]["Properties"][field])

    def test_references_existing_queue_destinations(self):
        resources = build_template()["Resources"]
        self.assertEqual(resources["ScoringMapping"]["Properties"]["EventSourceArn"],
                         {"Ref": "ExistingTransactionsArn"})
        self.assertEqual(resources["AlertMapping"]["Properties"]["DestinationConfig"]["OnFailure"]["Destination"],
                         {"Ref": "ExistingAlertFailuresArn"})
        self.assertEqual(resources["ReportQueuePolicy"]["Properties"]["Queues"],
                         [{"Ref": "ExistingReportFailuresUrl"}])
        self.assertEqual(resources["ReportAsync"]["Properties"]["DestinationConfig"]["OnFailure"]["Destination"],
                         {"Ref": "ExistingReportFailuresArn"})

    def test_starts_disabled_and_does_not_enable_consumers_without_functions(self):
        template = build_template()
        for flag in ("EnableFunctions", "EnableConsumers"):
            self.assertEqual(template["Parameters"][flag]["Default"], "false")
        self.assertIn({"Condition": "FunctionsEnabled"},
                      template["Conditions"]["ConsumersEnabled"]["Fn::And"])
        for resource in template["Resources"].values():
            if resource["Type"] == "AWS::Lambda::Function":
                self.assertEqual(resource["Properties"]["ReservedConcurrentExecutions"],
                                 {"Fn::If": ["FunctionsEnabled", 1, 0]})

    def test_no_dangling_resource_references(self):
        template = build_template()
        declared = set(template["Resources"]) | set(template["Parameters"]) | {
            "AWS::AccountId", "AWS::Region", "AWS::Partition", "AWS::NoValue"}

        def inspect(value):
            if isinstance(value, dict):
                if "Ref" in value:
                    self.assertIn(value["Ref"], declared)
                if "Fn::GetAtt" in value:
                    self.assertIn(value["Fn::GetAtt"][0], template["Resources"])
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(template)


if __name__ == "__main__":
    unittest.main()

"""Offline checks for the existing Stage 2 storage deployment boundary."""
import json

from infrastructure.foundation import build_template as foundation_template
from infrastructure.storage import build_template


def test_storage_stage_has_only_the_eight_planned_resources():
    template = build_template()
    assert len(template["Resources"]) == 8
    assert {r["Type"] for r in template["Resources"].values()} == {
        "AWS::KMS::Key", "AWS::KMS::Alias", "AWS::S3::Bucket", "AWS::S3::BucketPolicy",
    }
    assert template["Parameters"] == {
        "Stage": {"Type": "String", "Default": "dev", "AllowedValues": ["dev"]}
    }
    assert set(template["Outputs"]) == {"RawBucket", "QuarantineBucket", "ReportsBucket", "DataKeyArn"}
    assert all(r["DeletionPolicy"] == r["UpdateReplacePolicy"] == "Retain"
               for r in template["Resources"].values())


def test_storage_preserves_existing_security_and_lifecycle_design():
    resources = build_template()["Resources"]
    original = foundation_template()["Resources"]
    for name, resource in resources.items():
        properties = dict(resource["Properties"])
        if resource["Type"] in {"AWS::KMS::Key", "AWS::S3::Bucket"}:
            assert properties.pop("Tags") == [
                {"Key": "Project", "Value": "FinTrust"}, {"Key": "Environment", "Value": "dev"}
            ]
        assert properties == original[name]["Properties"]
    for label in ("Raw", "Quarantine", "Reports"):
        bucket = resources[label + "Bucket"]["Properties"]
        assert bucket["BucketName"]["Fn::Sub"] == (
            "fintrust-" + label.lower() + "-${AWS::AccountId}-${AWS::Region}-${Stage}"
        )
        assert all(bucket["PublicAccessBlockConfiguration"].values())
        assert bucket["VersioningConfiguration"]["Status"] == "Enabled"
        assert bucket["OwnershipControls"]["Rules"] == [{"ObjectOwnership": "BucketOwnerEnforced"}]
        encryption = bucket["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        assert encryption["BucketKeyEnabled"] is True
        assert encryption["ServerSideEncryptionByDefault"] == {
            "SSEAlgorithm": "aws:kms", "KMSMasterKeyID": {"Fn::GetAtt": ["DataKey", "Arn"]}
        }
        policy = resources[label + "BucketPolicy"]["Properties"]["PolicyDocument"]
        assert len(policy["Statement"]) == 5
        assert all(s["Effect"] == "Deny" for s in policy["Statement"])
        assert {s["Sid"] for s in policy["Statement"]} == {
            "RequireTls", "RejectExplicitOtherEncryption", "RejectKmsWithoutKey",
            "RejectCustomerProvidedKeys", "RejectExplicitOtherKey",
        }


def test_storage_references_do_not_depend_on_other_stages():
    template = build_template()
    allowed = set(template["Resources"]) | {"Stage", "AWS::Partition", "AWS::AccountId", "AWS::Region"}
    def check(value):
        if isinstance(value, dict):
            if "Ref" in value:
                assert value["Ref"] in allowed
            if "Fn::GetAtt" in value:
                assert value["Fn::GetAtt"][0] in template["Resources"]
            if "Fn::Sub" in value:
                import re
                assert all(token.split(".")[0] in allowed
                           for token in re.findall(r"\$\{([^}]+)\}", value["Fn::Sub"]))
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(template)
    assert "deployment/" not in json.dumps(template)  # Prefix is reserved, not an uploaded object.

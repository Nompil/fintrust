"""Security boundary checks for proposed, unattached Stage 2 permissions."""
import json
from pathlib import Path

ROOT = Path("infrastructure/iam")

def policies():
    return {name: json.loads((ROOT / ("stage2-" + name + "-policy.json")).read_text())
            for name in ("cloudformation", "s3", "kms")}

def statements(name):
    return {s["Sid"]: s for s in policies()[name]["Statement"]}

def test_every_statement_is_regional_and_each_managed_document_fits():
    for policy in policies().values():
        assert len(json.dumps(policy, separators=(",", ":"))) <= 6144
        for s in policy["Statement"]:
            assert s["Condition"]["StringEquals"]["aws:RequestedRegion"] == "af-south-1"
            assert "Principal" not in s
            assert s["Effect"] == "Allow"

def test_cloudformation_cannot_target_other_stacks_or_import_roles():
    values = statements("cloudformation")
    prepare = values["PrepareStorage"]
    assert prepare["Condition"]["Null"] == {
        "cloudformation:ResourceTypes": "false", "cloudformation:RoleArn": "true",
        "cloudformation:ImportResourceTypes": "true"}
    assert set(prepare["Condition"]["ForAllValues:StringEquals"]["cloudformation:ResourceTypes"]) == {
        "AWS::KMS::Key", "AWS::KMS::Alias", "AWS::S3::Bucket", "AWS::S3::BucketPolicy"}
    for sid, s in values.items():
        if sid != "ValidateStorage":
            assert s["Resource"] == "arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-storage-dev/*"
    assert "StringLike" not in values["ReadStorage"]["Condition"]
    assert values["ManageStorageSet"]["Condition"]["StringLike"] == {
        "cloudformation:ChangeSetName": "fintrust-storage-*"}

def test_bucket_grants_have_exact_names_and_no_object_or_delete_rights():
    expected = {"arn:aws:s3:::fintrust-" + name + "-966467878406-af-south-1-dev"
                for name in ("raw", "quarantine", "reports")}
    for s in policies()["s3"]["Statement"]:
        resources = {s["Resource"]} if isinstance(s["Resource"], str) else set(s["Resource"])
        if s["Sid"] == "ManageRawBucketNotifications":
            assert resources == {"arn:aws:s3:::fintrust-raw-966467878406-af-south-1-dev"}
            assert set(s["Action"]) == {"s3:GetBucketNotification", "s3:PutBucketNotification"}
        else:
            assert resources == expected
        assert not any("Object" in a or "Delete" in a for a in s["Action"])
        if s["Sid"] not in {"InspectNamedBuckets", "ManageRawBucketNotifications"}:
            assert s["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]
    assert statements("s3")["CreateNamedBuckets"]["Condition"]["StringEquals"]["s3:LocationConstraint"] == "af-south-1"

def test_key_creation_alias_and_administration_are_bounded():
    values=statements("kms")
    create=values["CreateTaggedKey"]
    assert create["Resource"] == "*"
    assert create["Condition"]["BoolIfExists"] == {"kms:BypassPolicyLockoutSafetyCheck":"false"}
    assert create["Condition"]["Bool"] == {"kms:MultiRegion": "false"}
    for key, value in {"kms:KeySpec":"SYMMETRIC_DEFAULT", "kms:KeyUsage":"ENCRYPT_DECRYPT",
                       "kms:KeyOrigin":"AWS_KMS", "aws:RequestTag/Project":"FinTrust",
                       "aws:RequestTag/Environment":"dev"}.items():
        assert create["Condition"]["StringEquals"][key] == value
    assert values["CreateNamedAlias"]["Resource"] == "arn:aws:kms:af-south-1:966467878406:alias/fintrust-dev"
    for sid in ("InspectOwnedKey", "ConfigureOwnedKey", "AuthorizeAliasTarget"):
        condition=values[sid]["Condition"]["StringEquals"]
        assert condition["aws:ResourceTag/Project"] == "FinTrust"
        assert condition["aws:ResourceTag/Environment"] == "dev"
    assert values["ConfigureOwnedKey"]["Condition"]["BoolIfExists"] == {
        "kms:BypassPolicyLockoutSafetyCheck":"false"}
    for s in values.values():
        assert not any(a in {"kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:CreateGrant",
                            "kms:ScheduleKeyDeletion", "kms:DisableKey", "kms:DeleteAlias",
                            "kms:UpdateAlias", "kms:UntagResource"} for a in s["Action"])
        if s["Sid"] != "InspectAliases" and s["Sid"] != "InspectOwnedKey":
            assert s["Condition"]["ForAnyValue:StringEquals"]["aws:CalledVia"] == ["cloudformation.amazonaws.com"]

def test_only_supported_wildcard_grants_exist_and_no_unrelated_services():
    for name, policy in policies().items():
        for s in policy["Statement"]:
            assert all(a.startswith(name + ":" if name != "cloudformation" else "cloudformation:") for a in s["Action"])
            if s["Resource"] == "*":
                assert s["Sid"] in {"ValidateStorage", "CreateTaggedKey", "InspectAliases"}
            assert not any("*" in a for a in s["Action"])

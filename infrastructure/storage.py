"""Render Stage 2 encrypted storage only; never call AWS."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from infrastructure.foundation import build_template as foundation_template


RESOURCE_NAMES = (
    "DataKey", "DataKeyAlias", "RawBucket", "RawBucketPolicy",
    "QuarantineBucket", "QuarantineBucketPolicy", "ReportsBucket", "ReportsBucketPolicy",
)


def build_template():
    foundation = foundation_template()
    resources = {name: deepcopy(foundation["Resources"][name]) for name in RESOURCE_NAMES}
    tags = [{"Key": "Project", "Value": "FinTrust"}, {"Key": "Environment", "Value": "dev"}]
    for name, resource in resources.items():
        if resource["Type"] in {"AWS::KMS::Key", "AWS::S3::Bucket"}:
            resource["Properties"]["Tags"] = deepcopy(tags)
        # Keep access controls and alias with the retained data/key during teardown.
        resource["DeletionPolicy"] = "Retain"
        resource["UpdateReplacePolicy"] = "Retain"
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "FinTrust Stage 2 private encrypted storage; separate approval required",
        "Parameters": {"Stage": {"Type": "String", "Default": "dev", "AllowedValues": ["dev"]}},
        "Resources": resources,
        "Outputs": {name: deepcopy(foundation["Outputs"][name]) for name in
                    ("RawBucket", "QuarantineBucket", "ReportsBucket", "DataKeyArn")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/stage2-storage.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print("Rendered Stage 2 storage only; no AWS resources changed.")


if __name__ == "__main__":
    main()

"""Render Stage 5 ingest only; validate retained Linux package offline."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import zipfile

from infrastructure.processing import build_template as processing_template
from tools.package_lambda import HANDLERS, verify_archive

ACCOUNT = "966467878406"
REGION = "af-south-1"
PACKAGE_SHA256 = "d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62"
CODE_BUCKET = "fintrust-reports-966467878406-af-south-1-dev"
CODE_KEY = "deployment/lambda/" + PACKAGE_SHA256 + "/fintrust.zip"
ROLE_ARN = "arn:aws:iam::966467878406:role/fintrust-ingest-dev"


def verify_package(path):
    path = Path(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    actual = verify_archive(path)
    if any(manifest.get(key) != value for key, value in actual.items()):
        raise ValueError("Package checksum/size manifest mismatch")
    if actual["sha256"] != PACKAGE_SHA256:
        raise ValueError("Package differs from the reviewed Linux artifact")
    if manifest.get("runtime") != "python3.12" or manifest.get("architecture") != "x86_64":
        raise ValueError("Wrong package runtime or architecture")
    probe = manifest.get("linux_verification", {})
    if manifest.get("linux_execution_verified") is not True or set(probe.get("handlers_imported", [])) != set(HANDLERS.values()):
        raise ValueError("Missing successful Linux handler evidence")
    if not probe.get("psycopg_native_loaded") or not probe.get("ca_loaded") or probe.get("network_attempts") != []:
        raise ValueError("Incomplete Linux dependency/CA/network evidence")
    if probe.get("machine") != "x86_64" or not str(probe.get("python", "")).startswith("3.12.") or not str(probe.get("platform", "")).startswith("Linux-"):
        raise ValueError("Wrong Linux execution platform")
    evidence = json.loads(path.with_name("ci-evidence.json").read_text())
    if evidence.get("package") != manifest or evidence.get("tests", {}).get("tests", 0) <= 0 or any(evidence.get("tests", {}).get(k, 1) != 0 for k in ("failures", "errors", "skipped")):
        raise ValueError("Missing matching green CI evidence")
    # Git checkouts on Windows may convert text line endings. No ZIP is changed.
    with zipfile.ZipFile(path) as archive:
        for folder in ("fintrust", "src", "frontend"):
            for source in Path(folder).rglob("*"):
                if source.is_file() and "__pycache__" not in source.parts and source.suffix in {".py", ".html", ".js", ".css"}:
                    name = source.as_posix()
                    if source.read_bytes().replace(b"\r\n", b"\n") != archive.read(name).replace(b"\r\n", b"\n"):
                        raise ValueError("Package source differs: " + name)
        name = "sql/monthly_summary.sql"
        if Path(name).read_bytes().replace(b"\r\n", b"\n") != archive.read(name).replace(b"\r\n", b"\n"):
            raise ValueError("Package SQL differs")
    return manifest


def build_template():
    legacy = processing_template()["Resources"]
    resources = {name: deepcopy(legacy[name]) for name in ("IngestLogs", "IngestFunction", "IngestAsync")}
    tags = [{"Key": "Project", "Value": "FinTrust"}, {"Key": "Environment", "Value": "dev"}]
    logs = resources["IngestLogs"]
    logs["Properties"]["LogGroupName"] = "/aws/lambda/fintrust-ingest-dev"
    logs["Properties"]["Tags"] = deepcopy(tags)
    logs["DeletionPolicy"] = logs["UpdateReplacePolicy"] = "Retain"
    function = resources["IngestFunction"]["Properties"]
    function.update(FunctionName="fintrust-ingest-dev", Role=ROLE_ARN, Architectures=["x86_64"],
                    ReservedConcurrentExecutions=0, Tags=tags,
                    Code={"S3Bucket": CODE_BUCKET, "S3Key": CODE_KEY, "S3ObjectVersion": {"Ref": "CodeObjectVersion"}})
    function["Environment"] = {"Variables": {
        "FINTRUST_SERVICE": "ingest", "FINTRUST_STAGE": "dev",
        "TRANSACTION_QUEUE_URL": "https://sqs.af-south-1.amazonaws.com/966467878406/fintrust-transactions-dev.fifo",
        "QUARANTINE_BUCKET": "fintrust-quarantine-966467878406-af-south-1-dev",
    }}
    resources["IngestAsync"]["Properties"]["DestinationConfig"]["OnFailure"]["Destination"] = "arn:aws:sqs:af-south-1:966467878406:fintrust-ingest-failures-dev"
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "FinTrust Stage 5 unwired ingest Lambda; separate execution approval required",
        "Parameters": {"CodeObjectVersion": {"Type": "String", "MinLength": 1,
            "AllowedPattern": "(?!null$)[A-Za-z0-9._+/=-]+", "Description": "Verified version ID of the approved package object"}},
        "Resources": resources,
        "Outputs": {"IngestFunctionArn": {"Value": {"Fn::GetAtt": ["IngestFunction", "Arn"]}}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path("build/ci-evidence/37342810131/fintrust-linux-verified/fintrust.zip"))
    parser.add_argument("--output", type=Path, default=Path("build/stage5-ingest.json"))
    args = parser.parse_args()
    manifest = verify_package(args.package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print("Package checksum and retained Linux evidence verified: " + manifest["sha256"])
    print("Rendered Stage 5 ingest only; no AWS resources changed.")


if __name__ == "__main__":
    main()

"""Validate a supplied release candidate before extraction; never build or access AWS."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

try:
    from .package_lambda import verify_archive
except ImportError:
    from package_lambda import verify_archive

SOURCE = Path("release-verification/fintrust-hardened.zip")
TARGET = Path("build/hardened-release/fintrust-hardened.zip")


def check_input(source, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Expected checksum must be a reviewed lowercase SHA256")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError("Release ZIP checksum differs; do not extract or rebuild")
    evidence = verify_archive(source)
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            name = info.filename
            parts = Path(name).parts
            if (name.startswith(("/", "\\")) or ".." in parts or "\\" in name
                    or any(part.startswith(".env") for part in parts)
                    or any(part in {".aws", ".git", "__pycache__", "tests", "test-results", "docs", "project-reference", ".venv", "venv"} for part in parts)
                    or name.endswith((".pyc", ".pyd", ".dll", ".exe", ".key", ".p12", ".pfx"))
                    or name.startswith("boto3/examples/")
                    or (name.startswith("botocore/data/") and name.endswith("/examples-1.json"))):
                raise ValueError(f"Unexpected or development-only archive member: {name}")
            data = archive.read(info)
            if (re.search(rb"(?:AKIA|ASIA)[A-Z0-9]{16}", data)
                    or re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data)):
                raise ValueError(f"Credential pattern found in archive member: {name}")
    return evidence


if __name__ == "__main__":
    evidence = check_input(SOURCE, os.environ["RELEASE_SHA256"])
    manifest = json.loads(SOURCE.with_suffix(".manifest.json").read_text())
    for key, value in evidence.items():
        if manifest.get(key) != value:
            raise ValueError(f"Release manifest mismatch: {key}")
    # Tests from this checkout must represent the supplied first-party code.
    with zipfile.ZipFile(SOURCE) as archive:
        for package in ("fintrust", "src"):
            local = {str(path.relative_to(Path.cwd())).replace("\\", "/")
                     for path in (Path.cwd() / package).rglob("*.py")}
            packaged = {name for name in archive.namelist()
                        if name.startswith(package + "/") and name.endswith(".py")}
            if local != packaged:
                raise ValueError(f"Release source file set differs: {package}")
            for name in local:
                if archive.read(name).replace(b"\r\n", b"\n") != Path(name).read_bytes().replace(b"\r\n", b"\n"):
                    raise ValueError(f"Release source differs from tested checkout: {name}")
    # Execution evidence cannot be inherited from a previous runner.
    manifest["linux_execution_verified"] = False
    manifest.pop("linux_verification", None)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, TARGET)
    TARGET.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))

"""Build one shared Lambda archive from pinned Linux wheels and a supplied RDS CA.

No AWS calls. Dependency download is from the configured Python package index.
Pass --wheelhouse to build with --no-index using previously downloaded wheels.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = {"ingest": "fintrust.ingest.lambda_handler", "scoring": "fintrust.score.lambda_handler",
            "alert": "fintrust.alert_delivery.lambda_handler", "api": "fintrust.api.lambda_handler",
            "report": "fintrust.report.lambda_handler"}


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {h.rsplit(".", 1)[0].replace(".", "/") + ".py" for h in HANDLERS.values()}
        required |= {"sql/monthly_summary.sql", "certs/global-bundle.pem", "frontend/index.html"}
        if not required <= names:
            raise ValueError("Archive lacks required handlers, SQL, frontend or CA")
        if any(n.endswith((".pyd", ".dll")) or "/.env" in n or n == ".env" for n in names):
            raise ValueError("Archive contains Windows binaries or environment secrets")
        driver = [n for n in names if n.startswith("psycopg2/_psycopg") and n.endswith(".so")]
        if len(driver) != 1 or "cpython-312" not in driver[0] or archive.read(driver[0])[:4] != b"\x7fELF":
            raise ValueError("Expected CPython 3.12 Linux PostgreSQL driver")
        uncompressed = sum(i.file_size for i in archive.infolist())
        if uncompressed >= 250 * 1024 * 1024:
            raise ValueError("Archive exceeds Lambda uncompressed size limit")
        if archive.testzip():
            raise ValueError("Archive CRC verification failed")
    data = path.read_bytes()
    return {"compressed_bytes": len(data), "uncompressed_bytes": uncompressed,
            "direct_upload_under_50_mib": len(data) < 50 * 1024 * 1024,
            "sha256": hashlib.sha256(data).hexdigest(),
            "code_sha256_base64": base64.b64encode(hashlib.sha256(data).digest()).decode()}


def build(ca_bundle, output, wheelhouse=None):
    ca_bundle, output = Path(ca_bundle).resolve(), Path(output).resolve()
    # Parse the certificate bundle before installing dependencies or writing outputs.
    ssl.create_default_context(cafile=str(ca_bundle))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lambda-", dir=output.parent) as temp:
        package = Path(temp)
        command = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-compile",
                   "--platform", "manylinux2014_x86_64", "--implementation", "cp", "--python-version", "3.12",
                   "--only-binary=:all:", "--no-deps", "--target", str(package), "-r", str(ROOT / "requirements-lambda.txt")]
        if wheelhouse:
            command += ["--no-index", "--find-links", str(Path(wheelhouse).resolve())]
        subprocess.run(command, check=True)
        for directory in ("fintrust", "src", "frontend"):
            shutil.copytree(ROOT / directory, package / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env*"))
        (package / "release-info.json").write_text(json.dumps({"source_commit":os.getenv("GITHUB_SHA",os.getenv("FINTRUST_RELEASE_COMMIT","UNDECLARED")),"runtime":"python3.12","architecture":"x86_64"})+"\n")
        (package / "sql").mkdir()
        shutil.copy2(ROOT / "sql/monthly_summary.sql", package / "sql/monthly_summary.sql")
        (package / "certs").mkdir()
        shutil.copy2(ca_bundle, package / "certs/global-bundle.pem")
        # Fixed ZIP metadata and ordered entries make builds repeatable with identical inputs.
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(path.relative_to(package).as_posix())
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
    manifest = {"runtime": "python3.12", "architecture": "x86_64", "handlers": HANDLERS,
                "source_commit":os.getenv("GITHUB_SHA",os.getenv("FINTRUST_RELEASE_COMMIT","UNDECLARED")), "ca_sha256": hashlib.sha256(ca_bundle.read_bytes()).hexdigest(), **verify_archive(output),
                "linux_execution_verified": False}
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca-bundle", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build/fintrust.zip")
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.ca_bundle, args.output, args.wheelhouse), indent=2))

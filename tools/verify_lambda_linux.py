"""Import archived handlers on Linux CPython 3.12 without network access."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile

try:
    from .package_lambda import HANDLERS, verify_archive
except ImportError:
    from package_lambda import HANDLERS, verify_archive


def validate_manifest(manifest, evidence):
    expected = {**evidence, "runtime": "python3.12", "architecture": "x86_64", "handlers": HANDLERS}
    for name, value in expected.items():
        if manifest.get(name) != value:
            raise ValueError(f"Manifest mismatch: {name}")


def report_probe_failure(error, environment):
    sensitive = ("SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL", "PRIVATE_KEY", "ACCESS_KEY", "DATABASE_URL")
    values = {value for source in (os.environ, environment) for key, value in source.items()
              if value and any(marker in key.upper() for marker in sensitive)}
    print(f"Lambda import probe failed (return code {error.returncode}).", file=sys.stderr)
    for label, output in (("stdout", error.stdout), ("stderr", error.stderr)):
        output = output or "<empty>"
        for value in sorted(values, key=len, reverse=True):
            output = output.replace(value, "[REDACTED]")
        print(f"Probe {label}:\n{output}", file=sys.stderr)


def verify(path, all_production=False):
    if (platform.system() != "Linux" or sys.version_info[:2] != (3, 12)
            or platform.python_implementation() != "CPython" or platform.machine() != "x86_64"):
        raise RuntimeError("This verification requires Linux x86_64 and CPython 3.12")
    path = Path(path).resolve()
    evidence = verify_archive(path)
    manifest_path = path.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest, evidence)
    manifest["linux_execution_verified"] = False
    manifest.pop("linux_verification", None)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="fintrust-import-") as folder:
        with zipfile.ZipFile(path) as archive:
            root = Path(folder).resolve()
            if any(not (root / name).resolve().is_relative_to(root) for name in archive.namelist()):
                raise ValueError("Unsafe archive member")
            archive.extractall(root)
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("AWS_", "DB_", "FINTRUST_"))}
        environment.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
                           AWS_DEFAULT_REGION="af-south-1", AWS_REGION="af-south-1",
                           AWS_EC2_METADATA_DISABLED="true", DB_CONFIG_SOURCE="environment",
                           DB_AUTH_MODE="iam", DB_HOST="db.invalid", DB_NAME="fintrust",
                           DB_USER="fintrust_api_dev", FINTRUST_SERVICE="api", FINTRUST_STAGE="dev",
                           DB_SSLROOTCERT=str(root / "certs/global-bundle.pem"))
        try:
            result = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("lambda_import_probe.py")),
                                     str(root), json.dumps(list(HANDLERS.values())),
                                     *(["--all-production"] if all_production else [])],
                                    cwd=root, env=environment, check=True, timeout=60,
                                    capture_output=True, text=True)
        except subprocess.CalledProcessError as error:
            report_probe_failure(error, environment)
            raise
        probe = json.loads(result.stdout)
    if probe["ca_sha256"] != manifest.get("ca_sha256"):
        raise ValueError("Manifest mismatch: ca_sha256")
    validate_manifest(manifest, verify_archive(path))
    manifest["linux_verification"] = {**probe, "machine": platform.machine(),
                                      "python": platform.python_version(), "platform": platform.platform()}
    manifest["linux_execution_verified"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"All {len(HANDLERS)} archived handlers imported on Linux CPython 3.12.")


if __name__ == "__main__":
    verify(sys.argv[1], "--all-production" in sys.argv[2:])

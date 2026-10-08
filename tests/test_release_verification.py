"""Fail closed before extraction and check modules unreachable from a handler."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from tools import verify_release_input as release


def test_checksum_mismatch_rejected_before_archive_inspection(tmp_path, monkeypatch):
    path = tmp_path / "candidate.zip"
    path.write_bytes(b"not even an archive")
    def unexpected_inspection(path):
        pytest.fail("Checksum must be checked before reading archive members")
    monkeypatch.setattr(release, "verify_archive", unexpected_inspection)
    with pytest.raises(ValueError, match="checksum differs"):
        release.check_input(path, "0" * 64)


@pytest.mark.parametrize("name,data", [
    (".env", b"local configuration"),
    ("fintrust/__pycache__/cached.pyc", b"cache"),
    ("tests/example.py", b"test"),
    ("../outside.py", b"unsafe"),
    ("boto3/examples/sample.rst", b"example"),
    ("botocore/data/sts/2011-06-15/examples-1.json", b"example"),
    ("fintrust/bad.py", b"AKIA" + b"A" * 16),
    ("fintrust/bad.py", b"-----BEGIN PRIVATE KEY-----"),
    ("windows.exe", b"MZ"),
])
def test_release_input_rejects_secret_dev_or_unsafe_material(tmp_path, monkeypatch, name, data):
    path = tmp_path / "candidate.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, data)
    monkeypatch.setattr(release, "verify_archive", lambda _: {})
    with pytest.raises(ValueError, match="archive member"):
        release.check_input(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_all_production_probe_checks_module_not_reachable_from_handler(tmp_path):
    package = tmp_path / "fintrust"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "handler.py").write_text("def handler(event, context): pass\n")
    (package / "unreferenced.py").write_text("import socket\nsocket.getaddrinfo('invalid.example', 443)\n")
    probe = Path(__file__).resolve().parents[1] / "tools/lambda_import_probe.py"
    result = subprocess.run([sys.executable, "-I", str(probe), str(tmp_path),
                             json.dumps(["fintrust.handler.handler"]), "--all-production"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert '"module": "fintrust.unreferenced"' in result.stderr
    assert '"operation": "socket.getaddrinfo"' in result.stderr


def test_failed_run_records_unknown_imports_without_claiming_verification(tmp_path, monkeypatch):
    from tools import record_release_verification as recorder
    monkeypatch.chdir(tmp_path)
    for key, value in {"GITHUB_SHA": "test-only", "GITHUB_RUN_ID": "0",
                       "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REPOSITORY": "test/fixture",
                       "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
                       "RELEASE_SHA256": "0" * 64}.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match="gate failed"):
        recorder.record()
    evidence = json.loads((tmp_path / "docs/EVIDENCE/11-ci/hardened-release-linux-ci.json").read_text())
    assert evidence["linux_execution_verified"] is False
    assert evidence["release_gate_passed"] is False
    assert evidence["tests"] is None
    assert evidence["artifact_sha256"] is None

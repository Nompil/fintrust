import zipfile
import json
from pathlib import Path
import subprocess
import sys
import pytest

from tools.package_lambda import HANDLERS, verify_archive
from infrastructure.ssm.put_parameters import build_parameters
from tools.verify_lambda_linux import validate_manifest


@pytest.mark.parametrize("field", ["sha256", "code_sha256_base64", "uncompressed_bytes", "architecture", "runtime", "handlers"])
def test_execution_gate_rejects_mismatched_manifest(field):
    evidence = {"sha256": "digest", "code_sha256_base64": "encoded", "uncompressed_bytes": 120}
    manifest = {**evidence, "architecture": "x86_64", "runtime": "python3.12", "handlers": HANDLERS}
    validate_manifest(manifest, evidence)
    manifest[field] = "incorrect"
    with pytest.raises(ValueError, match=field):
        validate_manifest(manifest, evidence)


@pytest.mark.parametrize("operation", ["socket.getaddrinfo('db.invalid', 5432)",
                                      "socket.socket().connect(('127.0.0.1', 9))"])
def test_import_probe_blocks_network_before_connection(tmp_path, operation):
    (tmp_path / "network_handler.py").write_text(
        f"import socket\n{operation}\ndef handler(event, context): pass\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "tools/lambda_import_probe.py"
    result = subprocess.run([sys.executable, "-I", str(script), str(tmp_path),
                             json.dumps(["network_handler.handler"])],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "Network access attempted during package verification" in result.stderr


def test_archive_rejects_missing_runtime_assets(tmp_path):
    path = tmp_path / "lambda.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("fintrust/api.py", "")
    with pytest.raises(ValueError, match="lacks required"):
        verify_archive(path)


@pytest.mark.parametrize("driver,content", [
    ("psycopg2/_psycopg.cp312-win_amd64.pyd", b"MZ"),
    ("psycopg2/_psycopg.cpython-311-x86_64-linux-gnu.so", b"\x7fELF"),
    ("psycopg2/_psycopg.cpython-312-x86_64-linux-gnu.so", b"MZ"),
])
def test_archive_rejects_wrong_native_driver(tmp_path, driver, content):
    path = tmp_path / "lambda.zip"
    names = {h.rsplit(".", 1)[0].replace(".", "/") + ".py" for h in HANDLERS.values()}
    names |= {"sql/monthly_summary.sql", "certs/global-bundle.pem", "frontend/index.html"}
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, "")
        archive.writestr(driver, content)
    with pytest.raises(ValueError, match="Windows|CPython"):
        verify_archive(path)


def test_parameter_rendering_only_for_database_services(monkeypatch):
    monkeypatch.setenv("FINTRUST_DB_HOST", "db.invalid")
    monkeypatch.setenv("FINTRUST_STAGE", "dev")
    for service in ("scoring", "api", "report"):
        monkeypatch.setenv("FINTRUST_SERVICE", service)
        params = build_parameters()
        assert {p["Name"] for p in params} == {
            f"/fintrust/dev/{service}/db_{field}" for field in ("host", "name", "user")}
        assert all(p["Type"] == "String" for p in params)
        assert params[-1]["Value"] == f"fintrust_{service}_dev"
    for service in ("ingest", "alert"):
        monkeypatch.setenv("FINTRUST_SERVICE", service)
        with pytest.raises(ValueError, match="Invalid service"):
            build_parameters()

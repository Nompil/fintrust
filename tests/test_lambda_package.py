import zipfile
import json
from pathlib import Path
import subprocess
import sys
import pytest

from tools.package_lambda import HANDLERS, verify_archive
from infrastructure.ssm.put_parameters import build_parameters
from tools.verify_lambda_linux import validate_manifest
from tools import verify_lambda_linux


def test_failed_probe_surfaces_diagnostics_and_keeps_manifest_unverified(tmp_path, monkeypatch, capsys):
    path = tmp_path / "lambda.zip"
    with zipfile.ZipFile(path, "w"):
        pass
    manifest_path = path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps({"linux_execution_verified": True,
                                         "linux_verification": {"old": "evidence"}}))
    monkeypatch.setattr(verify_lambda_linux.platform, "system", lambda: "Linux")
    monkeypatch.setattr(verify_lambda_linux.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(verify_lambda_linux.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(verify_lambda_linux.sys, "version_info", (3, 12))
    monkeypatch.setattr(verify_lambda_linux, "verify_archive", lambda path: {})
    monkeypatch.setattr(verify_lambda_linux, "validate_manifest", lambda *args: None)
    monkeypatch.setenv("DB_PASSWORD", "private-db-value")
    monkeypatch.setenv("GITHUB_TOKEN", "private-token-value")
    failure = subprocess.CalledProcessError(
        7, ["probe"], output="stage: import; private-db-value",
        stderr="ModuleNotFoundError: missing_module; private-token-value")

    def fail(*args, **kwargs):
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        raise failure

    monkeypatch.setattr(verify_lambda_linux.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError) as rejected:
        verify_lambda_linux.verify(path)
    assert rejected.value is failure
    output = capsys.readouterr()
    assert output.out == ""
    assert "return code 7" in output.err
    assert "Probe stdout:\nstage: import; [REDACTED]" in output.err
    assert "Probe stderr:\nModuleNotFoundError: missing_module; [REDACTED]" in output.err
    assert "private-db-value" not in output.err
    assert "private-token-value" not in output.err
    manifest = json.loads(manifest_path.read_text())
    assert manifest["linux_execution_verified"] is False
    assert "linux_verification" not in manifest


def test_failed_probe_labels_empty_streams(capsys):
    verify_lambda_linux.report_probe_failure(subprocess.CalledProcessError(1, ["probe"]), {})
    output = capsys.readouterr().err
    assert "Probe stdout:\n<empty>" in output
    assert "Probe stderr:\n<empty>" in output


@pytest.mark.parametrize("field", ["sha256", "code_sha256_base64", "uncompressed_bytes", "architecture", "runtime", "handlers"])
def test_execution_gate_rejects_mismatched_manifest(field):
    evidence = {"sha256": "digest", "code_sha256_base64": "encoded", "uncompressed_bytes": 120}
    manifest = {**evidence, "architecture": "x86_64", "runtime": "python3.12", "handlers": HANDLERS}
    validate_manifest(manifest, evidence)
    manifest[field] = "incorrect"
    with pytest.raises(ValueError, match=field):
        validate_manifest(manifest, evidence)


@pytest.mark.parametrize("operation", ["socket.getaddrinfo('db.invalid', 5432)",
                                      "socket.socket().connect(('127.0.0.1', 9))",
                                      "socket.socket().bind(('127.0.0.1', 0))"])
def test_import_probe_blocks_network_before_connection(tmp_path, operation):
    (tmp_path / "network_handler.py").write_text(
        f"import socket\n{operation}\ndef handler(event, context): pass\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "tools/lambda_import_probe.py"
    result = subprocess.run([sys.executable, "-I", str(script), str(tmp_path),
                             json.dumps(["network_handler.handler"])],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "Network access attempted during package verification" in result.stderr
    line = next(line for line in result.stderr.splitlines() if line.startswith("Blocked network operation: "))
    diagnostic = json.loads(line.removeprefix("Blocked network operation: "))
    assert diagnostic["operation"].startswith("socket.")
    assert any(frame["module"] == "network_handler" and frame["line"] == 2
               for frame in diagnostic["stack"])


def test_caught_network_rejection_still_reports_caller_without_locals(tmp_path):
    (tmp_path / "network_handler.py").write_text(
        "import socket\n"
        "def check_socket():\n"
        "    credential = 'private-value-not-for-logs'\n"
        "    try:\n"
        "        with socket.socket() as sock:\n"
        "            sock.bind(('127.0.0.1', 0))\n"
        "    except RuntimeError:\n"
        "        print('rejection caught')\n"
        "check_socket()\n"
        "raise ValueError('stop after diagnostic')\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "tools/lambda_import_probe.py"
    result = subprocess.run([sys.executable, "-I", str(script), str(tmp_path),
                             json.dumps(["network_handler.handler"])],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert result.stdout.strip() == "rejection caught"
    line = next(line for line in result.stderr.splitlines() if line.startswith("Blocked network operation: "))
    diagnostic = json.loads(line.removeprefix("Blocked network operation: "))
    assert diagnostic["operation"] == "socket.bind"
    assert diagnostic["stack"][0] == {"module": "network_handler", "function": "check_socket",
                                      "file": str(tmp_path / "network_handler.py"), "line": 6}
    assert "private-value-not-for-logs" not in result.stderr
    assert "127.0.0.1" not in line


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

import zipfile
import pytest

from tools.package_lambda import HANDLERS, verify_archive
from infrastructure.ssm.put_parameters import build_parameters


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

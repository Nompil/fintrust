import os

import pytest

from tools import local


@pytest.fixture
def practice_settings(monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    values = {"DB_HOST": "127.0.0.1", "DB_NAME": local.DATABASE,
        "DB_PORT": "5432", "DB_USER": local.ROLE, "DB_PASSWORD": "test-only",
        "FINTRUST_MODE": "local", "AWS_REGION": "af-south-1", "DYNAMODB_TABLE": "risk_scores"}
    monkeypatch.setattr(local, "local_settings", lambda: values)
    return values


def test_local_commands_reject_a_remote_database(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("DB_HOST=example.com\n")
    with pytest.raises(ValueError, match="DB_HOST"):
        local.local_settings()


def test_setup_preserves_an_unrelated_env_file(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "ROOT", tmp_path)
    original = "DB_NAME=other_project\nDB_USER=other_user\n"
    (tmp_path / ".env").write_text(original)
    with pytest.raises(ValueError, match="left unchanged"):
        local.setup()
    assert (tmp_path / ".env").read_text() == original


def test_setup_saves_only_application_credentials(tmp_path, monkeypatch):
    import psycopg2
    from dotenv import dotenv_values
    monkeypatch.setattr(local, "ROOT", tmp_path)
    (tmp_path / "sql").mkdir()
    for filename in ("schema.sql", "seed.sql", "views.sql", "procedure.sql"):
        (tmp_path / "sql" / filename).write_text("SELECT 1;")
    commands = []
    class Connection:
        def cursor(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, statement, parameters=None): commands.append(str(statement))
        def fetchone(self): return None
        def commit(self): pass
        def close(self): pass
    monkeypatch.setattr(psycopg2, "connect", lambda **kw: Connection())
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setattr(local, "getpass", lambda prompt: "admin-private")
    monkeypatch.setattr(local, "check", lambda: None)
    local.setup()
    values = dotenv_values(tmp_path / ".env")
    assert values["DB_USER"] == local.ROLE
    assert values["DB_NAME"] == local.DATABASE
    assert len(values["DB_PASSWORD"]) >= 32
    assert "admin-private" not in (tmp_path / ".env").read_text()
    assert sum("CREATE DATABASE" in statement for statement in commands) == 2


def test_unit_command_ignores_an_existing_database_url(monkeypatch):
    monkeypatch.setenv("FINTRUST_TEST_DATABASE_URL", "do-not-use")
    captured = {}
    def run(args, **kwargs):
        captured.update(kwargs)
        scratch = local.Path(args[args.index("--basetemp") + 1])
        assert scratch.parent.name.startswith("fintrust-tests-")
        assert scratch.parent.is_dir()
        captured["scratch"] = scratch
        return 0
    monkeypatch.setattr(local.subprocess, "call", run)
    assert local.test() == 0
    assert "FINTRUST_TEST_DATABASE_URL" not in captured["env"]
    assert not captured["scratch"].parent.exists()


def test_database_command_selects_only_the_test_database(practice_settings, monkeypatch):
    from psycopg2.extensions import parse_dsn
    captured = {}
    monkeypatch.setattr(local.subprocess, "call", lambda args, **kw: captured.update(kw) or 0)
    assert local.test(database=True) == 0
    settings = parse_dsn(captured["env"]["FINTRUST_TEST_DATABASE_URL"])
    assert settings["dbname"] == local.TEST_DATABASE
    assert settings["dbname"] != local.DATABASE


def test_local_ingestion_exports_both_rejected_rows(practice_settings, tmp_path, monkeypatch):
    from fintrust import ingest
    sample = (local.ROOT / "samples/transactions_day2.csv").read_text()
    (tmp_path / "samples").mkdir()
    (tmp_path / "samples/transactions_day2.csv").write_text(sample)
    monkeypatch.setattr(local, "ROOT", tmp_path)
    rows = []
    monkeypatch.setattr(ingest, "_load_rows", lambda values: rows.extend(values) or [])
    local.ingest_sample()
    assert len(rows) == 2
    quarantine = (tmp_path / "output/local/quarantine.jsonl").read_text()
    assert len(quarantine.splitlines()) == 2
    assert "greater than zero" in quarantine
    assert "unsupported currency" in quarantine


def test_local_api_uses_a_labelled_mock_score(practice_settings, monkeypatch):
    from fintrust import api
    monkeypatch.setattr(local, "check", lambda: None)
    responses = []
    def run(**kwargs):
        assert kwargs["host"] == "127.0.0.1"
        response = api.app.test_client().get(f"/v1/insights?account_id={local.ACCOUNT}")
        responses.append(response)
    monkeypatch.setattr(api.app, "run", run)
    local.serve()
    assert responses[0].status_code == 200
    data = responses[0].get_json()["data"]
    assert data["risk_score"] == "45"
    assert data["flags"] == ["practice_fixture"]
    assert "ttl" not in data

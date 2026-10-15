"""Fail-closed extension surface; real transaction/ACL proof is PG16 rehearsal."""
import ast
import hashlib
from pathlib import Path
from unittest.mock import Mock
import pytest
from migration_runner import common, extensions

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("version", [3, 4, 5, 6])
def test_bound_sql_and_transaction_wrapper(version):
    name, digest = extensions.MIGRATIONS[version]
    source = (ROOT / "sql/migrations" / name).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(source).hexdigest() == digest
    body = extensions.migration_body(version)
    assert body and not body.endswith("COMMIT;\n")


@pytest.mark.parametrize("version", [3, 4, 5, 6])
def test_changed_source_refused_before_sql(version, tmp_path, monkeypatch):
    name, _ = extensions.MIGRATIONS[version]
    folder = tmp_path / "sql/migrations"
    folder.mkdir(parents=True)
    (folder / name).write_text("BEGIN;\nDELETE FROM public.transactions;\nCOMMIT;\n")
    monkeypatch.setattr(extensions.config, "ROOT", tmp_path)
    with pytest.raises(common.Refused, match="source_hash_mismatch"):
        extensions.migration_body(version)


@pytest.mark.parametrize("operation", ["migrate", "migrate002", "migrate007", "bootstrap_extensions", "SELECT 1", "cleanup_extensions"])
def test_executor_rejects_unapproved_operation_without_connection_use(operation):
    conn = Mock()
    with pytest.raises(common.Refused, match="operation_not_allowed"):
        extensions.operate(conn, operation)
    conn.cursor.assert_not_called()


def test_catalog_copy_matches_frozen_application():
    def function(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_catalog_for_version")
    assert ast.dump(function(ROOT / "backend/migration_runner/extension_catalog.py"), include_attributes=False) == ast.dump(
        function(ROOT / "backend/fintrust/migrations.py"), include_attributes=False)


@pytest.mark.parametrize("phase", ["bootstrap_extensions", "iam_extensions", "cleanup_extensions"])
def test_extension_phase_stays_disabled_and_iam_cannot_read_secret(phase):
    from infrastructure.migration import runner_template, runtime_policy
    properties = runner_template(phase)["Resources"]["Runner"]["Properties"]
    assert properties["Handler"] == f"migration_runner.{phase}_entry.lambda_handler"
    assert properties["ReservedConcurrentExecutions"] == 0
    policy = runtime_policy(phase, "vpce-0123456789abcdef0")
    secret = [s for s in policy["Statement"] if "secretsmanager:GetSecretValue" in s["Action"]]
    assert len(secret) == 1
    assert secret[0]["Effect"] == ("Deny" if phase == "iam_extensions" else "Allow")


@pytest.mark.parametrize("field,value", [("sql", "DROP TABLE public.transactions"), ("host", "db.invalid"), ("version", 7)])
def test_handler_request_rejects_sql_host_or_version_overrides(field, value):
    import uuid
    from migration_runner import iam_extensions_entry
    event = {"operation": "migrate003", "request_id": str(uuid.uuid4()), field: value}
    with pytest.raises(common.RunnerFailure):
        iam_extensions_entry.lambda_handler(event, None)

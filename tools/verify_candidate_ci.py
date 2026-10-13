"""Verification-only controller; imports application code from an immutable checkout."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile

SOURCE = "38e2f2fc2f58eca50875b4f22bbc07841036fe54"
ROOT = Path(os.environ["FINTRUST_APPLICATION_ROOT"]).resolve()
OUT = Path(os.environ["FINTRUST_CI_EVIDENCE"]).resolve()
HARNESS = Path(__file__).resolve().parents[1]
ALLOWED = {".github/workflows/ci.yml", "tools/check_release1_roles_pg16.py", "tools/verify_candidate_ci.py"}
BROWSER = {
    "test_v2_component_investigation_browser", "test_workbench_browser",
    "test_investigation_browser", "test_missing_original_evidence_browser",
    "test_owned_unknown_account_browser", "test_named_multi_user_browser",
    "test_three_review_outcomes_browser_database_and_audit",
}
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def binding():
    assert os.environ["APPLICATION_SOURCE_COMMIT"] == SOURCE
    assert git(ROOT, "rev-parse", "HEAD") == SOURCE
    controller = git(HARNESS, "rev-parse", "HEAD")
    assert controller == os.environ["CI_HARNESS_COMMIT"]
    changed = set(git(HARNESS, "diff", "--name-only", SOURCE, controller).splitlines())
    assert changed == ALLOWED, changed
    git(ROOT, "diff", "--exit-code")
    git(ROOT, "diff", "--cached", "--exit-code")
    return {"application_source_commit": SOURCE, "ci_harness_commit": controller,
            "harness_files": sorted(changed), "candidate_tracked_files_unchanged": True,
            "previous_failed_run": "38455884840", "aws_access": False}


def catalog(cur, schema):
    queries = {
        "tables": "SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
        "columns": """SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,
            character_maximum_length,numeric_precision,numeric_scale,is_identity,identity_generation
            FROM information_schema.columns WHERE table_schema=%s ORDER BY table_name,ordinal_position""",
        "constraints": """SELECT c.relname,k.conname,k.contype,k.convalidated,pg_get_constraintdef(k.oid)
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s ORDER BY c.relname,k.conname""",
        "indexes": """SELECT c.relname,i.indisvalid,i.indisready,pg_get_indexdef(i.indexrelid)
            FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s ORDER BY c.relname""",
        "views": "SELECT viewname,definition FROM pg_views WHERE schemaname=%s ORDER BY viewname",
        "functions": """SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s ORDER BY p.proname""",
        "triggers": """SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t
            JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",
    }
    result = {}
    for key, query in queries.items():
        cur.execute(query, (schema,)); result[key] = cur.fetchall()
    return result


def migrations_gate():
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import parse_dsn
    from fintrust import migrations
    dsn = os.environ["FINTRUST_TEST_DATABASE_URL"]
    target = parse_dsn(dsn)
    assert target.get("host") in {"localhost", "127.0.0.1", "::1"}
    assert target.get("dbname") == "fintrust_test"
    conn = psycopg2.connect(dsn)
    schema = "ci_chain_" + uuid.uuid4().hex
    stages = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('server_version'),current_setting('server_version_num')::int")
            version, number = cur.fetchone()
            assert number == 160015, (version, number)
            cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")
            assert cur.fetchone() == (0,), "Migration gate requires an empty disposable database"
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            cur.execute(sql.SQL("SET search_path TO {},pg_catalog").format(sql.Identifier(schema)))
            cur.execute((ROOT / "sql/schema.sql").read_text().split("-- Additive identity hardening.")[0].replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;", ""))
        conn.commit()
        stages.append({"stage": "base", "result": "APPLIED", "seed_rows": 0})
        for number in range(1, 7):
            result = migrations.apply_local(conn, number, schema=schema)
            assert result == "APPLIED"
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass(%s)", (schema + ".transaction_lifecycle_events",))
                lifecycle = cur.fetchone()[0] is not None
                if number <= 2: assert not lifecycle
                else: assert lifecycle
                snapshot = catalog(cur, schema)
                if number == 5: before = snapshot
                if number == 6: after = snapshot
            conn.commit()
            stages.append({"stage": f"{number:03}", "result": result, "lifecycle_table_exists": lifecycle})
        for key in ("tables", "columns", "constraints", "indexes", "views", "triggers"):
            assert before[key] == after[key], f"006 unexpectedly altered {key}"
        before_functions, after_functions = dict(before["functions"]), dict(after["functions"])
        assert before_functions.keys() == after_functions.keys()
        changed = [key for key in before_functions if before_functions[key] != after_functions[key]]
        assert changed == ["guard_review_transition"], changed
        expected = set(migrations.TABLES) | {"customers", "accounts", "transactions", "risk_events", "alerts", "processed_transactions", "schema_migrations", "transaction_lifecycle_events"}
        assert {x[0] for x in after["tables"]} == expected
        assert {x[0] for x in after["views"]} == {"batch_reconciliation", "quarantine_workflow"}
        assert all(x[3] for x in after["constraints"])
        assert {x[2] for x in after["constraints"]} >= {"p", "f", "u", "c"}
        assert all(x[1] and x[2] for x in after["indexes"])
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT version,source_sha256,catalog_sha256 FROM {}.schema_migrations ORDER BY version").format(sql.Identifier(schema)))
            history = cur.fetchall()
        conn.commit()
        assert [x[0] for x in history] == list(range(1, 7))
        assert migrations.apply_local(conn, 6, schema=schema) == "ALREADY_APPLIED"
        write("migrations.json", {**binding(), "status": "PASSED", "postgresql": version,
              "started_from_empty_database": True, "isolated_schema": schema, "stages": stages,
              "migration_006_changed_functions_only": changed, "migration_006_tables_columns_unchanged": True,
              "final_catalog": after, "migration_history": history, "reapply_006": "ALREADY_APPLIED"})
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        conn.commit(); conn.close()


def junit(path):
    cases = ET.parse(path).getroot().findall(".//testcase")
    failures = [x for x in cases if x.find("failure") is not None or x.find("error") is not None]
    skips = [x for x in cases if x.find("skipped") is not None]
    return cases, {"collected": len(cases), "passed": len(cases) - len(failures) - len(skips),
                   "failed": len(failures), "skipped": len(skips)}


def regression():
    cases, counts = junit(OUT / "pytest.xml")
    assert counts == {"collected": 904, "passed": 904, "failed": 0, "skipped": 0}, counts
    gates = {x.get("name"): {"test": x.get("classname") + "::" + x.get("name"), "result": "PASSED"}
             for x in cases if x.get("name") in BROWSER}
    assert gates.keys() == BROWSER, sorted(gates)
    admin = [x for x in cases if x.get("name") == "test_database_roles_can_execute_pipeline_without_owner_privileges"]
    assert len(admin) == 1
    write("regression.json", {**binding(), "status": "PASSED", "counts": counts, "browser_gates": gates,
          "baseline_difference": "Windows: 903 passed / 1 administrator-only skip. Disposable Linux PostgreSQL superuser executes that same test: 904 passed / 0 skipped.",
          "administrator_test": admin[0].get("classname") + "::" + admin[0].get("name")})


def final():
    state = binding()
    regression()
    _, focused = junit(OUT / "focused-v2.xml")
    assert focused == {"collected": 51, "passed": 51, "failed": 0, "skipped": 0}, focused
    archive = ROOT / "build/release1-candidate/fintrust-release1-linux-py312.zip"
    manifest = json.loads(archive.with_suffix(".manifest.json").read_text())
    assert manifest["source_commit"] == SOURCE
    assert manifest["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert manifest["content_checked"] and manifest["linux_execution_verified"]
    assert manifest["linux_verification"]["all_production_modules_checked"]
    with zipfile.ZipFile(archive) as package:
        assert json.loads(package.read("release-info.json"))["source_commit"] == SOURCE
        assert not any(x.startswith(("tools/", ".github/", "tests/", "docs/")) for x in package.namelist())
    roles = json.loads((OUT / "postgres16-roles.json").read_text())
    assert roles["status"] == "PASSED" and roles["migrations"] == list(range(1, 7))
    assert json.loads((OUT / "migrations.json").read_text())["status"] == "PASSED"
    suspicious = re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|postgres(?:ql)?://[^\s:]+:[^\s@]+@")
    for file in OUT.rglob("*"):
        if file.is_file() and file.suffix in {".json", ".xml", ".txt", ".log", ".md"}:
            assert not suspicious.search(file.read_bytes()), f"Sensitive pattern in evidence: {file.name}"
    write("readiness-summary.json", {**state, "status": "PASSED", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
          "run_url": f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
          "environment": {"os": platform.platform(), "architecture": platform.machine(), "python": platform.python_version()},
          "full_regression": json.loads((OUT / "regression.json").read_text()), "focused_v2": focused,
          "package": manifest, "packaging_after_full_and_focused_pass": True,
          "artifact_filename": archive.name, "ci_harness_excluded_from_application_archive": True,
          "secret_pattern_checks": "PASSED", "source_content_check": "PASSED",
          "deployment_permission_review": roles["fixture_grant_supplement"], "aws_deployed": False,
          "live_aws_e2e": "PENDING", "production_readiness_claimed": False})
    print("Exact candidate Linux gate passed; no AWS deployment occurred.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=("migrations", "regression", "final"))
    {"migrations": migrations_gate, "regression": regression, "final": final}[parser.parse_args().mode]()

"""Proposed read-only catalog supplement: isolated loopback PostgreSQL only."""
from pathlib import Path
from test_private_rds_preflight import isolated, base
from fintrust.migrations import apply_local, TABLES

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "sql/preflight/002_release1_catalog.sql").read_text(encoding="utf-8")

def catalog(conn, schema):
    source = SOURCE.replace("'public'", "'" + schema + "'")
    source = source.removesuffix("ROLLBACK;\n")
    try:
        with conn.cursor() as cur:
            cur.execute(source)
            result = cur.fetchone()[0]
            assert result["read_only"] == "on"
            return result
    finally:
        conn.rollback()

def test_catalog_handles_absent_schema_objects(isolated):
    conn, schema = isolated
    result = catalog(conn, schema)
    assert all(not item["present"] for item in result["objects"])
    assert result["conditional_count_queries"] is None
    assert result["indexes"] is None

def test_catalog_after_both_migrations_preserves_ledger(isolated):
    conn, schema = isolated
    base(conn)
    apply_local(conn, 1, schema=schema)
    apply_local(conn, 2, schema=schema)
    result = catalog(conn, schema)
    assert all(item["present"] for item in result["objects"])
    assert set(TABLES) <= {item["name"] for item in result["objects"]}
    assert all(item["valid"] and item["ready"] for item in result["indexes"])
    assert any(item["security_definer"] for item in result["trigger_functions"])
    assert len(result["views"]) == 2
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM "' + schema + '".transactions')
        assert cur.fetchone()[0] == 200
    conn.rollback()
    assert result == catalog(conn, schema)

def test_catalog_supplement_emits_hashes_not_definitions():
    assert "REPEATABLE READ READ ONLY" in SOURCE
    assert "ROLLBACK;" in SOURCE
    assert "GetSecretValue" not in SOURCE and "pg_authid" not in SOURCE
    assert "'definition_md5'" in SOURCE and "'default_md5'" in SOURCE
    assert "'definition'," not in SOURCE and "'default'," not in SOURCE

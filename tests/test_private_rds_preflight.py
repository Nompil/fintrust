"""Exercise proposed read-only preflights on isolated LOCAL test schemas only."""
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "sql/migrations/001_transaction_identity.sql").read_text()


@pytest.fixture
def isolated():
    dsn = os.getenv("FINTRUST_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Disposable local PostgreSQL required")
    target = parse_dsn(dsn)
    assert target.get("host") in {"localhost", "127.0.0.1", "::1"}
    assert target.get("dbname") in {"fintrust_test", "fintrust_local_test"}
    conn = psycopg2.connect(dsn)
    name = "migration_preflight_" + uuid.uuid4().hex
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(name)))
    conn.commit()
    try:
        yield conn, name
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
        conn.commit()
        conn.close()


def base(conn):
    source = (ROOT / "sql/schema.sql").read_text().split("-- Additive identity hardening.")[0]
    source = source.replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;", "")
    with conn.cursor() as cur:
        cur.execute(source)
        cur.execute((ROOT / "sql/seed.sql").read_text())
    conn.commit()


def run(conn, name, phase):
    source = (ROOT / f"sql/preflight/001_transaction_identity_{phase}.sql").read_text()
    # Fixed internally generated test schema, never a caller-provided SQL identifier.
    source = source.replace("public.", name + ".").replace("'public'", "'" + name + "'")
    source = source.removesuffix("ROLLBACK;\n")
    try:
        with conn.cursor() as cur:
            cur.execute(source)
            result = cur.fetchone()[0]
            assert result["read_only"] == "on"
            return result
    finally:
        conn.rollback()


def test_missing_base_is_visible_without_bootstrapping(isolated):
    conn, name = isolated
    result = run(conn, name, "catalog")
    assert result["relations"] is None
    assert result["migration_columns_present"] == 0


def test_legacy_rows_need_no_identity_backfill(isolated):
    conn, name = isolated
    base(conn)
    result = run(conn, name, "data")
    assert result["row_counts"]["transactions"] == 200
    assert all(value == 0 for key,value in result.items() if key.endswith("_rows") or key.endswith("_groups"))
    assert run(conn, name, "catalog")["migration_columns_present"] == 0


def test_partial_migration_and_duplicate_reference_are_reported(isolated):
    conn,name = isolated
    base(conn)
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE transactions ADD source_system varchar(100), ADD source_transaction_id varchar(200)")
        cur.execute("UPDATE transactions SET source_system='upstream',source_transaction_id='repeated'")
    conn.commit()
    assert run(conn,name,"catalog")["migration_columns_present"] == 2
    assert run(conn,name,"data")["duplicate_source_identity_groups"] > 0
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with conn.cursor() as cur:
            cur.execute(MIGRATION)
    conn.rollback()
    # Failed DDL rolled back, including the other five additions.
    assert run(conn,name,"catalog")["migration_columns_present"] == 2


def test_full_migration_rerun_preserves_rows_and_definitions(isolated):
    conn,name = isolated
    base(conn)
    with conn.cursor() as cur:
        cur.execute(MIGRATION)
    first = run(conn,name,"catalog")
    with conn.cursor() as cur:
        cur.execute(MIGRATION)
    second = run(conn,name,"catalog")
    assert second["migration_columns_present"] == 7
    assert second["migration_indexes_present"] == 2
    assert first["columns"] == second["columns"]
    assert first["indexes"] == second["indexes"]
    assert first["constraints"] == second["constraints"]
    assert run(conn,name,"data")["row_counts"]["transactions"] == 200


def test_existing_wrong_column_and_named_index_are_not_silently_repaired(isolated):
    conn,name = isolated
    base(conn)
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE transactions ADD country text NOT NULL DEFAULT 'XX'")
        cur.execute("CREATE INDEX idx_tx_source_identity ON transactions(amount)")
        cur.execute(MIGRATION)
    result=run(conn,name,"catalog")
    column=next(c for c in result["columns"] if c["table"]=="transactions" and c["name"]=="country")
    index=next(i for i in result["indexes"] if i["name"]=="idx_tx_source_identity")
    assert column["type"]=="text" and column["not_null"] and column["default"]
    assert not index["unique"] and index["predicate"] is None
    # Presence counts alone do NOT prove a complete valid migration.
    assert result["migration_columns_present"]==7 and result["migration_indexes_present"]==2


def test_invalid_partial_values_are_reported_as_counts_only(isolated):
    conn,name=isolated
    base(conn)
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE transactions ADD source_system varchar(100), ADD source_transaction_id varchar(200), ADD file_sha256 char(64), ADD transaction_fingerprint char(64), ADD source_row integer")
        cur.execute("UPDATE transactions SET source_transaction_id='',file_sha256='bad',transaction_fingerprint='bad',source_row=1")
    conn.commit()
    result=run(conn,name,"data")
    for field in ("invalid_source_identity_rows","invalid_file_hash_rows","invalid_fingerprint_rows","invalid_source_row_rows"):
        assert result[field]==200
    assert "upstream" not in str(result)


def test_read_only_transaction_rejects_writes(isolated):
    conn,name=isolated
    base(conn)
    source=(ROOT / "sql/preflight/001_transaction_identity_catalog.sql").read_text().removesuffix("ROLLBACK;\n")
    source=source.replace("public.",name+".").replace("'public'","'"+name+"'")
    with conn.cursor() as cur:
        cur.execute(source)
        with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
            cur.execute(sql.SQL("DELETE FROM {}.transactions").format(sql.Identifier(name)))
    conn.rollback()
    assert run(conn,name,"data")["row_counts"]["transactions"]==200

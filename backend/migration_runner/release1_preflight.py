"""Fixed read-only Release 1 metadata/count supplement; no caller SQL."""
from . import config, common
from psycopg2 import sql
OBJECTS = ("customers","accounts","transactions","risk_events","alerts","processed_transactions",
 "schema_migrations","ingestion_batches","ingestion_attempts","ingestion_records","risk_reviews",
 "risk_review_history","quarantine_cases","quarantine_corrections","correction_outbox",
 "projection_outbox","operations_requests")

def supplement(cur):
    source=(config.ROOT/"sql/preflight/002_release1_catalog.sql").read_text(encoding="utf-8")
    if not source.endswith("ROLLBACK;\n") or "WITH expected(name) AS" not in source:
        raise common.Refused("release1_catalog_wrapper_mismatch")
    cur.execute(source[source.index("WITH expected(name) AS"):-len("ROLLBACK;\n")])
    result=cur.fetchone()[0]
    if result["read_only"]!="on":raise common.Refused("preflight_not_read_only")
    counts={}
    for obj in result["objects"]:
        if obj["name"] in OBJECTS and obj["present"] and obj["kind"] in ("r","p") and obj["can_select"]:
            cur.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(obj["name"])))
            counts[obj["name"]]=cur.fetchone()[0]
    result["row_counts"]=counts
    result.pop("conditional_count_queries",None)
    result["migration_history"]=None
    columns={c["name"] for c in result.get("columns") or [] if c["table"]=="schema_migrations"}
    if counts.get("schema_migrations") is not None and {"version","source_sha256","catalog_sha256"} <= columns:
        cur.execute("SELECT version,source_sha256,catalog_sha256 FROM public.schema_migrations ORDER BY version LIMIT 10")
        result["migration_history"]=[dict(zip(("version","source_sha256","catalog_sha256"),r)) for r in cur.fetchall()]
    if counts.get("transactions") is not None:
        cur.execute("""WITH records AS (SELECT to_jsonb(t) AS j FROM public.transactions t)
        SELECT count(*) FILTER (WHERE j->>'source_transaction_id' IS NULL),
         count(*) FILTER (WHERE j->>'transaction_fingerprint' IS NULL),
         count(*) FILTER (WHERE j->>'batch_id' IS NULL),count(*) FILTER (WHERE j->>'file_sha256' IS NULL),
         count(*) FILTER (WHERE j->>'source_row' IS NULL) FROM records""")
        result["legacy_provenance_null_counts"]=dict(zip(("source_reference","fingerprint","batch","file_hash","row_number"),cur.fetchone()))
    return result

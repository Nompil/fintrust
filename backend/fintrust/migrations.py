"""Ordered, checksummed local migration harness. Not a live RDS runner.
Only dedicated loopback test databases are permitted. Live runner approval remains separate.
"""
from .paths import RESOURCE_ROOT
import hashlib
import json
from pathlib import Path
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
ROOT=RESOURCE_ROOT
IDENTITY_COLUMNS={"source_system":"character varying(100)","source_transaction_id":"character varying(200)",
 "transaction_fingerprint":"character(64)","batch_id":"uuid","file_sha256":"character(64)","source_row":"integer","country":"character(2)"}
TABLES=("ingestion_batches","ingestion_attempts","ingestion_records","risk_reviews","risk_review_history","quarantine_cases","quarantine_corrections","correction_outbox","projection_outbox","operations_requests")

class SchemaDrift(ValueError): pass

def _catalog(cur,schema,version):
    if version==1:
        cur.execute("""SELECT a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod) FROM pg_attribute a
            JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND c.relname='transactions' AND a.attname=ANY(%s) AND NOT a.attisdropped ORDER BY a.attname""",(schema,list(IDENTITY_COLUMNS)))
        columns=cur.fetchall()
        if dict(columns)!=IDENTITY_COLUMNS: raise SchemaDrift("Identity column contract mismatch")
        cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND indexname=ANY(%s) ORDER BY indexname",(schema,["idx_tx_source_identity","idx_tx_duplicate_charge"]))
        indexes=cur.fetchall()
        if len(indexes)!=2 or not any("UNIQUE INDEX" in d and "(source_system, account_id, source_transaction_id)" in d and "WHERE (source_transaction_id IS NOT NULL)" in d for _,d in indexes):
            raise SchemaDrift("Identity index contract mismatch")
        cur.execute("""SELECT pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname='transactions' AND k.conname='transactions_source_identity_check'""",(schema,))
        constraints=cur.fetchall()
        import re
        expected="CHECK (((source_transaction_id IS NULL) OR ((length(btrim((source_transaction_id)::text)) > 0) AND (length(btrim((source_system)::text)) > 0) AND (source_system IS NOT NULL))))"
        normalize=lambda text:re.sub(r"[\s()]","",text).lower()
        if len(constraints)!=1 or normalize(constraints[0][0])!=normalize(expected): raise SchemaDrift("Identity constraint mismatch")
        values=[columns,indexes,constraints]
    else:
        cur.execute("""SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
            pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE n.nspname=%s AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""",(schema,list(TABLES)))
        columns=cur.fetchall()
        if {x[0] for x in columns}!=set(TABLES): raise SchemaDrift("Operational table missing")
        cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=ANY(%s) ORDER BY indexname",(schema,list(TABLES)));indexes=cur.fetchall()
        cur.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY c.relname,k.conname""",(schema,list(TABLES)));constraints=cur.fetchall()
        cur.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",(schema,list(TABLES)));triggers=cur.fetchall()
        cur.execute("SELECT viewname,definition FROM pg_views WHERE schemaname=%s AND viewname=ANY(%s) ORDER BY viewname",(schema,["batch_reconciliation","quarantine_workflow"]));views=cur.fetchall()
        cur.execute("""SELECT DISTINCT p.proname,pg_get_functiondef(p.oid),p.prosecdef,p.proconfig
            FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY p.proname""",(schema,list(TABLES)));functions=cur.fetchall()
        values=[columns,indexes,constraints,triggers,views,functions]
    return hashlib.sha256(json.dumps(values,default=str,sort_keys=True).encode()).hexdigest()

def _catalog_for_version(cur,schema,version):
    if version in {4,5,6}:
        # Current whole workflow and lifecycle catalogs validate intentional evolution;
        # earlier historical snapshots remain immutable in schema_migrations.
        return hashlib.sha256((_catalog(cur,schema,2)+_catalog_for_version(cur,schema,3)).encode()).hexdigest()
    if version!=3: return _catalog(cur,schema,version)
    tables=("transaction_lifecycle_events",)
    cur.execute("""SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
        pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE n.nspname=%s AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""",(schema,list(tables)))
    columns=cur.fetchall()
    if {x[0] for x in columns}!=set(tables): raise SchemaDrift("Operational table missing")
    cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=ANY(%s) ORDER BY indexname",(schema,list(tables)));indexes=cur.fetchall()
    cur.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
        JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY c.relname,k.conname""",(schema,list(tables)));constraints=cur.fetchall()
    cur.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",(schema,list(tables)));triggers=cur.fetchall()
    cur.execute("SELECT viewname,definition FROM pg_views WHERE schemaname=%s AND viewname=ANY(%s) ORDER BY viewname",(schema,["batch_reconciliation","quarantine_workflow"]));views=cur.fetchall()
    cur.execute("""SELECT DISTINCT p.proname,pg_get_functiondef(p.oid),p.prosecdef,p.proconfig
        FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY p.proname""",(schema,list(tables)));functions=cur.fetchall()
    values=[columns,indexes,constraints,triggers,views,functions]
    return hashlib.sha256(json.dumps(values,default=str,sort_keys=True).encode()).hexdigest()


def apply_local(conn,version,*,schema="public"):
    target=parse_dsn(conn.dsn)
    if target.get("host") not in {"127.0.0.1","localhost","::1"} or target.get("dbname") not in {"fintrust_local_test","fintrust_test"}:
        raise ValueError("Dedicated loopback test database required")
    names={1:"001_transaction_identity.sql",2:"002_operational_workflows.sql",3:"003_transaction_lifecycle.sql",4:"004_review_assignment.sql",5:"005_investigation_notes.sql",6:"006_versioned_risk_review.sql"}
    if version not in names: raise ValueError("Unknown migration")
    source=(ROOT/"sql/migrations"/names[version]).read_text(encoding="utf-8").replace("\r\n","\n")
    digest=hashlib.sha256(source.encode()).hexdigest()
    # SQL identifiers are quoted; do not allow replacement text to inject SQL.
    if not schema.replace("_","").isalnum(): raise ValueError("Invalid isolated schema")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",("fintrust-release1:"+schema,))
            cur.execute(sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(sql.Identifier(schema)))
            cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {}.schema_migrations(version INTEGER PRIMARY KEY,source_sha256 CHAR(64) NOT NULL,catalog_sha256 CHAR(64) NOT NULL,applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())").format(sql.Identifier(schema)))
            cur.execute(sql.SQL("SELECT source_sha256,catalog_sha256 FROM {}.schema_migrations WHERE version=%s").format(sql.Identifier(schema)),(version,));saved=cur.fetchone()
            if saved:
                cur.execute(sql.SQL("SELECT source_sha256,catalog_sha256 FROM {}.schema_migrations WHERE version IN (4,5,6) ORDER BY version DESC LIMIT 1").format(sql.Identifier(schema)))
                evolved=cur.fetchone()
                if evolved and version in {2,4,5}:
                    cur.execute(sql.SQL("SELECT max(version) FROM {}.schema_migrations WHERE version IN (4,5,6)").format(sql.Identifier(schema))); latest=cur.fetchone()[0]
                    fourth=(ROOT/"sql/migrations"/names[latest]).read_text(encoding="utf-8").replace("\r\n","\n")
                    if saved[0]!=digest or evolved!=(hashlib.sha256(fourth.encode()).hexdigest(),_catalog_for_version(cur,schema,latest)):
                        raise SchemaDrift("Assignment evolution or prior source drift detected")
                elif saved!=(digest,_catalog_for_version(cur,schema,version)): raise SchemaDrift("Migration source or schema drift detected")
                return "ALREADY_APPLIED"
            if version in {4,5,6}:
                for prior_version in ((5,) if version==6 else (4,) if version==5 else (2,3)):
                    cur.execute(sql.SQL("SELECT source_sha256,catalog_sha256 FROM {}.schema_migrations WHERE version=%s").format(sql.Identifier(schema)),(prior_version,));prior=cur.fetchone()
                    previous=(ROOT/"sql/migrations"/names[prior_version]).read_text(encoding="utf-8").replace("\r\n","\n")
                    if not prior or prior!=(hashlib.sha256(previous.encode()).hexdigest(),_catalog_for_version(cur,schema,prior_version)):
                        raise SchemaDrift("Verified workflow/lifecycle migrations must precede 004")
            if version==3:
                apply_previous=(ROOT/"sql/migrations/002_operational_workflows.sql").read_text(encoding="utf-8").replace("\r\n","\n")
                cur.execute(sql.SQL("SELECT source_sha256,catalog_sha256 FROM {}.schema_migrations WHERE version=2").format(sql.Identifier(schema)));prior=cur.fetchone()
                if not prior or prior!=(hashlib.sha256(apply_previous.encode()).hexdigest(),_catalog_for_version(cur,schema,2)):
                    raise SchemaDrift("Verified migration 002 must precede 003")
            if version==2:
                cur.execute(sql.SQL("SELECT source_sha256,catalog_sha256 FROM {}.schema_migrations WHERE version=1").format(sql.Identifier(schema)));prior=cur.fetchone()
                first=(ROOT/"sql/migrations/001_transaction_identity.sql").read_text(encoding="utf-8").replace("\r\n","\n")
                if not prior or prior!=(hashlib.sha256(first.encode()).hexdigest(),_catalog_for_version(cur,schema,1)):
                    raise SchemaDrift("Verified migration 001 must precede 002")
            script=source.replace("public.",schema+".")
            lines=[line for line in script.splitlines() if line.strip() not in {"BEGIN;","COMMIT;"}]
            cur.execute("\n".join(lines))
            signature=_catalog_for_version(cur,schema,version)
            cur.execute(sql.SQL("INSERT INTO {}.schema_migrations(version,source_sha256,catalog_sha256) VALUES(%s,%s,%s)").format(sql.Identifier(schema)),(version,digest,signature))
    return "APPLIED"

"""Fixed migration 002 IAM executor; separate administrator bootstrap/cleanup.
Prepared only. Never called automatically by preflight or migration 001.
"""
import hashlib
from psycopg2 import sql
from . import common,config,iam
from .workflow_catalog import _catalog,TABLES
from .sql_binding import MIGRATION_SHA256
WORKFLOW_SHA256="5b2c04440eea244bfce150347dfa1953dd2a7e7ddb6af7e3a66e187d1c912f02"
OWNER="fintrust_workflow_owner"
VIEWS=("batch_reconciliation","quarantine_workflow")
FUNCTIONS=("guard_ingestion_record","guard_review_transition","record_review_history","reject_history_change",
 "guard_batch_identity","check_batch_record_count","guard_correction_submission","guard_quarantine_origin","guard_operations_receipt")
HELPER="fintrust_create_release1_workflows"

def migration_body():
    source=(config.ROOT/"sql/migrations/002_operational_workflows.sql").read_text(encoding="utf-8").replace("\r\n","\n")
    if hashlib.sha256(source.encode()).hexdigest()!=WORKFLOW_SHA256:raise common.Refused("workflow_source_hash_mismatch")
    if source.count("\nBEGIN;\n")!=1 or not source.endswith("COMMIT;\n"):raise common.Refused("workflow_wrapper_mismatch")
    return source.split("\nBEGIN;\n",1)[1][:-len("COMMIT;\n")]

def baseline(cur):
    from .contract import assess
    c=common.catalog(cur)
    # 001 stays conservative. Only 002-owned workflow triggers are separately
    # assessed by verify()/the saved catalog signature, never ignored globally.
    c["triggers"]=[t for t in c.get("triggers") or [] if t["table"] not in TABLES]
    a=assess(c);d=common.data(cur) if a["base_valid"] else None;a=assess(c,d)
    if a["state"]!="correct":raise common.Refused("verified_001_required")
    return d["row_counts"]

def objects(cur):
    cur.execute("SELECT c.relname,pg_get_userbyid(c.relowner),c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(%s)",(list(TABLES+VIEWS),))
    return cur.fetchall()

def verify(cur):
    rows=objects(cur)
    if {r[0] for r in rows}!=set(TABLES+VIEWS) or any(r[1]!=OWNER or r[2] or r[3] for r in rows):raise common.Refused("workflow_ownership_or_objects_mismatch")
    cur.execute("SELECT proname,pg_get_userbyid(proowner) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND proname=ANY(%s)",(list(FUNCTIONS),))
    if sorted(cur.fetchall())!=sorted((n,OWNER) for n in FUNCTIONS):raise common.Refused("workflow_function_ownership_mismatch")
    return _catalog(cur,"public",2)

def operate(conn,op):
    if op not in {"migrate002","verify002"}:raise common.Refused("operation_not_allowed")
    with conn.cursor() as cur:
        common.setup(cur,read_only=op=="verify002");common.session_check(cur,config.USER);iam.identity(cur)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-release1:public'))")
        before=baseline(cur)
        cur.execute("SELECT version,source_sha256,catalog_sha256 FROM public.schema_migrations ORDER BY version")
        saved={v:(s,c) for v,s,c in cur.fetchall()}
        if set(saved)-{1,2} or saved.get(1)!=(MIGRATION_SHA256,_catalog(cur,"public",1)):raise common.Refused("migration_history_001_mismatch")
        if 2 in saved:
            if saved[2]!=(WORKFLOW_SHA256,verify(cur)):raise common.Refused("workflow_catalog_drift")
            return {"migration":"002","status":"ALREADY_APPLIED","rows_preserved":True},False
        if op=="verify002":raise common.Refused("workflow_002_absent")
        if objects(cur):raise common.Refused("partial_workflow_state")
        # Only the exact zero-argument helper, never caller-supplied SQL.
        cur.execute("SELECT public.fintrust_create_release1_workflows()")
        signature=verify(cur)
        if baseline(cur)!=before:raise common.Refused("financial_row_counts_changed")
        cur.execute("INSERT INTO public.schema_migrations(version,source_sha256,catalog_sha256) VALUES(2,%s,%s)",(WORKFLOW_SHA256,signature))
        return {"migration":"002","status":"APPLIED","rows_preserved":True,"catalog_sha256":signature},True

def bootstrap(conn,op):
    with conn.cursor() as cur:
        common.setup(cur,read_only=False);common.session_check(cur,config.MASTER)
        cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
        cur.execute("SELECT has_table_privilege('fintrust_admin','public.transactions','SELECT')")
        temporary_master_select=not cur.fetchone()[0]
        cur.execute("SET LOCAL ROLE fintrust_transactions_owner")
        if temporary_master_select:cur.execute("GRANT SELECT ON public.transactions TO fintrust_admin")
        cur.execute("RESET ROLE");baseline(cur)
        cur.execute("SELECT to_regclass('public.schema_migrations'),to_regprocedure('public.fintrust_create_release1_workflows()')")
        if cur.fetchone()!=(None,None) or objects(cur):raise common.Refused("existing_workflow_state_requires_review")
        cur.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s",(OWNER,))
        if cur.fetchone()[0]:raise common.Refused("existing_workflow_owner_requires_review")
        cur.execute("CREATE ROLE fintrust_workflow_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
        cur.execute("GRANT USAGE,CREATE ON SCHEMA public TO fintrust_workflow_owner")
        cur.execute("SET LOCAL ROLE fintrust_transactions_owner")
        cur.execute("GRANT REFERENCES(tx_id) ON public.transactions TO fintrust_workflow_owner")
        if temporary_master_select:cur.execute("REVOKE SELECT ON public.transactions FROM fintrust_admin")
        cur.execute("RESET ROLE")
        cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
        cur.execute("GRANT REFERENCES(risk_event_id),SELECT(risk_event_id,risk_score) ON public.risk_events TO fintrust_workflow_owner")
        cur.execute("GRANT REFERENCES(tx_id) ON public.processed_transactions TO fintrust_workflow_owner")
        signature=_catalog(cur,"public",1)
        cur.execute("SET LOCAL ROLE fintrust_workflow_owner")
        cur.execute("CREATE TABLE public.schema_migrations(version INTEGER PRIMARY KEY CHECK(version IN(1,2)),source_sha256 CHAR(64) NOT NULL,catalog_sha256 CHAR(64) NOT NULL,applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        cur.execute("INSERT INTO public.schema_migrations(version,source_sha256,catalog_sha256) VALUES(1,%s,%s)",(MIGRATION_SHA256,signature))
        cur.execute("GRANT SELECT,INSERT ON public.schema_migrations TO fintrust_migrate_dev")
        # Fixed SQL literal compiled from the checksum-bound canonical migration.
        # No function arguments; no dynamic object/SQL input from invocation.
        code=sql.SQL("BEGIN EXECUTE {}; DROP FUNCTION public.fintrust_create_release1_workflows(); END").format(sql.Literal(migration_body()))
        cur.execute(sql.SQL("CREATE FUNCTION public.fintrust_create_release1_workflows() RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS {}").format(sql.Literal(code.as_string(conn))))
        cur.execute("REVOKE ALL ON FUNCTION public.fintrust_create_release1_workflows() FROM PUBLIC")
        cur.execute("GRANT EXECUTE ON FUNCTION public.fintrust_create_release1_workflows() TO fintrust_migrate_dev")
        cur.execute("SELECT count(*) FROM pg_proc p,LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid='public.fintrust_create_release1_workflows()'::regprocedure AND a.grantee NOT IN ('fintrust_workflow_owner'::regrole,'fintrust_migrate_dev'::regrole)")
        if cur.fetchone()[0]:raise common.Refused("unreviewed_helper_executor")
        cur.execute("RESET ROLE")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
    return {"workflow_helper_ready":True,"migration_executed":False},True

def cleanup(conn,op):
    with conn.cursor() as cur:
        common.setup(cur,read_only=False);common.session_check(cur,config.MASTER)
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE usename=%s",(config.USER,))
        if cur.fetchone()[0]:raise common.Refused("maintenance_sessions_active")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
        cur.execute("SET LOCAL ROLE fintrust_workflow_owner")
        cur.execute("DROP FUNCTION IF EXISTS public.fintrust_create_release1_workflows()")
        cur.execute("REVOKE SELECT,INSERT ON public.schema_migrations FROM fintrust_migrate_dev")
        cur.execute("RESET ROLE")
        cur.execute("REVOKE CREATE ON SCHEMA public FROM fintrust_workflow_owner")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
    return {"workflow_helper_removed":True,"workflow_owner_create_revoked":True,"persistent_workflow_owner_retained":True},True

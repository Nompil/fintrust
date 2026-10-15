"""Fixed 003–006 executor. No discovery, caller SQL, automatic DDL or app imports.

Administrator installs checksum-bound zero-argument helpers. The IAM login may
only invoke those helpers and insert verified history, within one transaction.
Existing 001/002 phase archives remain separate and unchanged.
"""
import hashlib
import re
from psycopg2 import sql
from . import common, config, iam, workflows
from .extension_catalog import _catalog_for_version
from .sql_binding import MIGRATION_SHA256

MIGRATIONS = {
    3: ("003_transaction_lifecycle.sql", "5813a1d24b44c00d8f53629519a306e82b32e02a00d2ed34868d04037dc7f181"),
    4: ("004_review_assignment.sql", "ecf0badd166fa89c6143cbf2c75b6501a8b56fd3ae7385f496542bd51e2a55f6"),
    5: ("005_investigation_notes.sql", "8f1697374e1853bd1ce48c6f0c502deb9c51f431aac9d5430312d3f79129fcfe"),
    6: ("006_versioned_risk_review.sql", "9049d766b5613cdd74f814c278c3d5867349d99f08ef98b50c158d2d95b5c2a4"),
}
SOURCES = {1: MIGRATION_SHA256, 2: workflows.WORKFLOW_SHA256,
           **{v: value[1] for v, value in MIGRATIONS.items()}}
OPERATIONS = {f"migrate{v:03d}": v for v in MIGRATIONS}
OWNER = workflows.OWNER


def helper(version):
    if version not in MIGRATIONS:
        raise common.Refused("extension_version_not_allowed")
    return f"fintrust_apply_migration_{version:03d}"


def migration_body(version):
    name, expected = MIGRATIONS[version]
    source = (config.ROOT / "sql/migrations" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    if hashlib.sha256(source.encode()).hexdigest() != expected:
        raise common.Refused("extension_source_hash_mismatch")
    if source.count("\nBEGIN;\n") != 1 or not source.endswith("COMMIT;\n"):
        raise common.Refused("extension_wrapper_mismatch")
    return source.split("\nBEGIN;\n", 1)[1][:-len("COMMIT;\n")]


def check_owner(cur):
    # Definer helpers execute only as the existing, non-login workflow owner.
    cur.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s", (OWNER,))
    if cur.fetchone() != (False, False, False, False, False, False, False):
        raise common.Refused("extension_owner_privileges_mismatch")
    cur.execute("SELECT pg_has_role(%s,%s,'MEMBER'),has_schema_privilege(%s,'public','CREATE')", (config.USER, OWNER, config.USER))
    if cur.fetchone() != (False, False):
        raise common.Refused("extension_login_privileges_mismatch")
    workflows.verify(cur)
    cur.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.schema_migrations'::regclass")
    if cur.fetchone() != (OWNER,):
        raise common.Refused("extension_ledger_owner_mismatch")


def history(cur):
    check_owner(cur)
    cur.execute("SELECT version,source_sha256,catalog_sha256 FROM public.schema_migrations ORDER BY version")
    saved = {v: (s, c) for v, s, c in cur.fetchall()}
    if not saved or sorted(saved) != list(range(1, max(saved) + 1)) or max(saved) not in range(2, 7):
        raise common.Refused("extension_history_order_mismatch")
    if any(saved[v][0] != SOURCES[v] for v in saved):
        raise common.Refused("extension_history_source_mismatch")
    latest = max(saved)
    # Historical snapshots remain immutable. 004–006 deliberately evolve the
    # workflow catalog; validate its newest saved signature, not an old guard.
    versions = {1, latest}
    if latest == 3:
        versions.add(2)
    if latest >= 4:
        versions.add(3)
    for version in versions:
        if saved[version][1] != _catalog_for_version(cur, "public", version):
            raise common.Refused("extension_catalog_drift")
    if latest >= 3:
        cur.execute("SELECT pg_get_userbyid(relowner),relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.transaction_lifecycle_events'::regclass")
        if cur.fetchone() != (OWNER, False, False):
            raise common.Refused("lifecycle_ownership_mismatch")
        cur.execute("SELECT pg_get_userbyid(proowner),prosecdef FROM pg_proc WHERE oid='public.validate_lifecycle_event()'::regprocedure")
        if cur.fetchone() != (OWNER, False):
            raise common.Refused("lifecycle_function_ownership_mismatch")
    return saved


def verify_after(cur, version):
    return _catalog_for_version(cur, "public", version)


def baseline(cur):
    from .contract import assess
    catalog = common.catalog(cur)
    # Only these extension-owned triggers are assessed by history() instead.
    # Do not relax the original 001/002 verifier for unrelated trigger changes.
    reviewed = {*workflows.TABLES, "transaction_lifecycle_events"}
    catalog["triggers"] = [t for t in catalog.get("triggers") or [] if t["table"] not in reviewed]
    assessment = assess(catalog)
    data = common.data(cur) if assessment["base_valid"] else None
    if assess(catalog, data)["state"] != "correct":
        raise common.Refused("verified_001_required")
    return data["row_counts"]


def helper_code(conn, version, body):
    return sql.SQL("""BEGIN
                PERFORM pg_advisory_xact_lock(hashtext('fintrust-release1:public'));
                IF (SELECT max(version) FROM public.schema_migrations) <> {} OR
                   NOT EXISTS(SELECT 1 FROM public.schema_migrations WHERE version={} AND source_sha256={})
                THEN RAISE EXCEPTION 'Verified predecessor required'; END IF;
                EXECUTE {};
                DROP FUNCTION public.{}();
                END""").format(sql.Literal(version-1), sql.Literal(version-1),
                                sql.Literal(SOURCES[version-1]), sql.Literal(body),
                                sql.Identifier(helper(version))).as_string(conn)


def check_helper(cur, version):
    name = "public." + helper(version) + "()"
    cur.execute("SELECT pg_get_userbyid(proowner),prosecdef,proconfig,prosrc FROM pg_proc WHERE oid=to_regprocedure(%s)", (name,))
    if cur.fetchone() != (OWNER, True, ['search_path=pg_catalog, pg_temp'],
                         helper_code(cur.connection, version, migration_body(version))):
        raise common.Refused("extension_helper_definition_mismatch")
    cur.execute("SELECT count(*) FROM pg_proc p,LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=to_regprocedure(%s) AND (a.grantee NOT IN ('fintrust_workflow_owner'::regrole,'fintrust_migrate_dev'::regrole) OR a.is_grantable)", (name,))
    if cur.fetchone()[0]:
        raise common.Refused("extension_helper_executor_mismatch")


def operate(conn, op):
    if op not in {*OPERATIONS, "verify_extensions"}:
        raise common.Refused("operation_not_allowed")
    # Bind every source, including on rerun; changed SQL never silently skips.
    for version in MIGRATIONS:
        migration_body(version)
    with conn.cursor() as cur:
        common.setup(cur, read_only=op == "verify_extensions")
        iam.identity(cur)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-release1:public'))")
        before = baseline(cur)
        saved = history(cur)
        if op == "verify_extensions":
            if max(saved) != 6:
                raise common.Refused("extensions_incomplete")
            return {"status": "VERIFIED", "versions": list(saved)}, False
        version = OPERATIONS[op]
        if version in saved:
            return {"migration": f"{version:03d}", "status": "ALREADY_APPLIED", "rows_preserved": True}, False
        if max(saved) != version - 1:
            raise common.Refused("extension_predecessor_required")
        if version == 3:
            cur.execute("SELECT to_regclass('public.transaction_lifecycle_events'),to_regprocedure('public.validate_lifecycle_event()')")
            if cur.fetchone() != (None, None):
                raise common.Refused("partial_lifecycle_state")
        if version == 4:
            cur.execute("SELECT to_regclass('public.risk_reviews_assignee_queue')")
            if cur.fetchone()[0] is not None:
                raise common.Refused("partial_assignment_state")
        check_helper(cur, version)
        cur.execute(sql.SQL("SELECT public.{}()").format(sql.Identifier(helper(version))))
        signature = verify_after(cur, version)
        if baseline(cur) != before:
            raise common.Refused("financial_row_counts_changed")
        cur.execute("INSERT INTO public.schema_migrations(version,source_sha256,catalog_sha256) VALUES(%s,%s,%s)", (version, SOURCES[version], signature))
        history(cur)
        return {"migration": f"{version:03d}", "status": "APPLIED", "rows_preserved": True,
                "catalog_sha256": signature}, True


def bootstrap(conn, op):
    if op != "bootstrap_extensions":
        raise common.Refused("operation_not_allowed")
    bodies = {v: migration_body(v) for v in MIGRATIONS}
    with conn.cursor() as cur:
        common.setup(cur, read_only=False)
        common.session_check(cur, config.MASTER)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-release1:public'))")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
        cur.execute("SET LOCAL ROLE fintrust_workflow_owner")
        # Administrator can inspect the catalog; financial counts stay in the
        # IAM executor, which already has the reviewed SELECT-only base grants.
        saved = history(cur)
        if max(saved) != 2:
            raise common.Refused("bootstrap_requires_exact_002")
        cur.execute("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.schema_migrations'::regclass AND contype='c'")
        checks = cur.fetchall()
        if len(checks) != 1 or re.sub(r"[\s()]", "", checks[0][1]) != "CHECKversion=ANYARRAY[1,2]":
            raise common.Refused("unreviewed_ledger_constraint")
        for version in MIGRATIONS:
            cur.execute("SELECT to_regprocedure(%s)", ("public." + helper(version) + "()",))
            if cur.fetchone()[0] is not None:
                raise common.Refused("existing_extension_helper")
        cur.execute("RESET ROLE")
        cur.execute("GRANT CREATE ON SCHEMA public TO fintrust_workflow_owner")
        cur.execute("SET LOCAL ROLE fintrust_workflow_owner")
        # Add the replacement first, then remove only the inspected old CHECK.
        # Both DDL changes and all helper installations commit or roll back together.
        cur.execute("ALTER TABLE public.schema_migrations ADD CONSTRAINT fintrust_migration_versions_001_006 CHECK(version IN(1,2,3,4,5,6))")
        cur.execute(sql.SQL("ALTER TABLE public.schema_migrations DROP CONSTRAINT {}").format(sql.Identifier(checks[0][0])))
        cur.execute("GRANT SELECT,INSERT ON public.schema_migrations TO fintrust_migrate_dev")
        for version, body in bodies.items():
            code = helper_code(conn, version, body)
            cur.execute(sql.SQL("CREATE FUNCTION public.{}() RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS {}").format(sql.Identifier(helper(version)), sql.Literal(code)))
            cur.execute(sql.SQL("REVOKE ALL ON FUNCTION public.{}() FROM PUBLIC").format(sql.Identifier(helper(version))))
            cur.execute(sql.SQL("GRANT EXECUTE ON FUNCTION public.{}() TO fintrust_migrate_dev").format(sql.Identifier(helper(version))))
        cur.execute("RESET ROLE")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
    return {"extension_helpers_ready": True, "migration_executed": False}, True


def cleanup(conn, op):
    if op != "cleanup_extensions":
        raise common.Refused("operation_not_allowed")
    with conn.cursor() as cur:
        common.setup(cur, read_only=False)
        common.session_check(cur, config.MASTER)
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE usename=%s", (config.USER,))
        if cur.fetchone()[0]:
            raise common.Refused("maintenance_sessions_active")
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-release1:public'))")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
        cur.execute("SET LOCAL ROLE fintrust_workflow_owner")
        for version in MIGRATIONS:
            cur.execute(sql.SQL("DROP FUNCTION IF EXISTS public.{}()").format(sql.Identifier(helper(version))))
        cur.execute("REVOKE SELECT,INSERT ON public.schema_migrations FROM fintrust_migrate_dev")
        cur.execute("RESET ROLE")
        cur.execute("REVOKE CREATE ON SCHEMA public FROM fintrust_workflow_owner")
        cur.execute("GRANT fintrust_workflow_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
    return {"extension_helpers_removed": True, "owner_create_revoked": True}, True

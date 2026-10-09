"""IAM-only archive has no master-secret retrieval implementation."""
from . import common, config
from .contract import assess, safe_report

def connection():
    token = common.client("rds").generate_db_auth_token(DBHostname=config.HOST, Port=config.PORT,
                                                     DBUsername=config.USER, Region=config.REGION)
    try:
        return common.connect(config.USER, token)
    finally:
        token = None


def identity(cur):
    common.session_check(cur, config.USER)
    cur.execute("SELECT pg_has_role(current_user, 'rds_iam', 'MEMBER'), rolcanlogin, rolsuper, "
                "rolcreatedb, rolcreaterole, rolbypassrls, rolinherit FROM pg_roles WHERE rolname=current_user")
    if cur.fetchone() != (True, True, False, False, False, False, False):
        raise common.Refused("iam_role_privileges_mismatch")


def operate(conn, op):
    with conn.cursor() as cur:
        common.setup(cur, read_only=op != "migrate")
        identity(cur)
        if op == "cleanup-check":
            cur.execute("SELECT count(*) FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)")
            owned = cur.fetchone()[0]
            return {"owned_relations":owned,"drop_requires_administrator":True}, False
        if op == "migrate":
            cur.execute("SET LOCAL ROLE fintrust_transactions_owner")
            cur.execute("LOCK TABLE public.transactions IN ACCESS EXCLUSIVE MODE")
        c,d,a = common.inspect(cur)
        if op == "preflight":
            return safe_report(c,d,a), False
        if a["state"] in ("missing-base","conflicting"):
            raise common.Refused("migration_preflight_failed")
        if op == "verify":
            if a["state"] != "correct":
                raise common.Refused("verification_failed")
            return safe_report(c,d,a), False
        before = d["row_counts"]["transactions"]
        # Only this pinned file is executed. Its wrappers are removed so all DDL,
        # postchecks and row-count checks commit together, or roll back together.
        if a["state"] != "correct":
            columns, _ = common.migration_parts()
            cur.execute(columns)
            # Only the login can invoke the fixed helper, not the table-owner role.
            cur.execute("RESET ROLE")
            cur.execute("SELECT public.fintrust_create_identity_indexes()")
            cur.execute("SET LOCAL ROLE fintrust_transactions_owner")
        # A fully verified rerun is a no-op; the helper was dropped transactionally
        # by the successful first call. Never silently skip a conflicting definition.
        after_c, after_d, after_a = common.inspect(cur)
        if after_a["state"] != "correct" or after_d["row_counts"]["transactions"] != before:
            raise common.Refused("post_migration_verification_failed")
        result = safe_report(after_c,after_d,after_a)
        result["rows_preserved"] = True
        result["migration"] = "001_transaction_identity.sql"
    return result, True

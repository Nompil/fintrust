"""Only included in administrator-phase archives; no secrets in caller events."""
import json
from . import common, config

def connection():
    response = common.client("secretsmanager").get_secret_value(SecretId=config.SECRET, VersionStage="AWSCURRENT")
    try:
        value = json.loads(response["SecretString"])
        if response.get("ARN") != config.SECRET or "AWSCURRENT" not in response.get("VersionStages", []) or value.get("username") != config.MASTER or not isinstance(value.get("password"),str) or not value["password"]:
            raise common.Refused("secret_metadata_mismatch")
        return common.connect(config.MASTER, value["password"])
    finally:
        # Best-effort reference release, not a secure-memory-zeroization claim.
        response.clear()
        if "value" in locals() and isinstance(value,dict):
            value.clear()


def preflight(conn, op):
    return common.preflight(conn, config.MASTER), False


def bootstrap(conn, op):
    with conn.cursor() as cur:
        common.setup(cur, read_only=False)
        common.session_check(cur, config.MASTER)
        cur.execute("LOCK TABLE public.transactions IN ACCESS EXCLUSIVE MODE")
        c,d,a = common.inspect(cur)
        if not a["base_valid"] or a["state"] == "conflicting":
            raise common.Refused("schema_not_approved")
        # Fixed SQL refuses existing roles/unknown ownership instead of adapting.
        cur.execute((config.ROOT / "sql/bootstrap/temporary_identity.sql").read_text())
        cur.execute("SELECT pg_has_role(%s, 'rds_iam', 'MEMBER'), pg_has_role(%s, %s, 'SET')", (config.USER,config.USER,config.OWNER))
        if cur.fetchone() != (True,True):
            raise common.Refused("bootstrap_verification_failed")
    return {"temporary_login_created":True,"master_used_for_migration":False}, True


def cleanup(conn, op):
    with conn.cursor() as cur:
        common.setup(cur, read_only=False)
        common.session_check(cur, config.MASTER)
        cur.execute((config.ROOT / "sql/bootstrap/remove_temporary_identity.sql").read_text())
        cur.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (config.USER,))
        if cur.fetchone()[0] != 0:
            raise common.Refused("cleanup_verification_failed")
    return {"temporary_login_removed":True,"persistent_owner_retained":True}, True

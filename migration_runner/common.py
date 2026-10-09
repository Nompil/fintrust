"""Fixed SQL and connection helpers. No AWS clients or connections at import."""
import json
import uuid
from datetime import datetime, timezone
import boto3
from botocore.config import Config
import psycopg2
from . import config
from .contract import assess, safe_report

class Refused(Exception):
    pass

class RunnerFailure(Exception):
    """Only static sanitized categories may reach the Lambda error channel."""


def request(event, allowed):
    if not isinstance(event, dict) or set(event) != {"operation", "request_id"}:
        raise Refused("invalid_request")
    if event.get("operation") not in allowed or not isinstance(event.get("request_id"), str):
        raise Refused("operation_not_allowed")
    try:
        if str(uuid.UUID(event["request_id"])) != event["request_id"]:
            raise ValueError()
    except (ValueError, AttributeError):
        raise Refused("invalid_request_id") from None
    return event["operation"]


def client(service):
    return boto3.client(service, region_name=config.REGION,
                        config=Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts":1},
                                      ignore_configured_endpoint_urls=True))


def connect(user, password):
    # Fixed hostname/database/CA; never accept DSNs or host overrides in events.
    return psycopg2.connect(host=config.HOST, port=config.PORT, dbname=config.DATABASE,
        user=user, password=password, sslmode="verify-full", sslrootcert=str(config.CA),
        connect_timeout=5, application_name="fintrust-temporary-migration",
        options="-c statement_timeout=15000 -c lock_timeout=2000 -c idle_in_transaction_session_timeout=30000")


def body(path, *, migration=False):
    source = (config.ROOT / path).read_text(encoding="utf-8")
    if migration:
        from .sql_binding import MIGRATION_SHA256
        from hashlib import sha256
        if sha256(source.replace("\r\n", "\n").encode()).hexdigest() != MIGRATION_SHA256:
            raise Refused("migration_hash_mismatch")
        if not source.startswith("BEGIN;\n") or not source.endswith("COMMIT;\n"):
            raise Refused("migration_wrapper_mismatch")
        return source[len("BEGIN;\n"):-len("COMMIT;\n")]
    # Strip fixed transaction wrappers only. Caller owns a single transaction.
    start = source.index("SELECT jsonb_build_object") if path.endswith("catalog.sql") else source.index("WITH records")
    if not source.endswith("ROLLBACK;\n"):
        raise Refused("preflight_wrapper_mismatch")
    return source[start:-len("ROLLBACK;\n")]


# Canonical migration remains unchanged. The pinned source is partitioned at its
# fixed index section; the helper executes the same two statements with a qualified
# table name. Any canonical change requires a new source hash and review.
INDEX_MARKER = "-- References are unique within an upstream system/account, never amount/time."


def migration_parts():
    source = body("sql/migrations/001_transaction_identity.sql", migration=True)
    if source.count(INDEX_MARKER) != 1:
        raise Refused("migration_phase_boundary_mismatch")
    columns, indexes = source.split(INDEX_MARKER)
    return columns, INDEX_MARKER + indexes


def catalog(cur):
    cur.execute(body("sql/preflight/001_transaction_identity_catalog.sql"))
    return cur.fetchone()[0]


def data(cur):
    cur.execute(body("sql/preflight/001_transaction_identity_data.sql"))
    return cur.fetchone()[0]


def session_check(cur, user):
    cur.execute("SELECT current_database(), session_user, current_setting('server_version_num')::int, "
                "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())")
    database, actual_user, version, ssl = cur.fetchone()
    if database != config.DATABASE or actual_user != user or not 160000 <= version < 170000 or ssl is not True:
        raise Refused("database_identity_version_or_tls_mismatch")


def setup(cur, *, read_only):
    cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ " + ("READ ONLY" if read_only else "READ WRITE"))
    cur.execute("SET LOCAL search_path = pg_catalog, public")
    cur.execute("SET LOCAL lock_timeout = '2s'")
    cur.execute("SET LOCAL statement_timeout = '15s'")


def inspect(cur):
    c = catalog(cur)
    a = assess(c)
    d = data(cur) if a["base_valid"] else None
    a = assess(c, d)
    return c, d, a


def preflight(conn, user):
    with conn.cursor() as cur:
        setup(cur, read_only=True)
        session_check(cur, user)
        c, d, a = inspect(cur)
        result = safe_report(c, d, a)
    conn.rollback()
    return result


def run(event, allowed, connector, operation):
    conn = None
    committing = False
    try:
        op = request(event, allowed)
        conn = connector()
        result, write = operation(conn, op)
        if write:
            committing = True
            conn.commit()
            committing = False
        else:
            conn.rollback()
        # No event, credentials, SQL, raw error or result logging.
        print(json.dumps({"operation":op,"success":True}))
        return {"success":True,"operation":op,"request_id":event["request_id"],
                "recorded_utc":datetime.now(timezone.utc).isoformat(),"result":result}
    except Exception as error:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        category = "commit_outcome_unknown" if committing else "operation_refused" if isinstance(error,Refused) else (
            "authentication_failure" if isinstance(error, psycopg2.Error) and (error.pgcode or "").startswith("28") else "operation_failed")
        print(json.dumps({"success":False,"category":category}))
        raise RunnerFailure(category) from None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

import json
import os
from typing import Any

import boto3
import psycopg2

from .config import load_settings, AWS_REGION

rds = boto3.client("rds", region_name=AWS_REGION)


def get_connection():
    cfg = load_settings()
    password = cfg["db_password"]
    ssl_options = {}
    if cfg.get("db_auth_mode", os.getenv("DB_AUTH_MODE", "password")) == "iam":
        ca_bundle = os.environ["DB_SSLROOTCERT"]
        password = rds.generate_db_auth_token(
            DBHostname=cfg["db_host"], Port=cfg["db_port"], DBUsername=cfg["db_user"])
        ssl_options = {"sslmode": "verify-full", "sslrootcert": ca_bundle}
    elif os.getenv("AWS_EXECUTION_ENV"):
        ssl_options = {"sslmode": "verify-full", "sslrootcert": os.environ["DB_SSLROOTCERT"]}
    return psycopg2.connect(
        host=cfg["db_host"],
        dbname=cfg["db_name"],
        user=cfg["db_user"],
        password=password,
        connect_timeout=10,
        options="-c statement_timeout=20000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=20000",
        **ssl_options,
        port=cfg["db_port"],
    )


def run_query(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    from .read_session import read_connection
    with read_connection(get_connection) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
        except Exception:
            conn.rollback()
            raise


def safe_json_dumps(data: Any) -> str:
    return json.dumps(data, default=str)

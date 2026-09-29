import json
import os
from typing import Any

import psycopg2

from .config import load_settings


def get_connection():
    cfg = load_settings()
    return psycopg2.connect(
        host=cfg["db_host"],
        dbname=cfg["db_name"],
        user=cfg["db_user"],
        password=cfg["db_password"],
        port=cfg["db_port"],
    )


def run_query(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def safe_json_dumps(data: Any) -> str:
    return json.dumps(data, default=str)

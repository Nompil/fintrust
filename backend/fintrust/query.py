import os
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from .db import run_query
from .dynamo import get_item


def get_transactions(
    account_id: str,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    account_id = str(UUID(account_id))
    clauses = ["account_id = %s"]
    params: list[Any] = [account_id]
    if from_dt:
        clauses.append("tx_date >= %s")
        params.append(from_dt)
    if to_dt:
        clauses.append("tx_date <= %s")
        params.append(to_dt)
    params.append(max(1, min(limit, 500)))
    params.append(offset)
    sql = f"""
        SELECT tx_id::text, account_id::text, amount::text, currency,
               merchant, tx_date, tx_type, cross_border
        FROM transactions
        WHERE {' AND '.join(clauses)}
        ORDER BY tx_date DESC, tx_id DESC
        LIMIT %s OFFSET %s
    """
    return run_query(sql, tuple(params))


def get_insights(account_id: str, score_date: date | None = None, *, transaction_id: str | None = None) -> dict[str, Any] | None:
    account_id = str(UUID(account_id))
    # Transaction projections use TX#UUID; old daily summaries stay addressable.
    if transaction_id and score_date:
        raise ValueError("transaction_id and date cannot be combined")
    key = {"account_id": account_id,
           "score_date": "TX#" + str(UUID(transaction_id)) if transaction_id else (score_date or date.today()).isoformat()}
    item = get_item(os.getenv("DYNAMODB_TABLE", "risk_scores"), key)
    if item:
        item.pop("ttl", None)
    return item


def parse_datetime(value: str) -> datetime:
    from .validators import parse_transaction_date
    return parse_transaction_date(value)


def get_accounts() -> list[dict[str, Any]]:
    return run_query("SELECT account_id::text, account_type, status FROM accounts ORDER BY account_id")


def get_overview(account_scope=None) -> dict:
    scope=" WHERE account_id=ANY(%s::uuid[])" if account_scope is not None else ""
    params=(list(account_scope),) if account_scope is not None else ()
    counts = run_query("SELECT count(*) AS transactions, count(DISTINCT account_id) AS active_accounts, count(*) FILTER (WHERE cross_border) AS cross_border FROM transactions"+scope,params)[0]
    totals = run_query("SELECT currency, count(*) AS transactions, sum(amount)::text AS gross_amount FROM transactions"+scope+" GROUP BY currency ORDER BY currency",params)
    trend = run_query("SELECT (tx_date AT TIME ZONE 'UTC')::date::text AS day, count(*) AS transactions FROM transactions"+scope+" GROUP BY 1 ORDER BY 1",params)
    return {"counts": counts, "totals_by_currency": totals, "daily_transactions": trend}


def get_transaction_page(account_id, from_dt=None, to_dt=None, limit=50, cursor=None):
    """Count and page share one PostgreSQL statement snapshot."""
    from .pagination import fingerprint, decode_cursor, encode_cursor
    scope = fingerprint(account_id, from_dt, to_dt, limit)
    clauses, params = ["account_id = %s"], [account_id]
    for value, operator in ((from_dt, ">="), (to_dt, "<=")):
        if value:
            clauses.append(f"tx_date {operator} %s")
            params.append(value)
    boundary, page, boundary_params = "TRUE", 1, []
    if cursor is not None:
        when, identifier, page = decode_cursor(cursor, scope)
        boundary = "(tx_date, tx_id) < (%s, %s::uuid)"
        boundary_params = [when, identifier]
    result = run_query(f"""
        WITH filtered AS NOT MATERIALIZED (
            SELECT tx_id, account_id, amount, currency, merchant, tx_date, tx_type, cross_border
            FROM transactions WHERE {' AND '.join(clauses)}
        ), selected AS (
            SELECT tx_id::text, account_id::text, amount::text, currency, merchant,
                   tx_date, tx_type, cross_border
            FROM filtered WHERE {boundary}
            ORDER BY tx_date DESC, tx_id DESC LIMIT %s
        )
        SELECT (SELECT count(*) FROM filtered) AS total,
               COALESCE((SELECT json_agg(selected ORDER BY tx_date DESC, tx_id DESC)
                         FROM selected), '[]'::json) AS rows
    """, tuple(params + boundary_params + [limit + 1]))[0]
    rows = result['rows']
    for row in rows:
        row['tx_date'] = parse_datetime(row['tx_date'])
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, {'count': len(rows), 'page': page, 'total': result['total'],
                  'limit': limit, 'next_cursor': encode_cursor(rows[-1], scope, page + 1) if more else None}

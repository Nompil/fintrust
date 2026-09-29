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
    sql = f"""
        SELECT tx_id::text, account_id::text, amount::text, currency,
               merchant, tx_date, tx_type, cross_border
        FROM transactions
        WHERE {' AND '.join(clauses)}
        ORDER BY tx_date DESC
        LIMIT %s
    """
    return run_query(sql, tuple(params))


def get_insights(account_id: str, score_date: date | None = None) -> dict[str, Any] | None:
    account_id = str(UUID(account_id))
    key = {
        "account_id": account_id,
        "score_date": (score_date or date.today()).isoformat(),
    }
    item = get_item(os.getenv("DYNAMODB_TABLE", "risk_scores"), key)
    if item:
        item.pop("ttl", None)
    return item


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed

from datetime import date, datetime, timezone

from fintrust import query

ACCOUNT_ID = "20000000-0000-4000-8000-000000000001"


def test_get_transactions_uses_schema_columns_and_bounded_parameters(monkeypatch):
    captured = {}

    def fake_run_query(statement, parameters):
        captured["statement"] = statement
        captured["parameters"] = parameters
        return []

    monkeypatch.setattr(query, "run_query", fake_run_query)
    from_dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
    to_dt = datetime(2026, 9, 30, tzinfo=timezone.utc)

    assert query.get_transactions(ACCOUNT_ID, from_dt, to_dt, 900) == []
    assert "tx_id::text" in captured["statement"]
    assert "risk_score" not in captured["statement"]
    assert captured["parameters"] == (ACCOUNT_ID, from_dt, to_dt, 500)


def test_get_insights_uses_account_date_key_and_removes_ttl(monkeypatch):
    captured = {}
    item = {
        "account_id": ACCOUNT_ID,
        "score_date": "2026-09-28",
        "risk_score": 75,
        "ttl": 1790553600,
    }

    def fake_get_item(table_name, key):
        captured["table_name"] = table_name
        captured["key"] = key
        return item.copy()

    monkeypatch.setenv("DYNAMODB_TABLE", "risk_scores")
    monkeypatch.setattr(query, "get_item", fake_get_item)

    result = query.get_insights(ACCOUNT_ID, date(2026, 9, 28))

    assert captured["table_name"] == "risk_scores"
    assert captured["key"] == {"account_id": ACCOUNT_ID, "score_date": "2026-09-28"}
    assert result == {"account_id": ACCOUNT_ID, "score_date": "2026-09-28", "risk_score": 75}

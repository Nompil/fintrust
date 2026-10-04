from datetime import datetime, timezone
from decimal import Decimal

from fintrust import api

ACCOUNT_ID = "20000000-0000-4000-8000-000000000001"


def test_transactions_requires_account_id():
    response = api.app.test_client().get("/v1/transactions")

    assert response.status_code == 400
    assert response.get_json()["error"] == "account_id is required"
    assert response.json["status"] == "error"
    assert response.json["request_id"]


def test_transactions_returns_filtered_data(monkeypatch):
    captured = {}

    def fake_get_transactions(account_id, from_dt, to_dt, limit, offset):
        captured.update({
            "account_id": account_id,
            "from_dt": from_dt,
            "to_dt": to_dt,
            "limit": limit,
            "offset": offset,
        })
        return [{
            "tx_id": "tx-1",
            "account_id": account_id,
            "amount": "250.00",
            "tx_date": datetime(2026, 9, 28, tzinfo=timezone.utc),
        }]

    monkeypatch.setattr(api, "get_transactions", fake_get_transactions)
    response = api.app.test_client().get(
        f"/v1/transactions?account_id={ACCOUNT_ID}&limit=1000&offset=0"
        "&from=2026-09-01T00:00:00%2B00:00&to=2026-09-30T00:00:00%2B00:00"
    )

    assert response.status_code == 200
    assert response.get_json()["meta"] == {"count": 1, "limit": 500, "offset": 0}
    assert response.get_json()["data"][0]["tx_date"] == "2026-09-28T00:00:00+00:00"
    assert captured["account_id"] == ACCOUNT_ID
    assert captured["from_dt"].tzinfo is not None


def test_insights_returns_404_when_score_is_missing(monkeypatch):
    monkeypatch.setattr(api, "get_insights", lambda account_id, score_date: None)

    response = api.app.test_client().get(f"/v1/insights?account_id={ACCOUNT_ID}")

    assert response.status_code == 404
    assert response.get_json()["error"] == "No score found for this account and date"
    assert response.json["data"] is None


def test_insights_serializes_decimal_values(monkeypatch):
    monkeypatch.setattr(api, "get_insights", lambda account_id, score_date: {
        "account_id": account_id,
        "score_date": score_date.isoformat(),
        "risk_score": Decimal("75.5"),
    })

    response = api.app.test_client().get(f"/v1/insights?account_id={ACCOUNT_ID}")

    assert response.status_code == 200
    assert response.get_json()["data"]["risk_score"] == "75.5"


def test_health_returns_degraded_when_database_is_unavailable(monkeypatch):
    class UnavailableConnection:
        rolled_back = False
        closed = False

        def cursor(self):
            raise RuntimeError("database unavailable")

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    connection = UnavailableConnection()
    monkeypatch.setattr(api, "get_connection", lambda: connection)
    response = api.app.test_client().get("/v1/health")

    assert response.status_code == 503
    assert response.json["status"] == "degraded"
    assert response.json["data"] == {"db": "error"}
    assert connection.rolled_back is True
    assert connection.closed is True

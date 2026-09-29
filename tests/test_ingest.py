from fintrust import ingest

VALID_ACCOUNT = "20000000-0000-4000-8000-000000000001"


def test_validate_row_rejects_bad_amount_and_accepts_valid_row():
    valid_row = {
        "account_id": VALID_ACCOUNT,
        "amount": "250.00",
        "tx_date": "2026-09-28T09:15:00Z",
        "tx_type": "debit",
        "currency": "ZAR",
    }
    invalid_row = {**valid_row, "amount": "-1"}

    assert ingest.validate_row(valid_row) is None
    assert ingest.validate_row(invalid_row) == "amount must be greater than zero"


def test_transform_row_maps_csv_to_schema_types():
    values = ingest.transform_row({
        "account_id": VALID_ACCOUNT,
        "amount": "15.25",
        "tx_date": "2026-09-28T09:15:00Z",
        "tx_type": "DEBIT",
        "country": "US",
    }, "raw/test.csv")

    assert values[1] == VALID_ACCOUNT
    assert str(values[2]) == "15.25"
    assert values[6] == "debit"
    assert values[7] is True
    assert values[8] == "raw/test.csv"
    assert values[0] == ingest.transform_row({
        "account_id": VALID_ACCOUNT,
        "amount": "15.25",
        "tx_date": "2026-09-28T09:15:00Z",
        "tx_type": "DEBIT",
        "country": "US",
    }, "raw/test.csv")[0]


def test_process_csv_loads_good_rows_and_quarantines_bad_rows(monkeypatch):
    captured = {}
    monkeypatch.setattr(ingest, "_load_rows", lambda rows: captured.setdefault("rows", rows) and [])
    monkeypatch.setattr(ingest.s3, "put_object", lambda **kwargs: captured.setdefault("quarantine", kwargs))
    csv_text = (
        "account_id,amount,tx_date,tx_type\n"
        f"{VALID_ACCOUNT},20.00,2026-09-28,debit\n"
        f"{VALID_ACCOUNT},-5.00,2026-09-28,debit\n"
    )

    counts = ingest.process_csv("fintrust-ingest-dev", "raw/demo.csv", csv_text)

    assert counts == {"rows_received": 2, "rows_valid": 1, "rows_quarantined": 1}
    assert len(captured["rows"]) == 1
    assert captured["quarantine"]["Key"] == "quarantine/demo.csv.jsonl"

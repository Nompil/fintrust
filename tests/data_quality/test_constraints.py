import os
from pathlib import Path

import psycopg2
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def prepared_database_url():
    database_url = os.getenv("FINTRUST_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set FINTRUST_TEST_DATABASE_URL to run PostgreSQL integration checks")

    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute((PROJECT_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
            cursor.execute((PROJECT_ROOT / "sql" / "seed.sql").read_text(encoding="utf-8"))
            cursor.execute((PROJECT_ROOT / "sql" / "views.sql").read_text(encoding="utf-8"))
            cursor.execute((PROJECT_ROOT / "sql" / "procedure.sql").read_text(encoding="utf-8"))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return database_url


@pytest.fixture
def database_connection(prepared_database_url):
    connection = psycopg2.connect(prepared_database_url)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def assert_database_rejects(connection, expected_error, statement, parameters):
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
    except expected_error:
        connection.rollback()
        return
    connection.rollback()
    pytest.fail(f"Expected database to reject statement with {expected_error.__name__}")


def test_negative_amount_rejected_by_check_constraint(database_connection):
    assert_database_rejects(
        database_connection,
        psycopg2.errors.CheckViolation,
        "INSERT INTO transactions (account_id, amount, tx_date, tx_type, raw_file) "
        "VALUES (%s, -1, NOW(), 'debit', 'constraint-test.csv')",
        ("20000000-0000-4000-8000-000000000001",),
    )


def test_invalid_currency_rejected_by_check_constraint(database_connection):
    assert_database_rejects(
        database_connection,
        psycopg2.errors.CheckViolation,
        "INSERT INTO transactions (account_id, amount, currency, tx_date, tx_type, raw_file) "
        "VALUES (%s, 10, 'XXX', NOW(), 'debit', 'constraint-test.csv')",
        ("20000000-0000-4000-8000-000000000001",),
    )


def test_invalid_transaction_type_rejected_by_check_constraint(database_connection):
    assert_database_rejects(
        database_connection,
        psycopg2.errors.CheckViolation,
        "INSERT INTO transactions (account_id, amount, tx_date, tx_type, raw_file) "
        "VALUES (%s, 10, NOW(), 'cash', 'constraint-test.csv')",
        ("20000000-0000-4000-8000-000000000001",),
    )


def test_invalid_kyc_status_rejected_by_check_constraint(database_connection):
    assert_database_rejects(
        database_connection,
        psycopg2.errors.CheckViolation,
        "UPDATE customers SET kyc_status = 'unknown' "
        "WHERE customer_id = '10000000-0000-4000-8000-000000000001'",
        (),
    )


def test_account_with_transactions_cannot_be_deleted(database_connection):
    assert_database_rejects(
        database_connection,
        psycopg2.errors.RestrictViolation,
        "DELETE FROM accounts WHERE account_id = %s",
        ("20000000-0000-4000-8000-000000000001",),
    )


def test_risk_report_counts_transactions_not_repeated_risk_events(database_connection):
    with database_connection.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE transactions AS SELECT * FROM public.transactions WITH NO DATA")
        cursor.execute("CREATE TEMP TABLE risk_events AS SELECT * FROM public.risk_events WITH NO DATA")
        cursor.execute("""
            INSERT INTO transactions (tx_id, account_id, tx_date)
            SELECT md5(i::text)::uuid, '20000000-0000-4000-8000-000000000001'::uuid,
                   '2026-09-01'::timestamptz + i * INTERVAL '1 day'
            FROM generate_series(1, 4) i;
            INSERT INTO risk_events (tx_id, risk_score)
            SELECT md5('1')::uuid, 75 FROM generate_series(1, 4);
        """)
        statement = (PROJECT_ROOT / "sql/risk_report.sql").read_text(encoding="utf-8")
        cursor.execute(statement)
        assert cursor.fetchall() == []
        cursor.execute("INSERT INTO risk_events (tx_id, risk_score) SELECT md5(i::text)::uuid, 75 FROM generate_series(2, 4) i")
        cursor.execute(statement)
        assert cursor.fetchall() == [("20000000-0000-4000-8000-000000000001",)]


def test_running_balance_matches_small_hand_calculation(database_connection):
    with database_connection.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE transactions AS SELECT * FROM public.transactions WITH NO DATA")
        cursor.execute("""
            INSERT INTO transactions (tx_id, account_id, tx_date, tx_type, amount)
            SELECT md5(i::text)::uuid, '20000000-0000-4000-8000-000000000001'::uuid,
                   '2026-09-01'::timestamptz + i * INTERVAL '1 day', kind, amount
            FROM (VALUES (1, 'credit', 100), (2, 'debit', 25), (3, 'fee', 10)) v(i, kind, amount)
        """)
        cursor.execute((PROJECT_ROOT / "sql/monthly_summary.sql").read_text(encoding="utf-8"))
        assert [row[-1] for row in cursor.fetchall()] == [100, 75, 65]


def test_running_balance_keeps_currencies_separate(database_connection):
    with database_connection.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE transactions AS SELECT * FROM public.transactions WITH NO DATA")
        cursor.execute("""
            INSERT INTO transactions (tx_id, account_id, tx_date, tx_type, amount, currency)
            SELECT md5(currency)::uuid, '20000000-0000-4000-8000-000000000001'::uuid,
                   '2026-09-01'::timestamptz, 'credit', amount, currency
            FROM (VALUES ('ZAR', 100), ('USD', 20)) v(currency, amount)
        """)
        cursor.execute((PROJECT_ROOT / "sql/monthly_summary.sql").read_text(encoding="utf-8"))
        assert {row[1]: row[-1] for row in cursor.fetchall()} == {"USD": 20, "ZAR": 100}


def test_dashboard_queries_use_real_postgresql(prepared_database_url, monkeypatch):
    from fintrust import api, db
    monkeypatch.setattr(db, "get_connection", lambda: psycopg2.connect(prepared_database_url))
    monkeypatch.setattr(api, "get_connection", lambda: psycopg2.connect(prepared_database_url))
    client = api.app.test_client()
    assert client.get("/v1/health").status_code == 200
    overview = client.get("/v1/overview")
    assert overview.status_code == 200
    data = overview.get_json()["data"]
    assert data["counts"]["transactions"] >= 200
    assert {row["currency"] for row in data["totals_by_currency"]} == {"ZAR", "USD"}
    assert len(client.get("/v1/accounts").get_json()["data"]) == 5


@pytest.mark.parametrize('column', ['account_id', 'amount', 'tx_date', 'raw_file'])
def test_transaction_required_fields(database_connection, column):
    values = dict(account_id='20000000-0000-4000-8000-000000000001', amount=10,
                  tx_date='2026-09-30', raw_file='raw/constraints.csv')
    values[column] = None
    assert_database_rejects(database_connection, psycopg2.errors.NotNullViolation,
        "INSERT INTO transactions(account_id, amount, tx_date, raw_file, tx_type) VALUES (%s,%s,%s,%s,'debit')",
        tuple(values.values()))


def test_account_requires_customer(database_connection):
    assert_database_rejects(database_connection, psycopg2.errors.NotNullViolation,
        "INSERT INTO accounts(customer_id, account_type) VALUES (NULL, 'savings')", ())


def test_zero_amount_rejected(database_connection):
    assert_database_rejects(database_connection, psycopg2.errors.CheckViolation,
        "INSERT INTO transactions(account_id,amount,tx_date,tx_type,raw_file) VALUES (%s,0,NOW(),'debit','raw/test.csv')",
        ('20000000-0000-4000-8000-000000000001',))


def test_orphan_transaction_rejected(database_connection):
    assert_database_rejects(database_connection, psycopg2.errors.ForeignKeyViolation,
        "INSERT INTO transactions(account_id,amount,tx_date,tx_type,raw_file) VALUES (%s,10,NOW(),'debit','raw/test.csv')",
        ('ffffffff-ffff-4fff-8fff-ffffffffffff',))


def test_cursor_traversal_real_database(prepared_database_url, monkeypatch):
    from fintrust import db, query
    monkeypatch.setattr(db, 'get_connection', lambda: psycopg2.connect(prepared_database_url))
    account = '20000000-0000-4000-8000-000000000001'
    seen, token, page = [], None, 0
    while True:
        rows, meta = query.get_transaction_page(account, limit=7, cursor=token)
        page += 1
        assert meta['page'] == page
        seen.extend(row['tx_id'] for row in rows)
        token = meta['next_cursor']
        if token is None:
            break
        assert page < 100
    assert len(seen) == len(set(seen)) == meta['total']
    empty, meta = query.get_transaction_page('ffffffff-ffff-4fff-8fff-ffffffffffff')
    assert empty == [] and meta['total'] == 0


def test_real_ingestion_retains_source_key(prepared_database_url, monkeypatch):
    from fintrust import ingest
    from uuid import uuid4
    source = 'raw/traceability-' + str(uuid4()) + '.csv'
    monkeypatch.setattr(ingest, 'get_connection', lambda: psycopg2.connect(prepared_database_url))
    contents = 'account_id,amount,tx_date,tx_type\n20000000-0000-4000-8000-000000000001,12.34,2026-09-30,debit\n'
    try:
        result = ingest.process_csv('test-bucket', source, contents)
        assert result['rows_valid'] == 1
        with psycopg2.connect(prepared_database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT amount, raw_file FROM transactions WHERE raw_file=%s', (source,))
                rows = cursor.fetchall()
                assert len(rows) == 1 and rows[0][1] == source
    finally:
        with psycopg2.connect(prepared_database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM transactions WHERE raw_file=%s', (source,))

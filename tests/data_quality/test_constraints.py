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
        psycopg2.errors.ForeignKeyViolation,
        "DELETE FROM accounts WHERE account_id = %s",
        ("20000000-0000-4000-8000-000000000001",),
    )

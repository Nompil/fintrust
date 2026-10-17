"""Live troubleshooting must never reveal a database credential or raw error."""
import uuid
from unittest.mock import Mock
import pytest
import psycopg2
from migration_runner import common,iam,iam_entry

EVENT={'operation':'preflight','request_id':str(uuid.UUID(int=1))}
SECRET='DO_NOT_DISCLOSE_DATABASE_TOKEN_OR_CUSTOMER_VALUE'

def test_connection_diagnostic_redacts_original_exception(monkeypatch,capsys):
    monkeypatch.setattr(iam,'connection',Mock(side_effect=psycopg2.OperationalError('PAM authentication failed '+SECRET)))
    with pytest.raises(common.RunnerFailure) as caught:iam_entry.lambda_handler(EVENT,None)
    assert str(caught.value)=='operation_failed:connection:iam_authentication:none'
    assert SECRET not in str(caught.value)+capsys.readouterr().out

def test_sql_error_rolls_back_without_commit_or_raw_details(monkeypatch,capsys):
    connection=Mock()
    monkeypatch.setattr(iam,'connection',lambda:connection)
    monkeypatch.setattr(iam,'operate',Mock(side_effect=psycopg2.errors.InsufficientPrivilege(SECRET)))
    with pytest.raises(common.RunnerFailure) as caught:iam_entry.lambda_handler(EVENT,None)
    assert ':operation:database:' in str(caught.value)
    connection.rollback.assert_called_once();connection.commit.assert_not_called();connection.close.assert_called_once()
    assert SECRET not in str(caught.value)+capsys.readouterr().out

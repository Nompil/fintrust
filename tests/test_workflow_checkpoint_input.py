"""New checkpoint input must not become a caller-controlled SQL/credential path."""
import uuid
from unittest.mock import Mock
import pytest
from migration_runner import preflight_entry,common,iam

@pytest.mark.parametrize('extra',['sql','password','host','database'])
def test_checkpoint_refuses_override_before_opening_database(monkeypatch,extra):
    connect=Mock(side_effect=AssertionError('Connector must not run'))
    monkeypatch.setattr(iam,'connection',connect)
    event={'operation':'preflight_workflows','request_id':str(uuid.uuid4()),extra:'untrusted'}
    with pytest.raises(common.RunnerFailure,match='operation_refused'):
        preflight_entry.lambda_handler(event,None)
    connect.assert_not_called()

import pathlib
import uuid
import pytest
from migration_runner import base, base_entry, common, config


def test_initializer_source_is_pinned_and_excludes_later_phases(monkeypatch, tmp_path):
    body = base.source()
    assert 'CREATE TABLE transactions' in body
    assert 'source_transaction_id' not in body and 'INSERT INTO' not in body
    assert 'CREATE TABLE IF NOT EXISTS' not in body
    (tmp_path/'sql').mkdir()
    (tmp_path/'sql/schema.sql').write_text('changed\n'+base.MARKER)
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    with pytest.raises(common.Refused, match='base_source_hash_mismatch'):
        base.source()


def test_initializer_rejects_arbitrary_payload_before_connecting(monkeypatch):
    monkeypatch.setattr(base_entry.admin, 'connection', lambda: pytest.fail('Unexpected connection'))
    for event in ({'operation':'initialize_base','request_id':str(uuid.uuid4()),'sql':'SELECT 1'},
                  {'operation':'migrate','request_id':str(uuid.uuid4())}):
        with pytest.raises(common.RunnerFailure, match='operation_refused'):
            base_entry.lambda_handler(event, None)

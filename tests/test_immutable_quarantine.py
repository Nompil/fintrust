import uuid
import pytest
from fintrust import release_workflow, workflow_api, operations
from fintrust.auth import Principal


def forbidden(*args, **kwargs):
    raise AssertionError('Financial persistence must not be reached')


def test_manual_resubmission_cannot_reach_database_or_evidence_write(monkeypatch):
    monkeypatch.setattr(workflow_api, 'connection', forbidden)
    principal = Principal('analyst01', 'Risk/Compliance Analyst', ())
    with pytest.raises(PermissionError, match='immutable'):
        workflow_api._correct_case(str(uuid.uuid4()), {'action':'RESUBMIT', 'candidate':{'amount':'100.00'}}, principal)


def test_legacy_envelope_cannot_bypass_http_restriction(monkeypatch):
    monkeypatch.setattr(release_workflow, 'register', forbidden)
    with pytest.raises(PermissionError, match='source-system replacement'):
        release_workflow.process_envelope({'source_system':'manual-correction'})


def test_legacy_outbox_is_preserved_without_processing(monkeypatch):
    monkeypatch.setattr(release_workflow, '_with_connection', forbidden)
    assert release_workflow.drain_corrections() == {'completed':0,'paused':True,'reason':'SOURCE_REPLACEMENT_REQUIRED'}


def test_operations_cannot_restart_manual_corrections(monkeypatch):
    monkeypatch.setattr(workflow_api, '_query', forbidden)
    with pytest.raises(PermissionError, match='paused'):
        operations.retry({'request_id':str(uuid.uuid4()),'action':'RETRY_CORRECTION','target':str(uuid.uuid4()),'notes':'legacy request'}, Principal('ops01','Maintainer',()))


def test_analyst_permission_contract_no_longer_grants_correction():
    with pytest.raises(PermissionError):
        Principal('analyst01','Risk/Compliance Analyst',()).require('correct')

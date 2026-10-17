import io
from types import SimpleNamespace
import pytest
from fintrust.auth import Principal
from fintrust import cloud_intake,workflow_api,score,upload_ownership,frontend_workflows,operations,release_workflow

ACCOUNT='20000000-0000-4000-8000-000000000001'
OTHER='20000000-0000-4000-8000-000000000002'
CSV=(f'account_id,amount,currency,country,tx_date,tx_type,source_system,source_transaction_id\n'
     f'{ACCOUNT},10,ZAR,ZA,2026-10-17T10:00:00Z,debit,demo,cloud-1\n').encode()

@pytest.fixture
def intake(monkeypatch):
    monkeypatch.setenv('FINTRUST_CLOUD_INTAKE','1');monkeypatch.setenv('AUTH_MODE','cognito')
    monkeypatch.setenv('AWS_EXECUTION_ENV','AWS_Lambda_python3.12');monkeypatch.setenv('INPUT_BUCKET','versioned-raw')
    monkeypatch.delenv('FINTRUST_MODE',raising=False)
    principal=Principal('analyst01','Risk/Compliance Analyst',(ACCOUNT,),auth_source='cognito')
    calls=[]
    monkeypatch.setattr(workflow_api,'_query',lambda *a,**k:[{'account_id':ACCOUNT}])
    monkeypatch.setattr(score,'s3',SimpleNamespace(put_object=lambda **kw:(calls.append(kw) or {'VersionId':'verified-version'})))
    monkeypatch.setattr(upload_ownership,'owner',lambda *a:None)
    monkeypatch.setattr(upload_ownership,'claim',lambda batch,p,source:{'actor':p.subject,'admitted_at':'2026-10-17T10:00:00Z','source':source})
    monkeypatch.setattr(frontend_workflows,'record_upload',lambda *a,**k:None)
    def forbid(*a,**k):raise AssertionError('HTTP intake must not execute the financial worker')
    monkeypatch.setattr(release_workflow,'process_envelope',forbid)
    return principal,calls

def test_cloud_upload_stores_versioned_source_and_returns_pending_without_sql_writes(intake):
    principal,calls=intake
    result=operations.upload_csv('demo.csv',CSV,principal)
    assert result['upload_status']=='QUEUED' and result['reconciliation']['accepted']==0
    assert result['reconciliation']['pending']==1
    assert len(calls)==1 and calls[0]['Bucket']=='versioned-raw' and calls[0]['Key'].startswith('raw/uploads/')
    assert calls[0]['Body']==CSV

def test_known_outside_scope_is_denied_before_storage(intake,monkeypatch):
    principal,calls=intake
    monkeypatch.setattr(workflow_api,'_query',lambda *a,**k:[{'account_id':OTHER}])
    with pytest.raises(PermissionError):cloud_intake.upload('demo.csv',CSV,principal)
    assert not calls

def test_other_uploader_cannot_adopt_same_file(intake,monkeypatch):
    principal,calls=intake
    monkeypatch.setattr(upload_ownership,'owner',lambda *a:{'actor':'another-analyst'})
    with pytest.raises(PermissionError):cloud_intake.upload('demo.csv',CSV,principal)
    assert not calls

def test_local_identity_cannot_claim_cloud_admission(intake):
    _,calls=intake
    with pytest.raises(PermissionError):cloud_intake.upload('demo.csv',CSV,Principal('analyst01','Risk/Compliance Analyst',(ACCOUNT,)))
    assert not calls

def test_cloud_flag_does_not_enable_intake_outside_lambda(intake,monkeypatch):
    principal,calls=intake;monkeypatch.delenv('AWS_EXECUTION_ENV')
    with pytest.raises(PermissionError):cloud_intake.upload('demo.csv',CSV,principal)
    assert not calls

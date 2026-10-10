"""Real isolated PostgreSQL + mocked S3 presentation contract tests."""
import io
import uuid
import pytest
from tests.test_release1_end_to_end import release_db,authenticated_client,feed,run,row
from tests.test_release1_candidate import maintainer_headers
from fintrust import frontend_workflows as ui

@pytest.fixture
def local_receipts(monkeypatch):
    monkeypatch.setenv("FINTRUST_MODE","local");monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD","1")

def test_rejected_history_is_safe_durable_and_not_a_batch(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client;q=release_db[3]
    result=client.post('/v1/upload',data={"file":(io.BytesIO(b'wrong,headers\n1,2'),'../../bad.csv')},headers=headers('Admin'))
    assert result.status_code==400 and result.json['rejection']['rows_processed']==0
    assert q('SELECT count(*) FROM ingestion_batches')==[(0,)]
    history=client.get('/v1/upload-history',headers=headers('Admin')).json['data']
    assert len(history)==1 and history[0]['filename']=='bad.csv' and history[0]['reason_code']=='INVALID_CSV_SCHEMA'
    assert 'wrong,headers' not in str(history) and 'Bearer' not in str(history)
    assert client.get('/v1/audit-events',headers=headers('Read-only/Auditor')).json['data'][0]['action']=='UPLOAD_REJECTED'

def test_batch_detail_duplicate_classification_and_empty_failures(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client
    items=feed([row(),row(),row(source_transaction_id='BAD',amount='0')]);run(items)
    batch=items[0]['batch']['batch_id'];base='/v1/batches/'+batch
    result=client.get(base,headers=headers('Admin'));assert result.status_code==200,result.json
    data=result.json['data'];assert data['batch']['accounted_for']==3 and data['batch']['counts_consistent']
    assert [r['disposition'] for r in data['rows']]==['ACCEPTED','DUPLICATE','QUARANTINED']
    duplicates=client.get(base+'?disposition=DUPLICATE',headers=headers('Admin')).json['data']['rows']
    assert duplicates[0]['classification']=='SAME_FILE_DUPLICATE' and duplicates[0]['first_processed_at']
    assert client.get(base+'?disposition=FAILED_TECHNICAL',headers=headers('Admin')).json['data']['rows']==[]
    assert client.get('/v1/batches/'+str(uuid.uuid4()),headers=headers('Admin')).status_code==404

@pytest.mark.parametrize('query',['min_amount=NaN','tx_id=bad','from=2026-10-09','risk_level=High&risk_level=Low','unknown=x'])
def test_transaction_filters_reject_invalid_input(release_db,authenticated_client,query):
    client,headers=authenticated_client
    assert client.get('/v1/workflows/transactions?'+query,headers=headers('Admin')).status_code==400

def test_filters_and_review_risk_are_real(release_db,authenticated_client):
    client,headers=authenticated_client;run(feed([row(source_transaction_id='HIGH',amount='200000.01',country='US')]))
    response=client.get('/v1/workflows/transactions?source_id=HIGH&risk_level=High&country=US&min_amount=200000',headers=headers('Admin'))
    assert response.status_code==200 and len(response.json['data'])==1
    reviews=client.get('/v1/workflows/reviews',headers=headers('Admin')).json['data']
    assert reviews[0]['risk']['triggered_rules']

def test_maintainer_cannot_read_financial_intake_or_review(release_db,authenticated_client,maintainer_headers,local_receipts):
    client,_=authenticated_client
    for route in ['/v1/upload-history','/v1/audit-events','/v1/batches/'+str(uuid.uuid4()),'/v1/overview']:
        assert client.get(route,headers=maintainer_headers).status_code==403

def test_batch_detail_never_completes_unreconciled_counts(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client;items=feed([row(),row()]);run(items[:1])
    batch=items[0]['batch']['batch_id']
    result=client.get('/v1/batches/'+batch,headers=headers('Admin')).json['data']['batch']
    assert not result['counts_consistent'] and result['display_status']=='AWAITING_RECONCILIATION'

def test_batch_scope_and_receipts_do_not_leak_other_accounts(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client;q=release_db[3]
    other=q("SELECT account_id::text FROM accounts WHERE account_id<>%s LIMIT 1",(row()['account_id'],))[0][0]
    items=feed([row(account_id=other)]);run(items)
    assert client.get('/v1/batches/'+items[0]['batch']['batch_id'],headers=headers('Read-only/Auditor')).status_code==404
    assert client.get('/v1/upload-history?action=unrecognized',headers=headers('Admin')).status_code==400

"""Whole-route security coverage and a real SQL smoke gate; AWS is mocked."""
import re
import uuid
from decimal import Decimal
import pytest
from fintrust import api
from tests.test_release1_end_to_end import release_db, authenticated_client, feed, run, row, ACCOUNT
from tests.test_frontend_workflows import local_receipts
from tests.test_release1_candidate import maintainer_headers

ROUTES = sorted((method, rule.rule) for rule in api.app.url_map.iter_rules()
    if rule.rule.startswith('/v1/') and rule.rule != '/v1/health'
    for method in rule.methods - {'HEAD', 'OPTIONS'})

def concrete(route):
    return re.sub(r'<(?:[^:>]+:)?([^>]+)>', lambda m: '1' if m[1] == 'event' else
        'transactions' if m[1] == 'kind' else str(uuid.UUID(int=1)), route)

@pytest.mark.parametrize('method,route', ROUTES)
def test_every_protected_route_rejects_missing_identity(authenticated_client, method, route):
    client, _ = authenticated_client
    response = client.open(concrete(route), method=method, json={} if method == 'POST' else None)
    assert response.status_code == 401
    assert response.is_json and response.json['status'] == 'error'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Request-ID']

MUTATIONS = [('/v1/upload', ['Admin','Read-only/Auditor']),
    ('/v1/reviews/1/transition', ['Admin','Read-only/Auditor']),
    ('/v1/quarantine/'+str(uuid.UUID(int=1))+'/corrections', ['Admin','Read-only/Auditor']),
    ('/v1/operations/retry', ['Admin','Risk/Compliance Analyst','Read-only/Auditor']),
    ('/v1/administration/users', ['Risk/Compliance Analyst','Read-only/Auditor'])]

@pytest.mark.parametrize('route,role', [(p,r) for p,roles in MUTATIONS for r in roles])
def test_all_mutations_enforce_role_before_malformed_input(authenticated_client,local_receipts,route,role):
    client, headers = authenticated_client
    response = client.post(route,headers=headers(role),data='{',content_type='application/json')
    assert response.status_code == 403, response.json

@pytest.mark.parametrize('method,route', [(m,p) for m,p in ROUTES if p not in
    {'/v1/session','/v1/operations','/v1/operations/retry','/v1/workflows/<kind>'}])
def test_maintainer_cannot_read_financial_or_governance_routes(authenticated_client,maintainer_headers,method,route):
    response=authenticated_client[0].open(concrete(route),method=method,headers=maintainer_headers,json={} if method=='POST' else None)
    assert response.status_code==403

def test_system_smoke_sql_reconciliation_reports_and_failure_safety(release_db,authenticated_client,local_receipts,monkeypatch):
    _,_,connect,q,_=release_db
    client,headers=authenticated_client
    monkeypatch.setattr(api,'get_connection',connect)
    assert client.get('/v1/health').status_code==200
    for role in ('Admin','Risk/Compliance Analyst','Read-only/Auditor'):
        assert client.get('/v1/session',headers=headers(role)).json['data']['role']==role
    outcomes=run(feed([row(amount='50000.01'),row(source_transaction_id='SMOKE-LOW',amount='12'),
                      row(source_transaction_id='SMOKE-BAD',amount='0'),row(amount='50000.01')]))
    assert [r['status'] for r in outcomes[:-1]]==['ACCEPTED','ACCEPTED','QUARANTINED','DUPLICATE']
    assert q('SELECT accepted,quarantined,duplicate,pending,counts_consistent FROM batch_reconciliation')==[(2,1,1,0,True)]
    for path in ('/v1/workflows/transactions','/v1/workflows/reviews','/v1/workflows/quarantine',
                 '/v1/workflows/batches','/v1/release1/overview','/v1/release1/insights','/v1/audit-events',
                 '/v1/upload-history','/v1/operations','/v1/administration','/v1/administration/users','/v1/metrics'):
        response=client.get(path,headers=headers('Admin'))
        assert response.status_code==200,(path,response.json)
    response=client.get('/v1/reports?account_id='+ACCOUNT,headers=headers('Read-only/Auditor'))
    assert response.status_code==200,response.json
    expected=q('SELECT currency,count(*),sum(amount) FROM transactions WHERE account_id=%s GROUP BY currency',(ACCOUNT,))
    assert {(r['currency'],r['transactions'],Decimal(r['gross_amount'])) for r in response.json['data']}==set(expected)
    missing=client.get('/v1/transactions/'+str(uuid.uuid4()),headers=headers('Admin'))
    assert missing.status_code==404
    from fintrust import workflow_api
    monkeypatch.setattr(workflow_api,'_query',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('sensitive diagnostic sentinel')))
    failed=client.get('/v1/reports',headers=headers('Admin'))
    assert failed.status_code==500 and 'sentinel' not in failed.get_data(as_text=True)

def test_two_named_analysts_exact_file_replay_is_audited_without_extra_ledger(release_db,authenticated_client,local_receipts,monkeypatch):
    import io,json,os,hashlib
    from pathlib import Path
    from tests.test_release1_end_to_end import file_bytes
    client,headers=authenticated_client;q=release_db[3];s3=release_db[4]
    monkeypatch.setenv('INPUT_BUCKET','assurance-input')
    s3.create_bucket(Bucket='assurance-input',CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
    s3.put_bucket_versioning(Bucket='assurance-input',VersioningConfiguration={'Status':'Enabled'})
    registry_path=Path(os.environ['FINTRUST_AUTH_FILE']);registry=json.loads(registry_path.read_text())
    first=next(p for p in registry['principals'] if p['role']=='Risk/Compliance Analyst');first['subject']='analyst01'
    second={**first,'subject':'analyst02','token_sha256':hashlib.sha256(('e'*64).encode()).hexdigest()}
    registry['principals'].append(second);registry_path.write_text(json.dumps(registry))
    payload=file_bytes([row(source_transaction_id='TWO-UPLOADERS')])
    for identity in (headers('Risk/Compliance Analyst'),{'Authorization':'Bearer '+'e'*64}):
        result=client.post('/v1/upload',headers=identity,data={'file':(io.BytesIO(payload),'same.csv')})
        assert result.status_code==200,result.json
    assert result.json['data']['upload_status']=='DUPLICATE_FILE'
    assert q('SELECT count(*) FROM transactions')==[(201,)]
    history=client.get('/v1/upload-history',headers=headers('Admin')).json['data']
    assert {r['actor'] for r in history}=={'analyst01','analyst02'}
    assert {r['action'] for r in history}=={'UPLOAD_ACCEPTED','UPLOAD_REPLAY'}

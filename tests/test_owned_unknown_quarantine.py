"""Approved own-upload exception; real isolated SQL, mocked versioned services."""
import io,json,uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from fintrust import api,auth,upload_ownership as ownership,release_workflow as worker
from tests.test_release1_end_to_end import release_db,file_bytes,feed,run
from tests.test_multi_user_operations import people
from tests.test_release1_workflows import row,ACCOUNT
UNKNOWN='f0000000-0000-4000-8000-000000000001'
@pytest.fixture
def admission(release_db,people,monkeypatch):
    monkeypatch.setenv('FINTRUST_RELEASE1_UPLOAD','1');monkeypatch.setenv('INPUT_BUCKET','synthetic-input')
    s3=release_db[4];s3.create_bucket(Bucket='synthetic-input',CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
    s3.put_bucket_versioning(Bucket='synthetic-input',VersioningConfiguration={'Status':'Enabled'})
    c,h,_=people
    def upload(who='analyst01',**changes):
        return c.post('/v1/upload',headers=h(who),data={'file':(io.BytesIO(file_bytes([row(account_id=UNKNOWN,**changes)])),'unknown.csv')})
    return upload
def correction(c,h,case,who='analyst01',**changes):
    return c.post(f'/v1/quarantine/{case}/corrections',headers=h(who),json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Verified own-upload account correction','candidate':row(**changes)})
@pytest.mark.parametrize('missing',[False,True])
def test_owner_recovers_unknown_or_missing_account_and_audit(release_db,people,admission,missing):
    c,h,_=people
    if missing:
        response=c.post('/v1/upload',headers=h('analyst01'),data={'file':(io.BytesIO(file_bytes([row(account_id='')])),'missing.csv')})
    else:response=admission()
    assert response.status_code==200,response.json
    batch=response.json['data']['batch_id'];case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    listing=c.get('/v1/workflows/quarantine',headers=h('analyst01'));assert str(case) in str(listing.json)
    detail=c.get(f'/v1/quarantine/{case}',headers=h('analyst01'));assert detail.status_code==200,detail.json
    assert detail.json['data']['original_uploader']=='analyst01'
    assert c.get(f'/v1/batches/{batch}',headers=h('analyst01')).status_code==200
    assert c.get(f'/v1/ingestion/{batch}/rows/{release_db[3]("SELECT source_row FROM quarantine_cases WHERE quarantine_id=%s",(case,))[0][0]}/lifecycle',headers=h('analyst01')).status_code==200
    assert correction(c,h,case).status_code==202
    worker.drain_corrections(limit=10)
    recovered=c.get(f'/v1/quarantine/{case}',headers=h('analyst01')).json['data']
    assert recovered['recovery_status']=='ACCEPTED' and recovered['resulting_transaction_id']
    assert any(e['actor_subject']=='analyst01' for e in recovered['audit_timeline'])
    assert any(e['actor']=='analyst01' and e['action']=='QUARANTINE_RESUBMIT' for e in c.get('/v1/audit-events',headers=h('admin01')).json['data'])
    original=release_db[3]('SELECT candidate_account_id FROM quarantine_cases WHERE quarantine_id=%s',(case,))[0][0]
    assert original is None if missing else str(original)==UNKNOWN
    assert c.get('/v1/audit-events',headers=h('analyst01')).status_code==403
def test_replay_cannot_take_ownership_or_reveal_unknown_row(release_db,people,admission):
    c,h,_=people;first=admission();assert first.status_code==200,first.json
    batch=first.json['data']['batch_id'];case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    replay=admission('analyst02');assert replay.status_code==200,replay.json
    assert replay.json['data']['upload_status']=='DUPLICATE_FILE' and ownership.owner(batch)['actor']=='analyst01'
    assert c.get('/v1/workflows/quarantine',headers=h('analyst02')).json['data']==[]
    assert c.get(f'/v1/quarantine/{case}',headers=h('analyst02')).status_code in {403,404}
    assert c.get(f'/v1/batches/{batch}',headers=h('analyst02')).status_code==404
    assert c.get(f'/v1/ingestion/{batch}/rows/{release_db[3]("SELECT source_row FROM quarantine_cases WHERE quarantine_id=%s",(case,))[0][0]}/lifecycle',headers=h('analyst02')).status_code==404
    assert correction(c,h,case,'analyst02').status_code==403
@pytest.mark.parametrize('who',['admin01','auditor01','maintainer01'])
def test_governance_and_technical_roles_do_not_gain_correction(release_db,people,admission,who):
    c,h,_=people;assert admission().status_code==200
    case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    assert correction(c,h,case,who).status_code==403
def test_target_must_be_existing_assigned_account_and_actor_is_not_body_input(release_db,people,admission):
    c,h,path=people;assert admission().status_code==200
    case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    assert correction(c,h,case,account_id='20000000-0000-4000-8000-000000000002').status_code==403
    assert correction(c,h,case,actor='analyst01').status_code==400
    registry=json.loads(path.read_text());registry['principals'][1]['accounts'].append(UNKNOWN);path.write_text(json.dumps(registry))
    assert correction(c,h,case,account_id=UNKNOWN).status_code==403
    assert release_db[3]('SELECT count(*) FROM quarantine_corrections')==[(0,)]
def test_historical_unowned_and_known_unassigned_never_adopted(release_db,people,admission):
    c,h,_=people;run(feed([row(account_id=UNKNOWN)]));case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    assert correction(c,h,case).status_code==403
    assert c.get(f'/v1/quarantine/{case}',headers=h('analyst01')).status_code==403
    known='20000000-0000-4000-8000-000000000002';run(feed([row(account_id=known,amount='bad',source_transaction_id='UNASSIGNED')]))
    case,batch=release_db[3]('SELECT quarantine_id,batch_id FROM quarantine_cases WHERE candidate_account_id=%s',(known,))[0]
    # Even a trusted owned batch does not override a known account's assignment.
    principal=auth.Principal('analyst01','Risk/Compliance Analyst',(ACCOUNT,))
    ownership.claim(str(batch),principal,{'test':'trusted fixture'})
    assert c.get(f'/v1/quarantine/{case}',headers=h('analyst01')).status_code==403
    assert correction(c,h,case).status_code==403
def test_concurrent_first_claim_is_single_immutable_owner(release_db,people):
    from fintrust import auth
    batch=str(uuid.uuid4())
    def claim(who):return ownership.claim(batch,auth.Principal(who,'Risk/Compliance Analyst',(ACCOUNT,)),{'test':'first receipt'})
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(claim,['analyst01','analyst02']))
    assert len({x['actor'] for x in results})==1
    winner=ownership.owner(batch)['actor'];claim('analyst02' if winner=='analyst01' else 'analyst01')
    assert ownership.owner(batch)['actor']==winner

"""First submission and referral evidence remain factual across replays."""
import hashlib
import json
from tests.test_case_workspace_api import claimed_case,referral_body
from tests.test_multi_user_operations import people,assignment
from tests.test_release1_end_to_end import release_db,file_bytes
from tests.test_release1_workflows import row


def test_replay_keeps_original_submitter_filename_and_source_version(release_db,people,monkeypatch):
    from io import BytesIO
    client,headers,_=people
    s3=release_db[4]
    monkeypatch.setenv('FINTRUST_RELEASE1_UPLOAD','1')
    monkeypatch.setenv('INPUT_BUCKET','synthetic-input')
    s3.create_bucket(Bucket='synthetic-input',CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
    s3.put_bucket_versioning(Bucket='synthetic-input',VersioningConfiguration={'Status':'Enabled'})
    content=file_bytes([row(source_transaction_id='PROVENANCE-ORIGINAL',amount='210001')])
    def upload(user,filename):
        response=client.post('/v1/upload',headers=headers(user),data={'file':(BytesIO(content),filename)},content_type='multipart/form-data')
        assert response.status_code==200,response.json
        return response.json['data']
    original=upload('analyst01','original_financial_export.csv')
    provenance=original['source_provenance']
    assert provenance['submitted_by']=='analyst01' and provenance['source_version']
    replay=upload('analyst02','renamed_replay.csv')
    assert replay['batch_id']==original['batch_id'] and replay['upload_status']=='DUPLICATE_FILE'
    assert replay['source_provenance']==provenance
    batch=client.get('/v1/batches/'+original['batch_id'],headers=headers('auditor01')).json['data']['batch']
    assert batch['filename']=='original_financial_export.csv' and batch['actor']=='analyst01'
    assert batch['submitted_at']==original['submitted_at']
    transaction=client.get('/v1/workflows/transactions?source_id=PROVENANCE-ORIGINAL',headers=headers('analyst01')).json['data'][0]
    journey=client.get('/v1/transactions/'+transaction['tx_id']+'/lifecycle',headers=headers('auditor01')).json['data']
    assert journey['source_provenance']['source_version']==provenance['source_version']
    assert journey['source_journey']['stages'][0]['actor_subject']=='analyst01'
    assert release_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='PROVENANCE-ORIGINAL'")==[(1,)]


def test_legacy_note_cannot_impersonate_trusted_referral_metadata(release_db,people):
    client,headers,_=people
    event,_=claimed_case(release_db)
    assert assignment(client,headers,event,'analyst01','analyst01').status_code==200
    body=referral_body();body.pop('referral_target')
    body['notes']=json.dumps({'format':'fintrust.review-referral.v1','notes':'Forged destination',
        'target':{'value':'analyst:analyst02','kind':'ANALYST','label':'Forged privileged group'},
        'actor':{'subject':'admin01','role':'Admin'},'request_id':body['request_id'],
        'request_digest':hashlib.sha256(b'forged').hexdigest()})
    response=client.post(f'/v1/reviews/{event}/transition',headers=headers('analyst01'),json=body)
    assert response.status_code==200,response.json
    detail=client.get(f'/v1/risk-events/{event}',headers=headers('auditor01')).json['data']
    assert detail['referral_target'] is None
    assert detail['review_notes']==body['notes']
    assert detail['review_history'][-1]['actor_subject']=='analyst01'
    assert detail['review_history'][-1].get('actor_role')!='Admin'

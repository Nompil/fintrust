"""Missing local evidence is visible and blocks writes; financial reads remain independent."""
import uuid
from botocore.exceptions import ClientError
from fintrust import score,dynamo,release_workflow as worker
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_multi_user_operations import people
from tests.test_release1_workflows import row

def test_missing_original_preserves_detail_and_blocks_new_correction(release_db,people):
    c,h,_=people;run(feed([row(amount='bad')]))
    case,key,version=release_db[3]('SELECT quarantine_id,safe_payload_key,safe_payload_version FROM quarantine_cases')[0]
    score.s3.delete_object(Bucket='release1-safe',Key=key,VersionId=version)
    response=c.get(f'/v1/quarantine/{case}',headers=h('analyst01'))
    assert response.status_code==200,response.json
    data=response.json['data'];assert data['evidence_status']=='MISSING' and not data['evidence_available'] and data['candidate']=={} and data['audit_timeline']
    before=release_db[3]('SELECT count(*) FROM quarantine_corrections')
    for action in ('RESUBMIT','REJECT'):
        response=c.post(f'/v1/quarantine/{case}/corrections',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'action':action,'notes':'Missing original must never be invented','candidate':row() if action=='RESUBMIT' else None})
        assert response.status_code==409,response.json
    assert release_db[3]('SELECT count(*) FROM quarantine_corrections')==before

def test_missing_correction_preserves_recorded_worker_outcome(release_db,people):
    c,h,_=people;run(feed([row(amount='bad')]))
    case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    response=c.post(f'/v1/quarantine/{case}/corrections',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Verified synthetic correction','candidate':row(amount='25')});assert response.status_code==202,response.json
    worker.drain_corrections(limit=10)
    key,version=release_db[3]('SELECT corrected_payload_key,corrected_payload_version FROM quarantine_corrections')[0];score.s3.delete_object(Bucket='release1-safe',Key=key,VersionId=version)
    data=c.get(f'/v1/quarantine/{case}',headers=h('analyst01')).json['data']
    assert data['recovery_status']=='ACCEPTED' and data['resulting_transaction_id'] and data['corrected_values'] is None and not data['timeline_complete']
    assert data['correction_history'][0]['submitted_by']=='analyst01'

def test_provider_outage_does_not_hide_accepted_ledger(release_db,people,monkeypatch):
    c,h,_=people;run(feed([row(amount='200000.01',country='US')]))
    tx=release_db[3]("SELECT tx_id FROM transactions WHERE source_transaction_id='REF-001'")[0][0]
    def unavailable(*args,**kwargs):raise ClientError({'Error':{'Code':'ServiceUnavailable'}},'GetItem')
    monkeypatch.setattr(dynamo,'get_item',unavailable)
    detail=c.get(f'/v1/transactions/{tx}',headers=h('analyst01'));assert detail.status_code==200,detail.json
    assert detail.json['data']['cloud_alert']['delivery_state']=='UNAVAILABLE'
    life=c.get(f'/v1/transactions/{tx}/lifecycle',headers=h('analyst01'));assert life.status_code==200,life.json
    assert life.json['data']['current_state']=='STORED' and life.json['data']['alert_state']=='UNAVAILABLE'
    assert not any(e['event_type']=='ALERTED' for e in life.json['data']['timeline'])
    event=release_db[3]('SELECT risk_event_id FROM risk_events WHERE tx_id=%s',(tx,))[0][0]
    investigation=c.get(f'/v1/risk-events/{event}',headers=h('analyst01'));assert investigation.status_code==200,investigation.json
    assert investigation.json['data']['alert']['delivery_state']=='UNAVAILABLE' and investigation.json['data']['allowed_actions']['claim']


def test_sql_quarantine_recovery_with_reopened_local_evidence(release_db,people,monkeypatch,tmp_path):
    from tools.local_runtime_store import LocalStore,DurableS3
    c,h,_=people;raw=release_db[4];path=tmp_path/'services.sqlite'
    monkeypatch.setattr(score,'s3',DurableS3(raw,LocalStore(path)))
    run(feed([row(amount='bad',source_transaction_id='AFTER-RESTART')]))
    case,key,version=release_db[3]('SELECT quarantine_id,safe_payload_key,safe_payload_version FROM quarantine_cases')[0]
    raw.delete_object(Bucket='release1-safe',Key=key,VersionId=version)
    monkeypatch.setattr(score,'s3',DurableS3(raw,LocalStore(path)))
    detail=c.get(f'/v1/quarantine/{case}',headers=h('analyst01'));assert detail.status_code==200,detail.json
    assert detail.json['data']['candidate']['amount']=='bad' and detail.json['data']['evidence_available']
    response=c.post(f'/v1/quarantine/{case}/corrections',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Recover using exact persisted original after restart','candidate':row(amount='25',source_transaction_id='AFTER-RESTART')});assert response.status_code==202,response.json
    worker.drain_corrections(limit=10)
    detail=c.get(f'/v1/quarantine/{case}',headers=h('analyst01')).json['data']
    assert detail['recovery_status']=='ACCEPTED' and detail['resulting_transaction_id'] and detail['timeline_complete']
    assert release_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='AFTER-RESTART'")==[(1,)]
    assert any(e['actor_subject']=='analyst01' and e['actor_type']=='HUMAN' for e in detail['audit_timeline'])

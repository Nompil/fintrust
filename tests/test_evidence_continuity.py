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
        assert response.status_code==(403 if action=='RESUBMIT' else 409),response.json
    assert release_db[3]('SELECT count(*) FROM quarantine_corrections')==before


def test_missing_historical_correction_preserves_recorded_worker_outcome(release_db,people):
    from tests.legacy_quarantine_fixture import historical_correction
    c,h,_=people;run(feed([row(amount='bad')]))
    case=release_db[3]('SELECT quarantine_id FROM quarantine_cases')[0][0]
    old=historical_correction(release_db,case,row(amount='25'))
    score.s3.delete_object(Bucket='release1-safe',Key=old['key'],VersionId=old['version'])
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



def test_source_review_after_reopened_local_evidence_never_edits_original(release_db,people,monkeypatch,tmp_path):
    from tools.local_runtime_store import LocalStore,DurableS3
    c,h,_=people;raw=release_db[4];path=tmp_path/'services.sqlite'
    monkeypatch.setattr(score,'s3',DurableS3(raw,LocalStore(path)))
    run(feed([row(amount='bad',source_transaction_id='AFTER-RESTART')]))
    case,key,version=release_db[3]('SELECT quarantine_id,safe_payload_key,safe_payload_version FROM quarantine_cases')[0]
    raw.delete_object(Bucket='release1-safe',Key=key,VersionId=version)
    monkeypatch.setattr(score,'s3',DurableS3(raw,LocalStore(path)))
    detail=c.get(f'/v1/quarantine/{case}',headers=h('analyst01'));assert detail.status_code==200,detail.json
    assert detail.json['data']['candidate']['amount']=='bad' and detail.json['data']['evidence_available']
    assert c.post(f'/v1/quarantine/{case}/corrections',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Manual edit is prohibited','candidate':row(amount='25')}).status_code==403
    note=c.post(f'/v1/quarantine/{case}/notes',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'notes':'Source replacement requested after evidence restart'})
    assert note.status_code==201,note.json
    run(feed([row(amount='25',source_transaction_id='AFTER-RESTART')],'raw/replacement-after-restart.csv'))
    detail=c.get(f'/v1/quarantine/{case}',headers=h('analyst01')).json['data']
    assert detail['candidate']['amount']=='bad' and detail['recovery_status']=='OPEN'
    assert detail['source_review_notes']['data'][0]['actor']=='analyst01'
    assert release_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='AFTER-RESTART'")==[(1,)]

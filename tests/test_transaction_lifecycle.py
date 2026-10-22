"""Real isolated SQL; AWS transport mocked. No live database or AWS actions."""
import uuid
import pytest
import psycopg2
from tests.test_release1_end_to_end import release_db,authenticated_client,feed,run,row,ACCOUNT
from tests.test_frontend_workflows import local_receipts
from fintrust import release_workflow as worker,lifecycle,migrations,dynamo

def events(q,item):
    return q('SELECT event_type,actor_subject,occurred_at FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s ORDER BY sequence',(item['batch']['batch_id'],item['source']['row']))

@pytest.mark.parametrize('amount,country,level,review', [('10','ZA','Low','NOT_REQUIRED'),('150000','ZA','Medium','OPEN'),('200000.01','US','High','OPEN')])
def test_accepted_levels_stored_and_timeline_is_authoritative(release_db,authenticated_client,amount,country,level,review):
    q=release_db[3];client,headers=authenticated_client
    item=feed([row(amount=amount,country=country,source_transaction_id='LIFECYCLE')])[0]
    result=worker.process_envelope(item);identifier=result['transaction_id']
    assert result['risk_level']==level
    assert q('SELECT count(*) FROM transactions WHERE tx_id=%s',(identifier,))==[(1,)]
    recorded=events(q,item);assert [e[0] for e in recorded]==['RECEIVED','QUEUED','VALIDATED','SCORED','STORED']
    assert all(e[1]=='scoring-worker' and e[2].tzinfo for e in recorded)
    before=recorded;worker.process_envelope(item);assert events(q,item)==before
    response=client.get('/v1/transactions/'+identifier+'/lifecycle',headers=headers('Risk/Compliance Analyst'))
    assert response.status_code==200,response.json
    value=response.json['data'];assert value['current_state']=='STORED' and value['risk_state']==level and value['review_state']==review
    assert value['occurrences'][0]['source_file']==item['source']['key']
    assert value['timeline_complete']
    assert not any(e['event_type']=='ALERTED' for e in value['timeline'])

def test_review_actor_and_no_required_alert_before_review(release_db,authenticated_client):
    q=release_db[3];client,headers=authenticated_client
    result=worker.process_envelope(feed([row(amount='200000.01',country='US')])[0]);event=result['risk_event_id']
    body={'request_id':str(uuid.uuid4()),'expected_version':1,'status':'UNDER_REVIEW','notes':'Investigating','resolution_code':None}
    assert client.post(f'/v1/reviews/{event}/transition',json=body,headers=headers('Risk/Compliance Analyst')).status_code==200
    body.update(request_id=str(uuid.uuid4()),expected_version=2,status='CLEARED',resolution_code='VALID_ACTIVITY')
    assert client.post(f'/v1/reviews/{event}/transition',json=body,headers=headers('Risk/Compliance Analyst')).status_code==200
    value=client.get('/v1/transactions/'+result['transaction_id']+'/lifecycle',headers=headers('Read-only/Auditor')).json['data']
    assert value['review_state']=='CLEARED' and value['current_state']=='STORED'
    actions=[e for e in value['timeline'] if e['actor_type']=='HUMAN']
    assert [e['event_type'] for e in actions]==['UNDER_REVIEW','CLEARED']
    assert {e['actor_subject'] for e in actions}=={'Risk/Compliance Analyst'}
    assert value['alert_state']=='PENDING'


def test_source_replacement_has_new_occurrence_without_overwriting_quarantine(release_db,authenticated_client):
    q=release_db[3];client,headers=authenticated_client
    item=feed([row(amount='bad')])[0];result=worker.process_envelope(item)
    assert [e[0] for e in events(q,item)]==['RECEIVED','QUEUED','QUARANTINED']
    response=client.post(f"/v1/quarantine/{result['quarantine_id']}/corrections",json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Manual edit','candidate':row()},headers=headers('Risk/Compliance Analyst'))
    assert response.status_code==403
    assert worker.drain_corrections()['paused']
    original=client.get(f"/v1/ingestion/{item['batch']['batch_id']}/rows/2/lifecycle",headers=headers('Risk/Compliance Analyst')).json['data']
    assert original['current_state']=='QUARANTINED' and original['correction_timeline']==[]
    replacement=feed([row()],'raw/source-replacement.csv');run(replacement)
    current=client.get(f"/v1/ingestion/{replacement[0]['batch']['batch_id']}/rows/2/lifecycle",headers=headers('Risk/Compliance Analyst')).json['data']
    assert current['current_state']=='STORED'
    assert [e['event_type'] for e in current['timeline']]==['RECEIVED','QUEUED','VALIDATED','SCORED','STORED']
    assert q('SELECT count(*) FROM transactions')==[(201,)]

def test_technical_failure_retry_recovery_preserves_committed_ledger(release_db,monkeypatch):
    q=release_db[3];item=feed([row()])[0];publish=dynamo.publish_score
    monkeypatch.setattr(dynamo,'publish_score',lambda *a:(_ for _ in ()).throw(RuntimeError('sensitive sentinel')))
    with pytest.raises(RuntimeError):worker.process_envelope(item)
    assert q('SELECT count(*) FROM transactions')==[(201,)]
    assert [e[0] for e in events(q,item)][-1]=='TECHNICAL_FAILURE'
    assert q('SELECT error_type FROM transaction_lifecycle_events WHERE event_type=%s',('TECHNICAL_FAILURE',))==[('RuntimeError',)]
    monkeypatch.setattr(dynamo,'publish_score',publish);worker.process_envelope(item)
    assert [e[0] for e in events(q,item)]==['RECEIVED','QUEUED','VALIDATED','SCORED','STORED','TECHNICAL_FAILURE','RETRY','RECOVERED']
    worker.process_envelope(item);assert q('SELECT count(*) FROM transactions')==[(201,)]
    assert len(events(q,item))==8

@pytest.mark.parametrize('event', ['STORED','SCORED','RECOVERED','RETRY','DLQ'])
def test_prohibited_transitions_are_rejected_by_database(release_db,event):
    conn,name,connect,q,_=release_db;item=feed([row()])[0];worker.register(item)
    with pytest.raises(psycopg2.Error):worker._with_connection(lambda cur:lifecycle.append(cur,item,event))
    assert [e[0] for e in events(q,item)]==['RECEIVED','QUEUED']

def test_audit_immutable_and_dlq_requires_failure_evidence(release_db,monkeypatch):
    q=release_db[3];item=feed([row()])[0]
    monkeypatch.setattr(dynamo,'publish_score',lambda *a:(_ for _ in ()).throw(RuntimeError('failed')))
    with pytest.raises(RuntimeError):worker.process_envelope(item)
    # Trusted transport reconciliation only; no public state-setting route exists.
    worker._with_connection(lambda cur:lifecycle.append(cur,item,'DLQ'))
    with pytest.raises(ValueError,match='controlled redrive'):worker.process_envelope(item)
    for statement in ('UPDATE transaction_lifecycle_events SET actor_subject=actor_subject','DELETE FROM transaction_lifecycle_events'):
        with pytest.raises(psycopg2.Error):q(statement)
    assert events(q,item)[-1][0]=='DLQ'

def test_lifecycle_scope_missing_identity_and_unknown_objects(release_db,authenticated_client):
    client,headers=authenticated_client;item=feed([row()])[0];result=worker.process_envelope(item)
    path='/v1/transactions/'+result['transaction_id']+'/lifecycle'
    assert client.get(path).status_code==401
    assert client.get('/v1/transactions/'+str(uuid.uuid4())+'/lifecycle',headers=headers('Read-only/Auditor')).status_code==404
    assert client.get(path,headers=headers('Read-only/Auditor')).status_code==200

def test_migration_003_rerun_drift_and_history_preservation(release_db):
    conn,name,connect,q,_=release_db;item=feed([row()])[0];worker.process_envelope(item);before=events(q,item)
    assert migrations.apply_local(conn,3,schema=name)=='ALREADY_APPLIED'
    assert events(q,item)==before
    q('ALTER TABLE transaction_lifecycle_events ADD COLUMN drift text')
    with pytest.raises(migrations.SchemaDrift):migrations.apply_local(conn,3,schema=name)

def test_cross_account_lifecycle_reads_are_hidden(release_db,authenticated_client,monkeypatch):
    import json,os
    from pathlib import Path
    client,headers=authenticated_client;item=feed([row()])[0];result=worker.process_envelope(item)
    path=Path(os.environ['FINTRUST_AUTH_FILE']);registry=json.loads(path.read_text())
    for principal in registry['principals']:principal['accounts']=[str(uuid.uuid4())]
    path.write_text(json.dumps(registry))
    assert client.get('/v1/transactions/'+result['transaction_id']+'/lifecycle',headers=headers('Read-only/Auditor')).status_code==404
    assert client.get(f"/v1/ingestion/{item['batch']['batch_id']}/rows/2/lifecycle",headers=headers('Read-only/Auditor')).status_code==404

def test_alerted_only_with_durable_sent_evidence(release_db,authenticated_client):
    client,headers=authenticated_client;result=worker.process_envelope(feed([row(amount='200000.01',country='US')])[0])
    table=dynamo.dynamodb.Table('risk_scores')
    table.put_item(Item={'account_id':ACCOUNT,'score_date':'ALERT#'+result['transaction_id'],'delivery_state':'UNKNOWN','updated_at':'2026-10-09T11:00:00Z'})
    path='/v1/transactions/'+result['transaction_id']+'/lifecycle'
    value=client.get(path,headers=headers('Read-only/Auditor')).json['data']
    assert value['alert_state']=='UNKNOWN' and not any(e['event_type']=='ALERTED' for e in value['timeline'])
    table.put_item(Item={'account_id':ACCOUNT,'score_date':'ALERT#'+result['transaction_id'],'delivery_state':'SENT','updated_at':'2026-10-09T11:01:00Z'})
    value=client.get(path,headers=headers('Read-only/Auditor')).json['data']
    assert value['alert_state']=='SENT' and any(e['event_type']=='ALERTED' and e['actor_subject']=='alert-worker' for e in value['timeline'])

def test_recovery_cannot_be_fabricated_without_failure(release_db):
    item=feed([row()])[0];worker.process_envelope(item)
    with pytest.raises(psycopg2.Error):worker._with_connection(lambda cur:lifecycle.append(cur,item,'RECOVERED'))

def test_worker_repair_finishes_observed_projection_failure(release_db,monkeypatch):
    q=release_db[3];item=feed([row()])[0];original=dynamo.publish_score
    monkeypatch.setattr(dynamo,'publish_score',lambda *a:(_ for _ in ()).throw(RuntimeError('temporary')))
    with pytest.raises(RuntimeError):worker.process_envelope(item)
    identifier=q('SELECT canonical_tx_id::text FROM ingestion_records WHERE batch_id=%s',(item['batch']['batch_id'],))[0][0]
    monkeypatch.setattr(dynamo,'publish_score',original);worker.rebuild_projection(identifier)
    assert [e[0] for e in events(q,item)][-3:]==['TECHNICAL_FAILURE','RETRY','RECOVERED']

def test_duplicate_occurrence_keeps_original_canonical_identity(release_db,authenticated_client):
    q=release_db[3];client,headers=authenticated_client;items=feed([row(),row()]);results=run(items)
    assert results[0]['transaction_id']==results[1]['transaction_id']
    assert results[1]['status']=='DUPLICATE'
    assert [e[0] for e in events(q,items[1])]==['RECEIVED','QUEUED','VALIDATED','DUPLICATE']
    value=client.get('/v1/transactions/'+results[0]['transaction_id']+'/lifecycle',headers=headers('Read-only/Auditor')).json['data']
    assert len(value['occurrences'])==2 and value['current_state']=='STORED'


def test_historical_correction_timeline_retains_original_human_lineage(release_db,authenticated_client):
    from tests.legacy_quarantine_fixture import historical_correction
    client,headers=authenticated_client;q=release_db[3]
    case=worker.process_envelope(feed([row(amount='bad')])[0])['quarantine_id']
    old=historical_correction(release_db,case,row(),actor='Risk/Compliance Analyst')
    identifier=q("SELECT canonical_tx_id::text FROM ingestion_records WHERE batch_id=%s AND disposition='ACCEPTED'",(old['batch_id'],))[0][0]
    value=client.get('/v1/transactions/'+identifier+'/lifecycle',headers=headers('Read-only/Auditor')).json['data']
    correction=[e for e in value['timeline'] if e['event_type']=='CORRECTED'][0]
    assert correction['actor_type']=='HUMAN' and correction['actor_subject']=='Risk/Compliance Analyst'

def test_multiple_failed_deliveries_need_only_one_recovery(release_db,monkeypatch):
    q=release_db[3];item=feed([row()])[0];original=dynamo.publish_score
    monkeypatch.setattr(dynamo,'publish_score',lambda *a:(_ for _ in ()).throw(RuntimeError('temporary')))
    for _ in range(2):
        with pytest.raises(RuntimeError):worker.process_envelope(item)
    monkeypatch.setattr(dynamo,'publish_score',original)
    worker.process_envelope(item);before=events(q,item)
    worker.process_envelope(item);assert events(q,item)==before
    assert [e[0] for e in before].count('TECHNICAL_FAILURE')==2
    assert [e[0] for e in before].count('RECOVERED')==1
    assert q('SELECT count(*) FROM transactions')==[(201,)]

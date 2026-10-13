"""Real isolated SQL, frozen evidence, ownership and independent alerts."""
import json,uuid
import pytest
from fintrust import migrations,alert_delivery
from tests.test_multi_user_operations import people,event,assignment
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row,ACCOUNT

def get(c,h,e,who='analyst01'):
    return c.get(f'/v1/risk-events/{e}',headers=h(who))

@pytest.mark.parametrize('values,rule',[({'amount':'50000.01'},'AMOUNT_RISK'),({'country':'US'},'CROSS_BORDER')])
def test_signals_have_frozen_measurement_and_timestamp(release_db,people,values,rule):
    run(feed([row(**values)]));e=release_db[3]('SELECT risk_event_id FROM risk_events ORDER BY risk_event_id DESC LIMIT 1')[0][0]
    c,h,_=people;r=get(c,h,e);assert r.status_code==200,r.json
    s=next(x for x in r.json['data']['signals'] if x['rule']==rule)
    assert s['triggered_value'] and s['threshold'] and s['context'] and s['created_at']

def test_velocity_closed_window_and_duplicate_charge_evidence(release_db,people):
    rows=[row(source_transaction_id=f'V{i}',tx_date=f'2026-10-09T09:59:0{i}Z',amount=str(10+i)) for i in range(6)]
    run(feed(rows));q=release_db[3];result=q("SELECT result FROM processed_transactions WHERE result->'triggered_rules' @> '[{\"rule\":\"HIGH_VELOCITY\"}]'::jsonb")[0][0]
    signal=next(s for s in result['triggered_rules'] if s['rule']=='HIGH_VELOCITY');assert signal['triggered_value']==6 and signal['threshold']==5
    run(feed([row(source_transaction_id='D1',amount='123',merchant='Same shop',tx_date='2026-10-09T09:59:00Z'),row(source_transaction_id='D2',amount='123',merchant='Same shop',tx_date='2026-10-09T09:59:30Z')],filename='duplicate.csv'))
    result=q("SELECT result FROM processed_transactions WHERE result->'triggered_rules' @> '[{\"rule\":\"POSSIBLE_DUPLICATE_CHARGE\"}]'::jsonb")[0][0]
    signal=next(s for s in result['triggered_rules'] if s['rule']=='POSSIBLE_DUPLICATE_CHARGE');assert signal['matching_transaction_ids'] and signal['threshold']==120

@pytest.mark.parametrize('status,resolution',[('CLEARED','VALID_ACTIVITY'),('CONFIRMED_RISK','CONFIRMED_SUSPICIOUS'),('ESCALATED','SPECIALIST_REVIEW')])
def test_investigation_claim_note_decide_audit(release_db,people,status,resolution):
    c,h,_=people;e=event(release_db)
    initial=get(c,h,e).json['data'];assert initial['risk_level']=='High' and initial['alert']['required'] and initial['review_status']=='OPEN' and initial['allowed_actions']['claim']
    assert assignment(c,h,e,'analyst01','analyst01').status_code==200
    body={'request_id':str(uuid.uuid4()),'expected_version':2,'notes':'Investigated merchant and source references'}
    assert c.post(f'/v1/reviews/{e}/notes',headers=h('analyst02'),json=body).status_code==403
    r=c.post(f'/v1/reviews/{e}/notes',headers=h('analyst01'),json=body);assert r.status_code==200,r.json
    assert c.post(f'/v1/reviews/{e}/notes',headers=h('analyst01'),json=body).json['data']['replayed']
    d=get(c,h,e).json['data'];assert d['version']==3 and d['review_status']=='UNDER_REVIEW'
    assert len(d['review_history'])==3 and d['review_history'][-1]['actor_subject']=='analyst01'
    decision={'request_id':str(uuid.uuid4()),'expected_version':3,'notes':'Evidence checked','status':status,'resolution_code':resolution}
    assert c.post(f'/v1/reviews/{e}/transition',headers=h('analyst02'),json=decision).status_code==403
    assert c.post(f'/v1/reviews/{e}/transition',headers=h('analyst01'),json={**decision,'notes':''}).status_code==400
    assert c.post(f'/v1/reviews/{e}/transition',headers=h('analyst01'),json=decision).status_code==200
    d=get(c,h,e).json['data'];assert d['review_status']==status and d['reviewed_by']=='analyst01' and d['reviewed_at'] and len(d['review_history'])==4
    assert d['timeline_complete'] and not d['allowed_actions']['decide']

def test_scoped_filters_sort_counts_and_no_context_leak(release_db,people):
    c,h,path=people;e=event(release_db)
    r=c.get('/v1/workflows/risk-events?scenario=AMOUNT_RISK&risk_level=High&sort=severity',headers=h('analyst01'));assert r.status_code==200,r.json
    assert r.json['meta']['total_count']==1 and r.json['meta']['high_count']==1
    assert c.get('/v1/workflows/reviews?scenario=CROSS_BORDER',headers=h('analyst01')).json['meta']['active_count']==1
    assert c.get('/v1/workflows/reviews?scenario=INJECT',headers=h('analyst01')).status_code==400
    assert c.get('/v1/workflows/risk-events?sort=DROP',headers=h('analyst01')).status_code==400
    users=json.loads(path.read_text());users['principals'][1]['accounts']=[str(uuid.uuid4())];path.write_text(json.dumps(users))
    assert get(c,h,e).status_code==404
    assert c.get('/v1/workflows/risk-events',headers=h('analyst01')).json['meta']['total_count']==0

@pytest.mark.parametrize('who',['admin01','auditor01','maintainer01'])
def test_no_nonanalyst_notes(release_db,people,who):
    c,h,_=people;e=event(release_db)
    assert c.post(f'/v1/reviews/{e}/notes',headers=h(who),json={}).status_code==403

def test_alert_failed_retry_unknown_do_not_change_ledger_or_review(release_db,people,monkeypatch):
    from botocore.exceptions import ClientError
    from fintrust import dynamo
    monkeypatch.setattr(alert_delivery,'dynamodb',dynamo.dynamodb)
    c,h,_=people;e=event(release_db);d=get(c,h,e).json['data'];tx=str(d['tx_id'])
    monkeypatch.setenv('SES_SENDER','sender@example.test');monkeypatch.setenv('SES_RECIPIENT','recipient@example.test')
    class Reject:
        def send_email(self,**kwargs):raise ClientError({'Error':{'Code':'MessageRejected'},'ResponseMetadata':{'HTTPStatusCode':400}},'SendEmail')
    monkeypatch.setattr(alert_delivery,'ses',Reject())
    with pytest.raises(ClientError):alert_delivery.deliver(ACCOUNT,tx)
    d=get(c,h,e).json['data'];assert d['alert']['delivery_state']=='FAILED' and d['review_status']=='OPEN'
    assert release_db[3]('SELECT count(*) FROM transactions WHERE tx_id=%s',(tx,))[0][0]==1
    class Observe:
        def send_email(self,**kwargs):
            assert get(c,h,e).json['data']['alert']['delivery_state']=='RETRYING'
            raise RuntimeError('Ambiguous provider response')
    monkeypatch.setattr(alert_delivery,'ses',Observe())
    with pytest.raises(RuntimeError):alert_delivery.deliver(ACCOUNT,tx)
    d=get(c,h,e).json['data'];assert d['alert']['delivery_state']=='UNKNOWN' and d['alert']['reconciliation_required'] and d['review_status']=='OPEN'
    with pytest.raises(RuntimeError):alert_delivery.deliver(ACCOUNT,tx)

def test_note_version_immutable_history_and_migration_drift(release_db,people):
    c,h,_=people;e=event(release_db);assignment(c,h,e,'analyst01','analyst01')
    body={'request_id':str(uuid.uuid4()),'expected_version':1,'notes':'Stale'}
    assert c.post(f'/v1/reviews/{e}/notes',headers=h('analyst01'),json=body).status_code==409
    conn,schema,_,q,_=release_db
    assert migrations.apply_local(conn,5,schema=schema)=='ALREADY_APPLIED'
    assert migrations.apply_local(conn,4,schema=schema)=='ALREADY_APPLIED'
    import psycopg2
    with pytest.raises(psycopg2.Error):q('UPDATE risk_review_history SET notes=%s',('overwrite',))


@pytest.mark.parametrize('amount,level,review',[('10','Low',None),('50000.01','Medium','OPEN')])
def test_accepted_levels_remain_ledger_and_explainable(release_db,people,amount,level,review):
    run(feed([row(amount=amount,country='US')]))
    e=release_db[3]('SELECT max(risk_event_id) FROM risk_events')[0][0];c,h,_=people
    d=get(c,h,e).json['data'];assert d['risk_level']==level and d['review_status']==review and not d['alert']['required']
    assert d['tx_id'] and not d['allowed_actions']['decide']

def test_successful_alert_remains_independent_of_review(release_db,people,monkeypatch):
    from fintrust import dynamo
    c,h,_=people;e=event(release_db);d=get(c,h,e).json['data']
    monkeypatch.setattr(alert_delivery,'dynamodb',dynamo.dynamodb)
    monkeypatch.setenv('SES_SENDER','sender@example.test');monkeypatch.setenv('SES_RECIPIENT','recipient@example.test')
    class Send:
        def send_email(self,**kwargs):return {'MessageId':'synthetic-confirmed-send'}
    monkeypatch.setattr(alert_delivery,'ses',Send())
    assert alert_delivery.deliver(ACCOUNT,str(d['tx_id']))['status']=='SENT'
    assert alert_delivery.deliver(ACCOUNT,str(d['tx_id']))['status']=='SENT'
    d=get(c,h,e).json['data'];assert d['alert']['delivery_state']=='SENT' and d['review_status']=='OPEN'
    assert any(x['event_type']=='ALERTED' for x in d['timeline'])

def test_baseline_same_currency_preceding_window_and_frozen_source(release_db,people):
    run(feed([row(source_transaction_id='BEFORE',tx_date='2026-10-09T09:00:00Z',amount='20'),row(source_transaction_id='OTHER-CURRENCY',tx_date='2026-10-09T09:30:00Z',amount='999',currency='USD'),row(source_transaction_id='CURRENT',amount='200000.01',country='US')]))
    e=release_db[3]('SELECT max(risk_event_id) FROM risk_events')[0][0];c,h,_=people
    d=get(c,h,e).json['data'];context=d['account_context']
    expected=release_db[3]('SELECT count(*),avg(amount) FROM transactions WHERE account_id=%s AND currency=%s AND tx_date>=%s AND tx_date<%s',(ACCOUNT,'ZAR',context['window_start'],context['window_end']))[0]
    assert context['transaction_count']==expected[0] and float(context['average_amount'])==float(expected[1]) and context['currency']=='ZAR'
    assert any(float(t['amount'])==999 and t['currency']=='USD' for t in d['related_transactions']) and d['source_system']=='synthetic-demo'

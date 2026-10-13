"""Actual ingestion, SQL, scoped API, frozen replay and audit for V2 scenarios."""
import json
import pytest
from psycopg2.extras import Json
from fintrust import score, rules, dynamo
from tests.test_release1_end_to_end import release_db, feed, run
from tests.test_multi_user_operations import people
from tests.test_release1_workflows import row, ACCOUNT

@pytest.mark.parametrize('scenario,amount,country,count,duplicate,points,level,review',[
    ('LOW','10','ZA',1,False,0,'Low',False),
    ('MEDIUM','150000','ZA',1,False,25,'Medium',True),
    ('HIGH_AMOUNT','250000','ZA',1,False,40,'High',True),
    ('HIGH_VELOCITY','10','ZA',6,False,25,'Medium',True),
    ('CROSS_BORDER','10','US',1,False,15,'Low',False),
    ('POSSIBLE_DUPLICATE_CHARGE','10','ZA',1,True,20,'Medium',True),
    ('HIGH_TO_ALERT_REVIEW','150000','US',1,False,40,'High',True),
])
def test_controlled_v2_path(release_db,people,scenario,amount,country,count,duplicate,points,level,review):
    rows=[]
    if duplicate:rows.append(row(source_transaction_id='PRIOR',amount=amount,merchant='Match',tx_date='2026-10-09T09:59:30Z'))
    for i in range(count):rows.append(row(source_transaction_id=f'{scenario}-{i}',amount=amount if i==count-1 else str(11+i),country=country,merchant='Match' if duplicate else f'Unique-{i}',tx_date=f'2026-10-09T09:59:{40+i:02d}Z'))
    run(feed(rows));q=release_db[3];c,h,_=people
    tx,event,result=q('SELECT p.tx_id::text,r.risk_event_id,p.result FROM processed_transactions p JOIN risk_events r USING(tx_id) ORDER BY r.risk_event_id DESC LIMIT 1')[0]
    assert (result['score'],result['risk_level'],result['rule_version'])==(points,level,rules.RULE_VERSION)
    assert result['evaluated_at'] and all(x['evaluated_at']==result['evaluated_at'] for x in result['components'])
    assert q('SELECT count(*) FROM transactions WHERE tx_id=%s',(tx,))==[(1,)]
    assert q('SELECT count(*) FROM risk_reviews WHERE risk_event_id=%s',(event,))==[(int(review),)]
    api=c.get(f'/v1/risk-events/{event}',headers=h('analyst01')).json['data']
    assert api['risk_score']==points and api['risk_level']==level
    assert api['alert']['required']==(level=='High')
    assert api['risk']['components']==result['components']
    lifecycle=c.get('/v1/transactions/'+tx+'/lifecycle',headers=h('analyst01')).json['data']
    assert lifecycle['current_state']=='STORED'
    scored=next(e for e in lifecycle['timeline'] if e['event_type']=='SCORED')
    assert scored['actor_type']=='SYSTEM' and scored['occurred_at']
    if scenario=='HIGH_VELOCITY':
        evidence=next(x for x in api['signals'] if x['rule']=='HIGH_VELOCITY')
        assert evidence['triggered_value']==6 and evidence['window_seconds']==300
        assert evidence['observed_window_start'] and evidence['observed_window_end']
    if duplicate:
        evidence=next(x for x in api['signals'] if x['rule']=='POSSIBLE_DUPLICATE_CHARGE')
        assert evidence['matching_transactions'][0]['seconds_apart']=='10.0'
        assert q('SELECT count(*) FROM processed_transactions')==[(2,)]

def test_legacy_frozen_result_replays_without_new_model_or_history_changes(release_db,people,monkeypatch):
    # Build a controlled V1 snapshot in this disposable schema, never the user's DB.
    items=feed([row(amount='200000.01',country='US')]);run(items)
    q=release_db[3];tx,result=q('SELECT tx_id::text,result FROM processed_transactions')[0]
    original={**result,'score':70,'risk_level':'High','rule_version':'fintrust-r1-rules-2026-10-09',
        'triggered_rules':[{'rule':'HIGH_AMOUNT','points':30,'reason':'Amount exceeds 50000'},
                           {'rule':'VERY_HIGH_AMOUNT','points':25,'reason':'Amount exceeds 200000'},
                           {'rule':'CROSS_BORDER','points':15,'reason':'Country differs from ZA'}]}
    original.pop('components');original.pop('evaluated_at')
    q('UPDATE processed_transactions SET result=%s WHERE tx_id=%s',(Json(original),tx))
    q('UPDATE risk_events SET risk_score=70 WHERE tx_id=%s',(tx,))
    dynamo.dynamodb.Table('risk_scores').delete_item(Key={'account_id':ACCOUNT,'score_date':'TX#'+tx})
    # Rebuild the controlled historical projection from its authoritative frozen snapshot.
    before=q('SELECT event_type,actor_subject,occurred_at FROM transaction_lifecycle_events ORDER BY event_id')
    def fail(*a,**k):raise AssertionError('Frozen replay must not evaluate new scoring')
    monkeypatch.setattr(score,'evaluate',fail);monkeypatch.setenv('RISK_HIGH','99')
    run(items)
    assert q('SELECT result FROM processed_transactions WHERE tx_id=%s',(tx,))[0][0]==original
    assert q('SELECT event_type,actor_subject,occurred_at FROM transaction_lifecycle_events ORDER BY event_id')==before
    c,h,_=people;d=c.get(f"/v1/risk-events/{result['risk_event_id']}",headers=h('analyst01')).json['data']
    assert d['risk_score']==70 and d['risk']['rule_version']=='fintrust-r1-rules-2026-10-09'
    insights=c.get('/v1/release1/insights?days=all',headers=h('analyst01')).json['data']
    assert next(x for x in insights['rules'] if x['label']=='AMOUNT_RISK')['count']==1
    assert insights['scoring_versions']==[{'label':'fintrust-r1-rules-2026-10-09','count':1}]


@pytest.mark.parametrize('version,points,level,allowed',[
 ('fintrust-r1-rules-2026-10-09',30,'Low',False),
 ('fintrust-r1-rules-2026-10-09',40,'Medium',True),
 ('fintrust-r1-rules-2026-10-09',20,'Medium',False),
 ('fintrust-r2-rules-2026-10-13',15,'Low',False),
 ('fintrust-r2-rules-2026-10-13',25,'Medium',True),
 ('unknown-version',25,'Medium',False)])
def test_review_guard_uses_recorded_version_and_level(release_db,version,points,level,allowed):
    import psycopg2
    run(feed([row()]));q=release_db[3]
    tx,event,result=q('SELECT p.tx_id::text,r.risk_event_id,p.result FROM processed_transactions p JOIN risk_events r USING(tx_id)')[0]
    q('UPDATE processed_transactions SET result=%s WHERE tx_id=%s',(Json({**result,'rule_version':version,'score':points,'risk_level':level}),tx))
    q('UPDATE risk_events SET risk_score=%s WHERE tx_id=%s',(points,tx))
    if allowed:q("INSERT INTO risk_reviews(risk_event_id,change_actor) VALUES(%s,'scoring-worker')",(event,))
    else:
        with pytest.raises(psycopg2.Error,match='Medium or High'):q("INSERT INTO risk_reviews(risk_event_id,change_actor) VALUES(%s,'scoring-worker')",(event,))
    assert q('SELECT count(*) FROM risk_reviews WHERE risk_event_id=%s',(event,))==[(int(allowed),)]

def test_migration_006_reruns_and_detects_function_drift(release_db):
    from fintrust import migrations
    conn,schema,_,q,_=release_db
    for version in range(1,7):assert migrations.apply_local(conn,version,schema=schema)=='ALREADY_APPLIED'
    q("CREATE OR REPLACE FUNCTION guard_review_transition() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
    with pytest.raises(migrations.SchemaDrift):migrations.apply_local(conn,6,schema=schema)

def test_presentation_example_uses_frozen_actual_measurements(release_db,people):
    import os
    from pathlib import Path
    rows=[row(source_transaction_id=f'DEMO-{i}',merchant=f'Merchant-{i}',amount=str(10+i),tx_date=f'2026-10-09T09:{55+i:02d}:00Z') for i in range(5)]
    rows.extend([row(source_transaction_id='DEMO-5',merchant='Merchant-5',amount='20',tx_date='2026-10-09T09:59:30Z'),row(source_transaction_id='DEMO-6',merchant='Merchant-6',amount='21',tx_date='2026-10-09T09:59:40Z'),row(source_transaction_id='DEMO-7',merchant='Merchant-7',amount='150000',country='US',tx_date='2026-10-09T10:00:00Z')])
    run(feed(rows));q=release_db[3]
    result=q("SELECT result FROM processed_transactions WHERE result->>'score'='65'")[0][0]
    assert result['risk_level']=='High'
    assert [c['points'] for c in result['components']]==[25,15,25,0]
    assert result['components'][2]['triggered_value']==8
    assert result['components'][2]['observed_window_start']=='2026-10-09T09:55:00+00:00'
    assert result['components'][2]['observed_window_end']=='2026-10-09T10:00:00+00:00'
    if os.getenv('FINTRUST_RISK_V2_EVIDENCE'):
        out=Path(os.environ['FINTRUST_RISK_V2_EVIDENCE'])/'presentation-example.json'
        out.write_text(json.dumps({'label':'Controlled isolated PostgreSQL example; AWS mocked','flow':['Transaction','Measured values','Risk components','65%','HIGH','Analyst investigation'],'result':result},indent=2)+'\n',encoding='utf-8')

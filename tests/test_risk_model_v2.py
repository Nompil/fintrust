"""Independent numerical and evidence oracles for the authorised V2 model."""
from dataclasses import replace
from decimal import Decimal
import pytest
from fintrust.rules import ScoringConfig, RULE_VERSION, classify_risk, evaluate

STAMP='2026-10-13T10:00:00+00:00'
def record(amount='10',**changes):
    return dict(amount=amount,currency='ZAR',country='ZA',account_id='20000000-0000-4000-8000-000000000001',tx_date=STAMP,**changes)

@pytest.mark.parametrize('amount,points,level',[
    ('0',0,'Low'),('50000',0,'Low'),('50000.01',15,'Low'),('100000',15,'Low'),
    ('100000.01',25,'Medium'),('200000',25,'Medium'),('200000.01',40,'High')])
def test_amount_bands_are_exclusive(amount,points,level):
    r=evaluate(record(amount),evaluated_at=STAMP)
    assert (r['score'],r['risk_level'],r['rule_version'])==(points,level,RULE_VERSION)
    assert len(r['components'])==4
    assert [c['points'] for c in r['components']]==[points,0,0,0]
    assert len([c for c in r['components'] if c['rule']=='AMOUNT_RISK'])==1
    assert not {'HIGH_AMOUNT','VERY_HIGH_AMOUNT'} & {c['rule'] for c in r['triggered_rules']}
    amount_component=r['components'][0]
    assert amount_component['triggered_value']==amount
    assert amount_component['evaluated_at']==STAMP
    assert amount_component['threshold']==amount_component['amount_band']

@pytest.mark.parametrize('score,level',[(0,'Low'),(19,'Low'),(20,'Medium'),(39,'Medium'),(40,'High'),(100,'High')])
def test_investigation_priority_boundaries(score,level):assert classify_risk(score)==level

@pytest.mark.parametrize('amount,country,count,matches,score,level',[
    ('10','US',1,(),15,'Low'),('10','ZA',6,(),25,'Medium'),('10','ZA',1,('prior',),20,'Medium'),
    ('150000','US',1,(),40,'High'),('150000','ZA',6,(),50,'High'),
    ('10','ZA',6,('prior',),45,'High'),('250000','US',6,('prior',),100,'High'),
    ('150000','US',8,(),65,'High')])
def test_independent_component_combinations(amount,country,count,matches,score,level):
    row=record(amount);row['country']=country
    r=evaluate(row,count,duplicate_matches=matches,evaluated_at=STAMP)
    assert (r['score'],r['risk_level'])==(score,level)
    assert r['score']==sum(c['points'] for c in r['components'])
    assert all(c['rule_version']==RULE_VERSION for c in r['components'])

def test_cap_and_no_retired_synthetic_dimensions():
    cfg=replace(ScoringConfig(),very_high_points=100)
    row=record('250000',merchant='HighRisk Shop',tx_type='transfer');row['country']='US'
    r=evaluate(row,6,cfg,duplicate_matches=('other',))
    assert r['score']==100
    assert not {'TRANSFER','MERCHANT_MARKER'} & {c['rule'] for c in r['triggered_rules']}

def test_frozen_velocity_evidence_and_deterministic_evaluation():
    row=record('150000');row['country']='US'
    evidence={'observed_window_start':'2026-10-13T09:55:00+00:00','observed_window_end':STAMP}
    first=evaluate(row,8,evaluated_at=STAMP,velocity_evidence=evidence)
    assert first==evaluate(row,8,evaluated_at=STAMP,velocity_evidence=evidence)
    c=next(c for c in first['components'] if c['rule']=='HIGH_VELOCITY')
    assert (c['triggered_value'],c['threshold'],c['window_seconds'],c['points'])==(8,5,300,25)
    assert c['window_start']=='2026-10-13T09:55:00+00:00' and c['window_end']==STAMP
    assert c['observed_window_start']==evidence['observed_window_start'] and c['includes_current'] and c['closed_window']

def test_duplicate_and_explicit_cross_border_measurements():
    evidence=[{'tx_id':'prior','tx_date':STAMP,'seconds_apart':30}]
    row=record(cross_border=True)
    r=evaluate(row,duplicate_matches=('prior',),duplicate_evidence=evidence)
    cross=r['components'][1];duplicate=r['components'][3]
    assert cross['triggered_value']=='ZA' and cross['explicit_cross_border']
    assert cross['reason']=='Explicit cross-border flag' and cross['points']==15
    assert duplicate['matching_transactions']==evidence and duplicate['matching_transaction_ids']==['prior']
    assert duplicate['threshold']==120 and duplicate['points']==20
    assert duplicate['matching_fields']==['account_id','merchant','amount','currency','source_system','tx_type']

@pytest.mark.parametrize('currency',['ZAR','USD','EUR'])
def test_amount_bands_remain_in_original_currency(currency):
    row=record('150000');row['currency']=currency
    r=evaluate(row)
    assert r['score']==25 and r['components'][0]['currency']==currency

@pytest.mark.parametrize('amount',['-1','NaN','Infinity'])
def test_invalid_amounts_are_not_assessed(amount):
    with pytest.raises(ValueError):evaluate(record(amount))

@pytest.mark.parametrize('score',[-1,101,float('nan'),True])
def test_invalid_scores_are_not_classified(score):
    with pytest.raises(ValueError):classify_risk(score)

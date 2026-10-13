"""Read-model decisions use recorded evidence; never synthesize domain events."""
from datetime import datetime,timedelta,timezone
import pytest
from fintrust import analyst_workflow as model

NOW=datetime(2026,10,13,12,tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def default_policy(monkeypatch):
    for name in ('FINTRUST_REVIEW_SLA_SECONDS','FINTRUST_REVIEW_MEDIUM_SLA_SECONDS',
                 'FINTRUST_REVIEW_HIGH_SLA_SECONDS','FINTRUST_REVIEW_ESCALATED_SLA_SECONDS',
                 'FINTRUST_REVIEW_SLA_ENABLED','FINTRUST_REVIEW_SLA_DUE_SOON_SECONDS'):
        monkeypatch.delenv(name,raising=False)


@pytest.mark.parametrize('row,state,review',[
    ({'risk':{'score':0,'risk_level':'Low'}},'ASSESSED','NOT_REQUIRED'),
    ({'risk':{'score':25,'risk_level':'Medium'},'review_status':'OPEN'},'ASSESSED','OPEN'),
    ({'risk':{'score':55,'risk_level':'High'}},'ASSESSED','NOT_RECORDED'),
    ({'raw_file':'seed/week13-day2.csv'},'HISTORICAL','HISTORICAL'),
    ({'raw_file':'modern.csv','tx_date':NOW-timedelta(days=500)},'NOT_RECORDED','NOT_RECORDED'),
    ({'assessment_pending':True},'PENDING','NOT_RECORDED'),
    ({'assessment_failed':True},'FAILED','NOT_RECORDED'),
    ({'risk':{'risk_level':'Low'}},'NOT_RECORDED','NOT_RECORDED'),
    ({'risk':{'score':False,'risk_level':'Low'}},'NOT_RECORDED','NOT_RECORDED'),
])
def test_missing_assessment_is_never_low_or_an_invented_review(row,state,review):
    snapshot=dict(row)
    value=model.assessment(row)
    assert value['assessment_state']==state and value['review_state']==review
    assert value.get('risk')==snapshot.get('risk')


@pytest.mark.parametrize('field,value',[
    ('batch_id','new-run'),('source_transaction_id','new-reference'),
    ('source_system','new-source'),('transaction_fingerprint','new-fingerprint'),('has_occurrence',True)
])
def test_seed_filename_cannot_hide_modern_provenance(field,value):
    row={'raw_file':'seed/week13-day2.csv',field:value}
    assert model.assessment(row)['assessment_state']=='NOT_RECORDED'


@pytest.mark.parametrize('level,hours,target,state',[
    ('Medium',1,86400,'WITHIN_SLA'),('Medium',23.5,86400,'DUE_SOON'),
    ('High',3.5,14400,'DUE_SOON'),('High',5,14400,'OVERDUE'),
    ('High',4,14400,'OVERDUE'),('Low',10,None,'NOT_APPLICABLE')
])
def test_recorded_review_age_uses_configured_risk_tier(level,hours,target,state):
    row={'risk':{'risk_level':level},'review_status':'UNDER_REVIEW','created_at':NOW-timedelta(hours=hours)}
    value=model.review(row,NOW)
    assert value['sla_seconds']==target and value['sla_state']==state
    if target is not None:assert value['sla_due_at']==row['created_at']+timedelta(seconds=target)


def test_reassignment_and_notes_do_not_restart_escalation_clock():
    created=NOW-timedelta(hours=10); escalation=NOW-timedelta(hours=3)
    history=[{'version':1,'before_status':None,'after_status':'OPEN','reviewer_subject':None,'actor_subject':'scoring-worker','changed_at':created},
             {'version':2,'before_status':'OPEN','after_status':'UNDER_REVIEW','reviewer_subject':'analyst01','actor_subject':'analyst01','changed_at':created+timedelta(minutes=1)},
             {'version':3,'before_status':'UNDER_REVIEW','after_status':'ESCALATED','reviewer_subject':'analyst01','actor_subject':'analyst01','changed_at':escalation},
             {'version':4,'before_status':'ESCALATED','after_status':'ESCALATED','reviewer_subject':'analyst02','actor_subject':'admin01','changed_at':NOW-timedelta(minutes=5)}]
    row={'created_at':created,'review_status':'ESCALATED','reviewer_subject':'analyst02','risk':{'risk_level':'High'}}
    value=model.review(row,NOW,history)
    assert value['assigned_by']=='admin01' and value['assigned_at']==history[-1]['changed_at']
    assert value['escalated_at']==escalation and value['sla_due_at']==escalation+timedelta(hours=2)
    assert value['sla_state']=='OVERDUE' and value['overdue_seconds']==3600


def test_missing_escalation_timestamp_never_restarts_from_review_creation():
    row={'created_at':NOW-timedelta(hours=30),'review_status':'ESCALATED','risk':{'risk_level':'High'}}
    value=model.review(row,NOW)
    assert value['sla_state']=='NOT_RECORDED' and value['sla_due_at'] is None


def test_terminal_decision_has_no_active_sla_breach():
    row={'created_at':NOW-timedelta(hours=30),'review_status':'CLEARED','risk':{'risk_level':'High'}}
    value=model.review(row,NOW)
    assert value['sla_state']=='NOT_APPLICABLE' and not value['over_sla'] and value['remaining_seconds'] is None


def test_custom_policy_and_explicit_disabled_configuration(monkeypatch):
    monkeypatch.setenv('FINTRUST_REVIEW_HIGH_SLA_SECONDS','7200')
    row={'created_at':NOW-timedelta(hours=3),'review_status':'OPEN','risk':{'risk_level':'High'}}
    assert model.review(row,NOW)['sla_state']=='OVERDUE'
    monkeypatch.setenv('FINTRUST_REVIEW_SLA_ENABLED','false')
    assert model.review(row,NOW)['sla_state']=='NOT_CONFIGURED'
    assert row['sla_due_at'] is None and not row['over_sla']


@pytest.mark.parametrize('name,value',[
    ('FINTRUST_REVIEW_HIGH_SLA_SECONDS','0'),('FINTRUST_REVIEW_MEDIUM_SLA_SECONDS','3.5'),
    ('FINTRUST_REVIEW_ESCALATED_SLA_SECONDS','999999999'),('FINTRUST_REVIEW_SLA_ENABLED','maybe')
])
def test_invalid_policy_fails_instead_of_displaying_a_false_target(monkeypatch,name,value):
    monkeypatch.setenv(name,value)
    with pytest.raises(ValueError):model.policy()


def test_primary_reason_uses_frozen_count_and_window():
    risk={'score':25,'risk_level':'Medium','triggered_rules':[{'rule':'HIGH_VELOCITY','triggered_value':8,'window_seconds':300}]}
    assert model.primary_reason(risk)=='High velocity · 8 in 5 min'
    assert risk['triggered_rules'][0]['triggered_value']==8


def test_a_truncated_history_cannot_invent_assignment_at_its_first_visible_note():
    fields=model.history_fields([{'version':500,'reviewer_subject':'analyst01','actor_subject':'analyst01','changed_at':NOW,'before_status':'UNDER_REVIEW','after_status':'UNDER_REVIEW'}],'analyst01')
    assert fields['assigned_at'] is None


@pytest.mark.parametrize('risk,expected',[
    ({'score':0,'risk_level':'Low','triggered_rules':[]},'No triggered rules'),
    ({'risk_level':'Low','triggered_rules':[]},'No recorded explanation'),
    ({'score':0,'risk_level':'Low'},'No recorded explanation'),
    ({'risk_level':'Low','reason':'Original recorded explanation'},'Original recorded explanation'),
])
def test_primary_explanation_does_not_turn_missing_rule_evidence_into_no_rules(risk,expected):
    assert model.primary_reason(risk)==expected


def test_subsecond_before_sla_deadline_is_due_soon_not_a_false_breach():
    row={'created_at':NOW-timedelta(hours=4),'review_status':'OPEN','risk':{'risk_level':'High'}}
    value=model.review(row,NOW-timedelta(milliseconds=500))
    assert value['sla_due_at']==NOW
    assert value['sla_state']=='DUE_SOON' and not value['over_sla']
    assert value['sla_label']=='Due soon · <1m remaining'
    assert model.review(row,NOW)['sla_state']=='OVERDUE'

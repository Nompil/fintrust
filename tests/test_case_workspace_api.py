"""Scoped case queues and durable requested-referral evidence on disposable PG.

Calendar fixtures establish an initial immutable creation clock with INSERT;
they never rewrite the creation timestamps or history of an existing review.
"""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from psycopg2.extras import Json

from fintrust import analyst_workflow
from tests.test_multi_user_operations import people, assignment
from tests.test_release1_end_to_end import release_db, feed, run
from tests.test_release1_workflows import row, ACCOUNT


def claimed_case(database, identity='REFERRAL-CASE'):
    result = run(feed([row(source_transaction_id=identity, amount='210000',
                          tx_date='2026-10-09T08:00:00Z', merchant='Referral evidence')]))[0]
    return result['risk_event_id'], result['transaction_id']


def referral_body(target='analyst:analyst02', request_id=None):
    return {'request_id': request_id or str(uuid.uuid4()), 'expected_version': 2,
            'status': 'ESCALATED', 'resolution_code': 'SPECIALIST_REVIEW',
            'notes': 'Recorded source and account context require a requested review',
            'referral_target': target}


def test_referral_is_durable_idempotent_evidence_and_not_assignment(release_db, people):
    client, headers, _ = people
    event, tx = claimed_case(release_db)
    assert assignment(client, headers, event, 'analyst01', 'analyst01').status_code == 200
    original = release_db[3]('SELECT row_to_json(t),p.result FROM transactions t JOIN processed_transactions p USING(tx_id) WHERE tx_id=%s', (tx,))
    options = client.get(f'/v1/reviews/{event}/referral-targets', headers=headers('analyst01'))
    assert options.status_code == 200, options.json
    assert {item['value'] for item in options.json['data']} == {'SPECIALIST_REVIEW', 'analyst:analyst02'}
    assert all('specialist' not in item['label'].lower() for item in options.json['data'] if item['value'].startswith('analyst:'))
    body = referral_body()
    response = client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=body)
    assert response.status_code == 200, response.json
    replay = client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=body)
    assert replay.status_code == 200 and replay.json['data']['replayed']
    assert release_db[3]('SELECT review_status,reviewer_subject,version FROM risk_reviews WHERE risk_event_id=%s', (event,)) == [('ESCALATED', 'analyst01', 3)]
    assert release_db[3]('SELECT count(*) FROM risk_review_history WHERE risk_event_id=%s', (event,)) == [(3,)]
    detail = client.get(f'/v1/risk-events/{event}', headers=headers('analyst01')).json['data']
    assert detail['referral_target'] == 'analyst:analyst02' and detail['review_notes'] == body['notes']
    assert detail['review_history'][-1]['referral_target'] == 'analyst:analyst02'
    assert detail['review_history'][-1]['notes'] == body['notes']
    assert detail['sla_seconds'] == 7200
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json={**body, 'referral_target': 'SPECIALIST_REVIEW'}).status_code == 409
    # Administrator allocation is a separate, attributed action.
    assert assignment(client, headers, event, 'admin01', 'analyst02', 3).status_code == 200
    assigned = client.get(f'/v1/risk-events/{event}', headers=headers('admin01')).json['data']
    assert assigned['reviewer_subject'] == 'analyst02' and assigned['referral_target'] == 'analyst:analyst02'
    assert assigned['sla_due_at'] == detail['sla_due_at']
    assert release_db[3]('SELECT actor_subject,before_status,after_status FROM risk_review_history WHERE risk_event_id=%s ORDER BY version', (event,)) == [
        ('scoring-worker', None, 'OPEN'), ('analyst01', 'OPEN', 'UNDER_REVIEW'),
        ('analyst01', 'UNDER_REVIEW', 'ESCALATED'), ('admin01', 'ESCALATED', 'ESCALATED')]
    assert release_db[3]('SELECT row_to_json(t),p.result FROM transactions t JOIN processed_transactions p USING(tx_id) WHERE tx_id=%s', (tx,)) == original


@pytest.mark.parametrize('who', ['analyst02', 'admin01', 'auditor01', 'maintainer01'])
def test_referral_options_and_mutation_require_current_scoped_analyst_owner(release_db, people, who):
    client, headers, _ = people
    event, _ = claimed_case(release_db)
    assert assignment(client, headers, event, 'analyst01', 'analyst01').status_code == 200
    assert client.get(f'/v1/reviews/{event}/referral-targets', headers=headers(who)).status_code == 403
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers(who), json=referral_body()).status_code == 403
    assert release_db[3]('SELECT count(*) FROM risk_review_history WHERE risk_event_id=%s', (event,)) == [(2,)]


@pytest.mark.parametrize('target,expected', [
    ('analyst:analyst01', 400), ('analyst:admin01', 403), ('analyst:auditor01', 403),
    ('analyst:maintainer01', 403), ('analyst:missing', 403), ('UNKNOWN_DESTINATION', 400),
])
def test_referral_target_validation_never_changes_ownership_or_history(release_db, people, target, expected):
    client, headers, _ = people
    event, _ = claimed_case(release_db)
    assert assignment(client, headers, event, 'analyst01', 'analyst01').status_code == 200
    response = client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=referral_body(target))
    assert response.status_code == expected, response.json
    assert release_db[3]('SELECT review_status,reviewer_subject,version FROM risk_reviews WHERE risk_event_id=%s', (event,)) == [('UNDER_REVIEW', 'analyst01', 2)]


def test_options_do_not_disclose_foreign_account_user_and_disabled_target_is_denied(release_db, people):
    client, headers, registry_path = people
    registry = json.loads(registry_path.read_text())
    registry['principals'].append({'subject':'foreign-analyst', 'display_name':'Foreign Account Person',
        'role':'Risk/Compliance Analyst', 'status':'ACTIVE', 'accounts':['20000000-0000-4000-8000-000000000002'],
        'created_at':datetime.now(timezone.utc).isoformat(), 'token_sha256':hashlib.sha256(('6'*64).encode()).hexdigest()})
    registry_path.write_text(json.dumps(registry))
    event, _ = claimed_case(release_db)
    assert assignment(client, headers, event, 'analyst01', 'analyst01').status_code == 200
    options = client.get(f'/v1/reviews/{event}/referral-targets', headers=headers('analyst01'))
    assert options.status_code == 200 and 'Foreign Account Person' not in str(options.json) and 'foreign-analyst' not in str(options.json)
    denied = client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=referral_body('analyst:foreign-analyst'))
    assert denied.status_code == 403
    change = {'username':'analyst02', 'display_name':'Second Analyst', 'role':'Risk/Compliance Analyst', 'status':'DISABLED', 'notes':'Controlled unavailable recipient'}
    assert client.post('/v1/administration/users', headers=headers('admin01'), json=change).status_code == 200
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=referral_body()).status_code == 403


def test_replay_preserves_prior_referral_when_recipient_is_disabled(release_db, people):
    client, headers, _ = people
    event, _ = claimed_case(release_db)
    assert assignment(client, headers, event, 'analyst01', 'analyst01').status_code == 200
    body = referral_body()
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=body).status_code == 200
    history = release_db[3]('SELECT row_to_json(h) FROM risk_review_history h WHERE risk_event_id=%s ORDER BY version', (event,))
    change = {'username':'analyst02', 'display_name':'Second Analyst', 'role':'Maintainer', 'status':'DISABLED', 'notes':'Controlled recipient role and status change'}
    assert client.post('/v1/administration/users', headers=headers('admin01'), json=change).status_code == 200
    replay = client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=body)
    assert replay.status_code == 200 and replay.json['data']['replayed']
    assert release_db[3]('SELECT row_to_json(h) FROM risk_review_history h WHERE risk_event_id=%s ORDER BY version', (event,)) == history
    assert client.get(f'/v1/risk-events/{event}', headers=headers('analyst01')).json['data']['referral_target'] == body['referral_target']


def test_legacy_escalation_has_no_manufactured_referral_and_target_is_escalation_only(release_db, people):
    client, headers, _ = people
    event, _ = claimed_case(release_db)
    assert assignment(client, headers, event, 'analyst01', 'analyst01').status_code == 200
    wrong = {**referral_body(), 'status':'CLEARED', 'resolution_code':'VALID_ACTIVITY'}
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=wrong).status_code == 400
    legacy = referral_body(); legacy.pop('referral_target')
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json=legacy).status_code == 200
    detail = client.get(f'/v1/risk-events/{event}', headers=headers('analyst01')).json['data']
    assert detail['referral_target'] is None and detail['review_notes'] == legacy['notes']
    assert detail['review_history'][-1].get('referral_target') is None


def initial_review(database, created_at, identity, level='High', account=ACCOUNT):
    """Create a fresh schema-valid review fixture with its initial source clock."""
    query = database[3]; tx = str(uuid.uuid4()); score = 40 if level == 'High' else 25
    query('''INSERT INTO transactions(tx_id,account_id,amount,currency,merchant,tx_date,tx_type,raw_file,
        source_system,source_transaction_id,transaction_fingerprint,country)
        VALUES(%s,%s,%s,'ZAR','Calendar fixture',%s,'debit','controlled/calendar.csv','calendar-fixture',%s,%s,'ZA')''',
        (tx, account, '210000' if level=='High' else '150000', created_at, identity, hashlib.sha256(identity.encode()).hexdigest()))
    event = query('INSERT INTO risk_events(tx_id,risk_score,reason) VALUES(%s,%s,%s) RETURNING risk_event_id', (tx, score, 'Controlled recorded assessment'))[0][0]
    query('INSERT INTO processed_transactions(tx_id,fingerprint,result) VALUES(%s,%s,%s)', (tx, hashlib.sha256(tx.encode()).hexdigest(),
        Json({'score':score, 'risk_level':level, 'rule_version':'fintrust-r2-rules-2026-10-13', 'triggered_rules':[]})))
    query("INSERT INTO risk_reviews(risk_event_id,created_at,change_actor) VALUES(%s,%s,'scoring-worker')", (event, created_at))
    return event


def test_due_today_is_sast_calendar_day_full_scope_before_pagination(release_db, people, monkeypatch):
    client, headers, _ = people
    now = datetime(2026, 10, 14, 21, 30, tzinfo=timezone.utc)  # 23:30 SAST
    monkeypatch.setattr(analyst_workflow, 'now_utc', lambda: now)
    at_midnight = datetime(2026, 10, 13, 22, 0, tzinfo=timezone.utc)
    today_overdue = initial_review(release_db, at_midnight-timedelta(hours=4), 'DAY-START')
    today_last = initial_review(release_db, datetime(2026,10,14,21,59,59,tzinfo=timezone.utc)-timedelta(hours=4), 'DAY-LAST')
    tomorrow = initial_review(release_db, datetime(2026,10,14,22,0,tzinfo=timezone.utc)-timedelta(hours=4), 'NEXT-DAY')
    foreign = initial_review(release_db, now-timedelta(hours=5), 'FOREIGN-DAY', account='20000000-0000-4000-8000-000000000002')
    history = release_db[3]('SELECT row_to_json(h) FROM risk_review_history h ORDER BY risk_event_id,version')
    response = client.get('/v1/workflows/reviews?queue=due_today&limit=1', headers=headers('analyst01'))
    assert response.status_code == 200, response.json
    assert response.json['meta']['total_count'] == 2 and response.json['meta']['has_more']
    assert response.json['data'][0]['risk_event_id'] == today_overdue
    all_today = client.get('/v1/workflows/reviews?queue=due_today&limit=100', headers=headers('analyst01')).json
    assert {r['risk_event_id'] for r in all_today['data']} == {today_overdue, today_last}
    assert tomorrow not in {r['risk_event_id'] for r in all_today['data']} and foreign not in {r['risk_event_id'] for r in all_today['data']}
    counts = response.json['meta']['scope_counts']
    assert counts['due_today'] == 2 and counts['overdue'] == 1 and counts['unassigned'] == 3
    overview = client.get('/v1/release1/overview', headers=headers('analyst01')).json['data']
    insight = client.get('/v1/release1/insights?days=all', headers=headers('analyst01')).json['data']['metrics']
    assert overview['due_today'] == insight['due_today'] == 2
    assert overview['reviews_over_sla'] == insight['reviews_over_sla'] == 1
    assert release_db[3]('SELECT row_to_json(h) FROM risk_review_history h ORDER BY risk_event_id,version') == history
    assert analyst_workflow.policy()['targets'] == {'MEDIUM':86400, 'HIGH':14400, 'ESCALATED':7200}

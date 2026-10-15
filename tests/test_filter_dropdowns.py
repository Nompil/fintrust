"""Scoped dropdown values and real filtering; disposable SQL and synthetic users."""
import json
import uuid
import pytest
from tests.test_multi_user_operations import people, assignment
from tests.test_release1_end_to_end import release_db, run, feed
from tests.test_release1_workflows import row, ACCOUNT


def test_choices_cover_scope_not_first_page_and_apply(release_db, people):
    client, headers, _ = people
    run(feed([row(source_transaction_id='DROPDOWN-ZA',country='ZA',amount='210001'),
              row(source_transaction_id='DROPDOWN-US',country='US',amount='210002')]))
    q = release_db[3]
    event = q("SELECT r.risk_event_id FROM risk_events r JOIN transactions t USING(tx_id) WHERE source_transaction_id='DROPDOWN-ZA'")[0][0]
    assert assignment(client,headers,event,'admin01','analyst02').status_code == 200
    response = client.get('/v1/filter-options',headers=headers('analyst01'))
    assert response.status_code == 200
    data = response.json['data']
    assert 'ZA' in data['countries'] and 'US' in data['countries']
    assert data['assignees'] == [{'value':'analyst02','label':'analyst02'}]
    assert all('token' not in str(item).lower() and 'email' not in str(item).lower() for item in data['assignees'])
    filtered = client.get('/v1/workflows/transactions?country=US&limit=1',headers=headers('analyst01'))
    assert filtered.status_code == 200 and filtered.json['data']
    assert all(item['country'] == 'US' for item in filtered.json['data'])
    events = client.get('/v1/workflows/reviews?assignee=analyst02',headers=headers('analyst01'))
    assert events.status_code == 200 and all(item['reviewer_subject']=='analyst02' for item in events.json['data'])
    assert client.get('/v1/release1/insights?days=all&country=US',headers=headers('analyst01')).status_code == 200


def test_options_never_leak_another_account_or_owner(release_db, people):
    client,headers,_ = people
    other = '20000000-0000-4000-8000-000000000002'
    run(feed([row(account_id=other,source_transaction_id='OUTSIDE-SCOPE',country='FR',amount='210001')]))
    q=release_db[3]
    q("UPDATE risk_reviews SET review_status='UNDER_REVIEW',reviewer_subject='outside-owner',change_actor='outside-owner',review_notes='Synthetic fixture',version=version+1,change_request_id=%s WHERE risk_event_id=(SELECT r.risk_event_id FROM risk_events r JOIN transactions t USING(tx_id) WHERE source_transaction_id='OUTSIDE-SCOPE')",(str(uuid.uuid4()),))
    data=client.get('/v1/filter-options',headers=headers('analyst01')).json['data']
    assert 'FR' not in data['countries'] and 'outside-owner' not in json.dumps(data)
    assert client.get('/v1/filter-options?account_id='+other,headers=headers('analyst01')).status_code == 403
    assert client.get('/v1/filter-options?account_id='+ACCOUNT,headers=headers('auditor01')).status_code == 200
    assert client.get('/v1/filter-options',headers=headers('maintainer01')).status_code == 403
    assert client.get('/v1/filter-options').status_code == 401


@pytest.mark.parametrize('query',['account_id=x','account_id='+ACCOUNT+'&account_id='+ACCOUNT,'limit=25','country=ZA'])
def test_invalid_or_extra_options_filters_refused(release_db, people, query):
    client,headers,_=people
    assert client.get('/v1/filter-options?'+query,headers=headers('analyst01')).status_code == 400


def test_empty_scope_returns_no_choices(release_db):
    from fintrust.auth import Principal
    from fintrust.filter_options import read
    from werkzeug.datastructures import MultiDict
    assert read(Principal('empty','Read-only/Auditor',()),MultiDict()) == {
        'countries':[],'transaction_types':[],'assignees':[]}

"""Real SQL analytical filters; invalid rows never inherit accepted risk filters."""
import pytest
from tests.test_release1_end_to_end import release_db, feed, run
from tests.test_multi_user_operations import people
from tests.test_release1_workflows import row, ACCOUNT

def test_filters_change_full_aggregate_and_scoped_detail(release_db, people):
    client, headers, _ = people
    run(feed([row(source_transaction_id='LOW-UX',amount='10',country='ZA'),row(source_transaction_id='HIGH-UX',amount='200000.01',country='US'),row(source_transaction_id='BAD-UX',amount='bad')]))
    path='/v1/release1/insights?days=all'
    base=client.get(path,headers=headers('analyst01')).json['data']
    assert base['metrics']['transactions']==release_db[3]('SELECT count(*) FROM transactions WHERE account_id=%s',(ACCOUNT,))[0][0]
    assert base['metrics']['high_risk_rate']==50
    assert base['metrics']['quarantined']==1
    for query in ['risk_level=High','country=US&risk_level=High','scenario=HIGH_AMOUNT','review_status=OPEN','tx_type=debit&country=US&risk_level=High','risk_level=High&country=US&scenario=CROSS_BORDER']:
        response=client.get(path+'&'+query,headers=headers('analyst01'))
        assert response.status_code==200,response.json
        data=response.json['data']
        assert data['metrics']['transactions']==1
        assert len(data['transactions'])==1
        assert data['transactions'][0]['risk_level']=='High'
        assert data['high_accounts']==[{'label':ACCOUNT,'count':1}]
        assert sum(r['count'] for r in data['risk_trend'])==1
        assert data['metrics']['quarantined']==1
        assert 'do not apply to invalid rows' in data['quality_scope_note']
    empty=client.get(path+'&risk_level=Low&country=US',headers=headers('analyst01')).json['data']
    assert empty['metrics']['transactions']==0 and empty['metrics']['high_risk_rate'] is None
    assert empty['transactions']==[]
    assert client.get(path+'&account_id=20000000-0000-4000-8000-000000000002',headers=headers('analyst01')).status_code==403
    assert client.get(path,headers=headers('maintainer01')).status_code==403

@pytest.mark.parametrize('query',['risk_level=Critical','scenario=unknown','review_status=FINISHED','tx_type=refund','country=ZAR','country=US%27','from=broken','from=2026-10-10&to=2026-10-09','country=US&country=ZA'])
def test_invalid_analytical_filters_fail_closed(release_db,people,query):
    client,headers,_=people
    assert client.get('/v1/release1/insights?days=all&'+query,headers=headers('analyst01')).status_code==400

def test_date_boundaries_exclusive_end(release_db,people):
    client,headers,_=people
    run(feed([row(amount='200000.01',country='US')]))
    timestamp=release_db[3]('SELECT tx_date FROM processed_transactions JOIN transactions USING(tx_id)')[0][0]
    start=timestamp.isoformat().replace('+00:00','Z')
    from urllib.parse import urlencode
    inclusive=client.get('/v1/release1/insights?'+urlencode({'days':'all','from':start,'risk_level':'High'}),headers=headers('auditor01')).json['data']
    exclusive=client.get('/v1/release1/insights?'+urlencode({'days':'all','to':start,'risk_level':'High'}),headers=headers('auditor01')).json['data']
    assert inclusive['metrics']['transactions']==1
    assert exclusive['metrics']['transactions']==0

"""Report scope/date boundaries use accepted ledger data, never inferred balances."""
import pytest
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_multi_user_operations import people
from tests.test_release1_workflows import row

def test_report_period_currency_and_exclusive_end(release_db,people):
    # Keep this cohort separate from the rolling NOW()-based seed dates.
    c,h,_=people;run(feed([row(source_transaction_id='REPORT-A',amount='15',tx_date='2000-10-08T00:00:00Z'),row(source_transaction_id='REPORT-B',amount='20',tx_date='2000-10-09T00:00:00Z')]))
    response=c.get('/v1/reports?from=2000-10-08&to=2000-10-09&currency=ZAR',headers=h('auditor01'));assert response.status_code==200,response.json
    data=response.json['data'];assert len(data)==1 and data[0]['transactions']==1 and float(data[0]['gross_amount'])==15 and float(data[0]['net_movement'])==-15
    assert c.get('/v1/reports?from=9999-01-01',headers=h('auditor01')).json['data']==[]
    usd=c.get('/v1/reports?from=2000-10-08&to=2000-10-09&currency=USD',headers=h('auditor01')).json['data']
    assert all(item['currency']=='USD' for item in usd)
    expected=release_db[3]("SELECT count(*) FROM transactions WHERE account_id=%s AND currency='USD' AND tx_date>='2000-10-08' AND tx_date<'2000-10-09'",(row()['account_id'],))[0][0]
    assert sum(item['transactions'] for item in usd)==expected
    assert c.get('/v1/reports',headers=h('maintainer01')).status_code==403

@pytest.mark.parametrize('query',['from=bad','from=2026-10-09&to=2026-10-08','currency=zar','currency=ZAR%27','from=2026-01-01&from=2026-02-01'])
def test_report_invalid_filters_fail_closed(release_db,people,query):
    c,h,_=people;assert c.get('/v1/reports?'+query,headers=h('auditor01')).status_code==400


def test_report_sast_boundaries_and_scoped_currency_options(release_db,people):
    c,h,_=people
    run(feed([
        row(source_transaction_id='SAST-BEFORE',amount='1',tx_date='2000-10-07T21:59:59Z'),
        row(source_transaction_id='SAST-START',amount='15',tx_date='2000-10-07T22:00:00Z'),
        row(source_transaction_id='SAST-LAST',amount='20',currency='USD',tx_date='2000-10-08T21:59:59Z'),
        row(source_transaction_id='SAST-END',amount='30',currency='EUR',tx_date='2000-10-08T22:00:00Z'),
        row(source_transaction_id='OTHER-ACCOUNT-GBP',amount='50',currency='GBP',account_id='20000000-0000-4000-8000-000000000002',tx_date='2000-10-08T12:00:00Z'),
    ]))
    path='/v1/reports?from=2000-10-08&to=2000-10-09&date_timezone=Africa/Johannesburg'
    response=c.get(path,headers=h('analyst01'));assert response.status_code==200,response.json
    data=response.json['data']
    assert {(r['currency'],r['transactions'],float(r['gross_amount'])) for r in data}=={('ZAR',1,15),('USD',1,20)}
    assert response.json['meta']['date_timezone']=='Africa/Johannesburg'
    expected=release_db[3]("SELECT DISTINCT currency FROM transactions WHERE account_id=%s ORDER BY currency",(row()['account_id'],))
    assert response.json['meta']['currencies']==[r[0] for r in expected]
    assert 'EUR' in response.json['meta']['currencies']  # Outside period, still available in authorized ledger.
    assert 'GBP' not in response.json['meta']['currencies']  # Another account's currency must not leak.
    filtered=c.get(path+'&currency=USD&limit=1',headers=h('analyst01')).json
    assert len(filtered['data'])==1 and filtered['data'][0]['currency']=='USD'
    assert filtered['meta']['currencies']==response.json['meta']['currencies']
    assert c.get(path+'&account_id=20000000-0000-4000-8000-000000000005',headers=h('analyst01')).status_code==403
    assert c.get(path.replace('Africa/Johannesburg','invalid'),headers=h('analyst01')).status_code==400

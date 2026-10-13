"""Existing inclusive end bounds coexist with explicit analytical half-open bounds."""
from urllib.parse import urlencode
from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row


def test_transaction_end_is_inclusive_by_default_and_explicitly_exclusive_for_insights(release_db,people):
    client,headers,_=people
    result=run(feed([row(source_transaction_id='END-BOUNDARY',amount='10',tx_date='2026-10-08T22:00:00Z')]))[0]
    filters={'source_id':'END-BOUNDARY','to':'2026-10-08T22:00:00Z'}
    path='/v1/workflows/transactions?'
    for mode in (None,'0','1'):
        query={**filters,**({'to_exclusive':mode} if mode is not None else {})}
        response=client.get(path+urlencode(query),headers=headers('analyst01'))
        assert response.status_code==200,response.json
        assert [item['tx_id'] for item in response.json['data']]==([] if mode=='1' else [result['transaction_id']])
    malformed=client.get(path+urlencode({**filters,'to_exclusive':'yes'}),headers=headers('analyst01'))
    assert malformed.status_code==400
    analytical=client.get('/v1/release1/insights?'+urlencode({'days':'all','risk_level':'Low','to':filters['to']}),headers=headers('analyst01'))
    assert analytical.status_code==200,analytical.json
    assert analytical.json['data']['metrics']['transactions']==0

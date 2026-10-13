"""Actual delivery receipts survive the additive Analyst alert projection."""
from datetime import datetime,timezone
import pytest
from fintrust import analyst_workflow,dynamo
from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row,ACCOUNT


@pytest.mark.parametrize('claim,receipt,assessment,level,expected,source',[
    ({'delivery_state':'SENT'},'FAILED','ASSESSED','High','SENT','DYNAMODB_CLAIM'),
    ({'delivery_state':'FAILED'},'SENT','ASSESSED','High','FAILED','DYNAMODB_CLAIM'),
    ({'delivery_state':'UNKNOWN'},'SENT','ASSESSED','High','UNKNOWN','DYNAMODB_CLAIM'),
    ({'delivery_state':'RETRYING'},None,'ASSESSED','High','RETRYING','DYNAMODB_CLAIM'),
    ({'delivery_state':'UNAVAILABLE'},'SENT','ASSESSED','High','SENT','SQL_RECEIPT'),
    ({},'FAILED','ASSESSED','High','FAILED','SQL_RECEIPT'),
    ({},None,'HISTORICAL',None,'NOT_APPLICABLE','HISTORICAL_PROVENANCE'),
    ({},None,'NOT_RECORDED',None,'NOT_RECORDED','MISSING_ASSESSMENT_EVIDENCE'),
    ({},None,'ASSESSED','Low','NOT_REQUIRED','RECORDED_ASSESSMENT_POLICY'),
    ({},None,'ASSESSED','High','PENDING','REQUIRED_ALERT_INTENT'),
])
def test_delivery_projection_preserves_actual_receipts_and_never_infers_email_delivery(claim,receipt,assessment,level,expected,source):
    result=analyst_workflow.alert_projection({'assessment_state':assessment,'risk':{'risk_level':level}},claim,[{'delivery_state':receipt}] if receipt else [])
    assert result['alert_state']==expected and result['alert_state_source']==source


@pytest.mark.parametrize('state',['SENT','FAILED'])
def test_transaction_detail_and_lifecycle_show_actual_sql_delivery(release_db,people,monkeypatch,state):
    client,headers,_=people;query=release_db[3]
    result=run(feed([row(source_transaction_id='DELIVERY-'+state,amount='210000')]))[0]
    query('INSERT INTO alerts(risk_event_id,severity,message,delivery_state,sent_at) VALUES(%s,%s,%s,%s,%s)',
          (result['risk_event_id'],'High','Controlled delivery receipt',state,datetime.now(timezone.utc) if state=='SENT' else None))
    ledger=query('SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s',(result['transaction_id'],))
    monkeypatch.setattr(dynamo,'get_item',lambda *args,**kwargs:None)
    for suffix in ('','/lifecycle'):
        response=client.get('/v1/transactions/'+result['transaction_id']+suffix,headers=headers('analyst01'))
        assert response.status_code==200,response.json
        assert response.json['data']['alert_state']==state
        assert response.json['data']['alert_state_source']=='SQL_RECEIPT'
    detail=client.get('/v1/transactions/'+result['transaction_id'],headers=headers('analyst01')).json['data']
    # Preserve the original separately sourced cloud contract, which is an
    # intent fallback here, not a statement that the SQL receipt is absent.
    assert detail['cloud_alert']['delivery_state']=='PENDING'
    assert query('SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s',(result['transaction_id'],))==ledger


def test_detail_missing_and_historical_records_do_not_inherit_no_alert_required(release_db,people,monkeypatch):
    client,headers,_=people;query=release_db[3]
    monkeypatch.setattr(dynamo,'get_item',lambda *args,**kwargs:None)
    historical=query("SELECT tx_id::text FROM transactions t WHERE account_id=%s AND NOT EXISTS(SELECT 1 FROM risk_events r WHERE r.tx_id=t.tx_id) ORDER BY tx_id LIMIT 1",(ACCOUNT,))[0][0]
    response=client.get('/v1/transactions/'+historical,headers=headers('analyst01'))
    assert response.status_code==200,response.json
    assert response.json['data']['alert_state']=='NOT_APPLICABLE'
    modern=run(feed([row(source_transaction_id='MISSING-DELIVERY-SCORE',amount='10')]))[0]['transaction_id']
    query("UPDATE processed_transactions SET result=result-'score' WHERE tx_id=%s",(modern,))
    response=client.get('/v1/transactions/'+modern,headers=headers('analyst01'))
    assert response.status_code==200,response.json
    assert response.json['data']['alert_state']=='NOT_RECORDED'
    assert response.json['data']['cloud_alert']['delivery_state']=='NOT_REQUIRED'

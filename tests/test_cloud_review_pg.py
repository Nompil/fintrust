"""Real isolated SQL; Cognito gateway claims and AWS services are mocked."""
import time,uuid
import boto3
from fintrust import api,cognito_auth,workflow_api,cloud_directory
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row,ACCOUNT

def test_cloud_analyst_claim_note_decide_and_scope_revocation_without_local_registry(release_db,monkeypatch):
    run(feed([row(source_transaction_id='CLOUD-REVIEW',amount='200000.01',country='US')]))
    query=release_db[3];event=query('SELECT risk_event_id FROM risk_events ORDER BY risk_event_id DESC LIMIT 1')[0][0]
    monkeypatch.setattr(workflow_api,'connection',release_db[2])
    for key,value in {'AUTH_MODE':'cognito','AWS_EXECUTION_ENV':'AWS_Lambda_python3.12','FINTRUST_MODE':'cloud',
                      'COGNITO_USER_POOL_ID':'af-south-1_TestPool','COGNITO_APP_CLIENT_ID':'testclient',
                      'COGNITO_DOMAIN':'https://auth.example.test','COGNITO_REDIRECT_URI':'https://api.example.test/dev/',
                      'COGNITO_LOGOUT_URI':'https://api.example.test/dev/','COGNITO_USER_SCOPE_TABLE':'workforce-scopes'}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.delenv('FINTRUST_AUTH_FILE',raising=False)
    table=boto3.resource('dynamodb',region_name='af-south-1').create_table(TableName='workforce-scopes',BillingMode='PAY_PER_REQUEST',
        AttributeDefinitions=[{'AttributeName':'subject','AttributeType':'S'}],KeySchema=[{'AttributeName':'subject','KeyType':'HASH'}])
    subject='30000000-0000-4000-8000-000000000001'
    table.put_item(Item={'subject':cloud_directory.KEY,'schema_version':1,'users':[{'username':'analyst01','cognito_sub':subject}]})
    scope={'subject':subject,'username':'analyst01','status':'ACTIVE','group':'Analysts','accounts':[ACCOUNT]}
    table.put_item(Item=scope)
    now=int(time.time())
    token=cognito_auth.set_gateway_claims({'iss':'https://cognito-idp.af-south-1.amazonaws.com/af-south-1_TestPool',
        'sub':subject,'username':'analyst01','client_id':'testclient','token_use':'access','scope':'openid profile',
        'cognito:groups':'Analysts','iat':str(now),'exp':str(now+300)})
    client=api.app.test_client();headers={'Authorization':'Bearer gateway-validated-token'}
    try:
        response=client.get(f'/v1/risk-events/{event}',headers=headers)
        assert response.status_code==200,response.json
        response=client.post(f'/v1/reviews/{event}/assignment',headers=headers,json={
            'request_id':str(uuid.uuid4()),'expected_version':1,'assignee':'analyst01','notes':'Cloud investigation claim'})
        assert response.status_code==200,response.json
        response=client.post(f'/v1/reviews/{event}/notes',headers=headers,json={
            'request_id':str(uuid.uuid4()),'expected_version':2,'notes':'Checked the recorded source evidence'})
        assert response.status_code==200,response.json
        response=client.post(f'/v1/reviews/{event}/transition',headers=headers,json={
            'request_id':str(uuid.uuid4()),'expected_version':3,'status':'CLEARED','resolution_code':'VALID_ACTIVITY','notes':'Evidence reviewed'})
        assert response.status_code==200,response.json
        assert query('SELECT after_status FROM risk_review_history WHERE risk_event_id=%s ORDER BY version',(event,))[-1]==('CLEARED',)
        scope['accounts']=[];table.put_item(Item=scope)
        assert client.get(f'/v1/risk-events/{event}',headers=headers).status_code==404
        scope['status']='DISABLED';table.put_item(Item=scope)
        assert client.get('/v1/session',headers=headers).status_code==401
    finally:cognito_auth.reset_gateway_claims(token)

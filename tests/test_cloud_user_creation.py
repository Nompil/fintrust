import json
import uuid
import boto3
import pytest
from moto import mock_aws
from fintrust import cloud_users
from fintrust.auth import Principal

ACCOUNT='20000000-0000-4000-8000-000000000001'
ADMIN_SUB='10000000-0000-4000-8000-000000000001'
NEW_SUB='10000000-0000-4000-8000-000000000002'
ADMIN=Principal('admin01','Admin',(ACCOUNT,),auth_source='cognito')


class Cognito:
    def __init__(self):self.created=0;self.invited=0;self.fail=None;self.groups=['Administrators']
    def admin_list_groups_for_user(self,**kwargs):return {'Groups':[{'GroupName':g} for g in self.groups]}
    def admin_create_user(self,**kwargs):
        assert 'TemporaryPassword' not in kwargs and kwargs['ForceAliasCreation'] is False
        if kwargs['MessageAction']=='RESEND':
            self.invited+=1
            if self.fail=='invite':raise TimeoutError('synthetic response loss')
            return {}
        self.created+=1
        assert kwargs['MessageAction']=='SUPPRESS'
        assert not any(a['Name']=='email_verified' for a in kwargs['UserAttributes'])
        if self.fail=='create':raise TimeoutError('synthetic response loss')
        return {'User':{'Attributes':[{'Name':'sub','Value':NEW_SUB}]}}
    def admin_add_user_to_group(self,**kwargs):
        if self.fail=='group':raise RuntimeError('synthetic group setup outage')


@pytest.fixture
def environment(monkeypatch):
    with mock_aws():
        db=boto3.resource('dynamodb',region_name='af-south-1')
        for name,key in [('scopes','subject'),('requests','request_id')]:
            db.create_table(TableName=name,KeySchema=[{'AttributeName':key,'KeyType':'HASH'}],AttributeDefinitions=[{'AttributeName':key,'AttributeType':'S'}],BillingMode='PAY_PER_REQUEST')
        scopes=db.Table('scopes')
        scopes.put_item(Item={'subject':cloud_users.DIRECTORY_KEY,'schema_version':1,'users':[{'username':'admin01','cognito_sub':ADMIN_SUB}]})
        scopes.put_item(Item={'subject':ADMIN_SUB,'username':'admin01','status':'ACTIVE','group':'Administrators','accounts':[ACCOUNT]})
        fake=Cognito()
        monkeypatch.setenv('COGNITO_USER_SCOPE_TABLE','scopes')
        monkeypatch.setenv('USER_PROVISIONING_TABLE','requests')
        monkeypatch.setenv('COGNITO_USER_POOL_ID','af-south-1_Test')
        monkeypatch.setattr(cloud_users,'clients',lambda:(fake,db))
        yield fake,scopes,db.Table('requests')


def body():
    return {'request_id':str(uuid.uuid4()),'username':'new-analyst','display_name':'New Analyst','email':'owned-test@example.test',
            'role':'Risk/Compliance Analyst','accounts':[ACCOUNT],'notes':'Approved analyst access'}


def test_create_configures_scope_directory_and_one_cognito_invitation(environment):
    fake,scopes,requests=environment
    payload=body();result=cloud_users.create_user(payload,ADMIN)
    assert result['state']=='INVITATION_REQUESTED'
    scope=scopes.get_item(Key={'subject':NEW_SUB})['Item']
    assert scope['status']=='ACTIVE' and scope['accounts']==[ACCOUNT] and scope['group']=='Analysts'
    directory=scopes.get_item(Key={'subject':cloud_users.DIRECTORY_KEY})['Item']
    assert directory['users'][-1]['cognito_sub']==NEW_SUB
    assert fake.created==fake.invited==1
    assert cloud_users.create_user(payload,ADMIN)==result
    assert fake.created==fake.invited==1
    receipt=requests.get_item(Key={'request_id':payload['request_id']})['Item']
    assert 'password' not in json.dumps(receipt).lower()


@pytest.mark.parametrize('role',['Risk/Compliance Analyst','Read-only/Auditor','Maintainer'])
def test_non_admin_cannot_provision_or_read_requests(environment,role):
    fake,_,_=environment
    caller=Principal('not-admin',role,(ACCOUNT,),auth_source='cognito')
    with pytest.raises(PermissionError):cloud_users.create_user(body(),caller)
    with pytest.raises(PermissionError):cloud_users.get_request(str(uuid.uuid4()),caller)
    assert fake.created==0


def test_scope_and_role_cannot_be_supplied_from_outside_admin_authority(environment):
    fake,_,_=environment
    payload=body();payload['accounts']=['20000000-0000-4000-8000-000000000099']
    with pytest.raises(PermissionError):cloud_users.create_user(payload,ADMIN)
    assert fake.created==0


def test_passwords_and_extra_authority_fields_are_rejected(environment):
    fake,_,_=environment
    payload=body();payload['password']='never-accepted'
    with pytest.raises(ValueError):cloud_users.create_user(payload,ADMIN)
    assert fake.created==0


def test_request_id_cannot_be_reused_for_another_role(environment):
    payload=body();cloud_users.create_user(payload,ADMIN)
    payload['role']='Admin'
    with pytest.raises(cloud_users.ProvisioningConflict):cloud_users.create_user(payload,ADMIN)


def test_disabled_administrator_and_stale_group_tokens_cannot_grant_access(environment):
    fake,scopes,_=environment
    fake.groups=['Auditors']
    with pytest.raises(PermissionError):cloud_users.create_user(body(),ADMIN)
    fake.groups=['Administrators']
    scopes.update_item(Key={'subject':ADMIN_SUB},UpdateExpression='SET #status=:disabled',ExpressionAttributeNames={'#status':'status'},ExpressionAttributeValues={':disabled':'DISABLED'})
    with pytest.raises(PermissionError):cloud_users.create_user(body(),ADMIN)
    assert fake.created==0


@pytest.mark.parametrize('failure,state',[('create','CREATION_UNKNOWN'),('group','SETUP_NEEDS_REVIEW'),('invite','INVITATION_UNKNOWN')])
def test_uncertain_or_partial_results_are_not_automatically_repeated(environment,failure,state):
    fake,scopes,_=environment;fake.fail=failure
    payload=body();result=cloud_users.create_user(payload,ADMIN)
    assert result['state']==state
    before=(fake.created,fake.invited)
    assert cloud_users.create_user(payload,ADMIN)['state']==state
    assert (fake.created,fake.invited)==before
    if failure!='invite':assert scopes.get_item(Key={'subject':NEW_SUB}).get('Item',{}).get('status')!='ACTIVE'


def test_second_request_cannot_create_the_same_username(environment):
    fake,_,_=environment
    cloud_users.create_user(body(),ADMIN)
    with pytest.raises(cloud_users.ProvisioningConflict):cloud_users.create_user(body(),ADMIN)
    assert fake.created==1 and fake.invited==1


def test_directory_append_preserves_concurrent_and_existing_entries(environment):
    _,scopes,_=environment
    cloud_users.append_directory(scopes,{'username':'other','cognito_sub':NEW_SUB})
    cloud_users.append_directory(scopes,{'username':'other','cognito_sub':NEW_SUB})
    users=scopes.get_item(Key={'subject':cloud_users.DIRECTORY_KEY})['Item']['users']
    assert [u['username'] for u in users]==['admin01','other']


def test_infrastructure_does_not_grant_database_or_iam_access():
    from infrastructure.user_administration import add_user_administration
    template=add_user_administration({'Parameters':{},'Resources':{'Deployment':{'Type':'AWS::ApiGateway::Deployment','DependsOn':['V1Get']},'Stage':{'Type':'AWS::ApiGateway::Stage','Properties':{'DeploymentId':{'Ref':'Deployment'}}}}})
    function=template['Resources']['UserAdminFunction']['Properties']
    assert 'VpcConfig' not in function
    assert function['ReservedConcurrentExecutions']['Fn::If'][2]==0
    policy=json.dumps(template['Resources']['UserAdminRole']['Properties']['Policies'])
    assert 'secretsmanager:' not in policy and 'rds' not in policy and 'iam:' not in policy
    for name in ('UserProvisioningGet','UserProvisioningPost'):
        assert template['Resources'][name]['Properties']['AuthorizationType']=='COGNITO_USER_POOLS'
        assert name in template['Resources']['DeploymentWorkforce20261022']['DependsOn']
    assert 'Deployment' not in template['Resources']
    assert template['Resources']['Stage']['Properties']['DeploymentId']=={'Ref':'DeploymentWorkforce20261022'}


def test_gateway_handler_requires_real_authorizer_context_and_admin_scope(environment,monkeypatch):
    import time
    from fintrust import cognito_auth
    for key,value in {'AWS_EXECUTION_ENV':'AWS_Lambda_python3.12','COGNITO_APP_CLIENT_ID':'test-client',
        'COGNITO_DOMAIN':'https://owned-test.auth.af-south-1.amazoncognito.com',
        'COGNITO_REDIRECT_URI':'https://owned-test.example/dev/','COGNITO_LOGOUT_URI':'https://owned-test.example/dev/'}.items():monkeypatch.setenv(key,value)
    claims={'iss':cognito_auth.configuration()['issuer'],'token_use':'access','client_id':'test-client',
            'sub':ADMIN_SUB,'username':'admin01','cognito:groups':'[Administrators]','scope':'openid',
            'iat':str(int(time.time())),'exp':str(int(time.time())+300)}
    event={'resource':'/v1/user-provisioning','httpMethod':'POST','body':json.dumps(body()),'requestContext':{'authorizer':{'claims':claims}}}
    assert cloud_users.lambda_handler({**event,'requestContext':{}},None)['statusCode']==403
    assert environment[0].created==0
    response=cloud_users.lambda_handler(event,None)
    assert response['statusCode']==201,json.loads(response['body'])
    assert json.loads(response['body'])['data']['state']=='INVITATION_REQUESTED'
    assert cognito_auth._gateway_claims.get() is None

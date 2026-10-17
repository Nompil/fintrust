import copy
from contextlib import nullcontext
import pytest
from fintrust.auth import Principal
from fintrust import cloud_directory,identity_registry,workflow_api

SUB='30000000-0000-4000-8000-000000000001'
ACCOUNT='20000000-0000-4000-8000-000000000001'

@pytest.fixture
def directory(monkeypatch):
    monkeypatch.setenv('AUTH_MODE','cognito')
    monkeypatch.setenv('COGNITO_USER_SCOPE_TABLE','scopes')
    monkeypatch.delenv('FINTRUST_AUTH_FILE',raising=False)
    docs={cloud_directory.KEY:{'schema_version':1,'users':[{'username':'analyst01','cognito_sub':SUB}]},
          SUB:{'username':'analyst01','status':'ACTIVE','group':'Analysts','accounts':[ACCOUNT]}}
    calls=[]
    class Table:
        def get_item(self,**kwargs):
            assert kwargs['ConsistentRead'] is True
            calls.append(kwargs['Key']['subject'])
            return {'Item':copy.deepcopy(docs.get(kwargs['Key']['subject'],{}))}
    class Resource:
        def Table(self,name):
            assert name=='scopes'
            return Table()
    import boto3
    monkeypatch.setattr(boto3,'resource',lambda *a,**k:Resource())
    return docs,calls

def test_cloud_metadata_uses_authoritative_scopes_without_local_credentials(directory):
    docs,calls=directory
    user=identity_registry.read_registry()['principals'][0]
    assert user['role']=='Risk/Compliance Analyst' and user['accounts']==[ACCOUNT]
    assert 'token_sha256' not in user and identity_registry.provisioned(user)
    assert calls==[cloud_directory.KEY,SUB]
    docs[SUB]['status']='DISABLED'
    assert identity_registry.read_registry()['principals']==[]

@pytest.mark.parametrize('change',[{'username':'other'},{'group':'Unknown'},{'status':'DISABLED'}])
def test_stale_directory_never_grants_authority(directory,change):
    docs,_=directory;docs[SUB].update(change)
    assert cloud_directory.read()['principals']==[]

def test_cloud_mutation_rechecks_role_scope_and_active_status(directory,monkeypatch):
    docs,_=directory
    principal=Principal('analyst01','Risk/Compliance Analyst',(ACCOUNT,),auth_source='cognito')
    monkeypatch.setattr(workflow_api,'_update_review',lambda *args:{'updated':True})
    assert workflow_api.update_review(1,{},principal)=={'updated':True}
    docs[SUB]['accounts']=[]
    with pytest.raises(PermissionError):workflow_api.update_review(1,{},principal)

def test_cloud_directory_rejects_duplicate_or_malformed_metadata(directory):
    docs,_=directory
    docs[cloud_directory.KEY]['users']*=2
    with pytest.raises(PermissionError):cloud_directory.read()
    docs[cloud_directory.KEY]['users']=[{'username':'analyst01','cognito_sub':'invalid'}]
    with pytest.raises(PermissionError):cloud_directory.read()

def test_cloud_administrator_can_read_active_scoped_workforce_but_local_editor_stays_blocked(directory):
    from fintrust import local_users
    docs,_=directory;docs[SUB]['group']='Administrators'
    principal=Principal('analyst01','Admin',(ACCOUNT,),auth_source='cognito')
    users=local_users.listing(principal)
    assert len(users)==1 and users[0]['role']=='Admin' and users[0]['credential_provisioned']
    with pytest.raises(PermissionError):local_users.change(principal,{})
    with pytest.raises(PermissionError):local_users.listing(Principal('analyst01','Risk/Compliance Analyst',(ACCOUNT,),auth_source='cognito'))

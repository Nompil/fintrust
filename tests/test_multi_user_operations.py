"""Named local users, single-owner reviews and immutable quarantine recovery.
Real isolated PostgreSQL; AWS transports are mocked by release_db.
"""
import hashlib,json,uuid
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from fintrust import api,auth,local_users,review_assignment,migrations,release_workflow as worker
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row,ACCOUNT

@pytest.fixture
def people(tmp_path,monkeypatch):
    roles={'admin01':'Admin','analyst01':'Risk/Compliance Analyst','analyst02':'Risk/Compliance Analyst','auditor01':'Read-only/Auditor','maintainer01':'Maintainer'}
    tokens={name:(str(i)*64) for i,name in enumerate(roles,1)}
    registry=tmp_path/'people.json'
    registry.write_text(json.dumps({'principals':[{'subject':n,'display_name':n.title(),'role':v,'status':'ACTIVE','accounts':[ACCOUNT],'created_at':datetime.now(timezone.utc).isoformat(),'token_sha256':hashlib.sha256(tokens[n].encode()).hexdigest()} for n,v in roles.items()]}))
    monkeypatch.setenv('FINTRUST_AUTH_FILE',str(registry));monkeypatch.setenv('FINTRUST_MODE','local')
    def headers(n):return {'Authorization':'Bearer '+tokens[n]}
    return api.app.test_client(),headers,registry

def event(db):
    run(feed([row(amount='200000.01',country='US')]))
    return db[3]('SELECT risk_event_id FROM risk_reviews')[0][0]
def assignment(client,h,e,who,target,version=1):
    return client.post(f'/v1/reviews/{e}/assignment',headers=h(who),json={'request_id':str(uuid.uuid4()),'expected_version':version,'assignee':target,'notes':'Controlled assignment'})
def decision(client,h,e,who,version=2):
    return client.post(f'/v1/reviews/{e}/transition',headers=h(who),json={'request_id':str(uuid.uuid4()),'expected_version':version,'status':'CLEARED','resolution_code':'VALID_ACTIVITY','notes':'Reviewed evidence'})

@pytest.mark.parametrize('role',['Risk/Compliance Analyst','Read-only/Auditor','Maintainer','Admin'])
def test_admin_creates_named_records_without_credentials(release_db,people,role):
    c,h,path=people;body={'username':'new-user','display_name':'New User','email':'user@example.test','role':role,'status':'ACTIVE','notes':'Approved onboarding'}
    response=c.post('/v1/administration/users',headers=h('admin01'),json=body)
    assert response.status_code==200,response.json
    data=response.json['data'];assert data['role']==role and not data['credential_provisioned'] and data['user_id']
    assert data['email']=='user@example.test' and data['last_sign_in_at'] is None
    audit=c.get('/v1/audit-events',headers=h('admin01')).json['data'];assert any(x['actor']=='admin01' and x['action']=='USER_CREATED' for x in audit)

@pytest.mark.parametrize('who',['analyst01','auditor01','maintainer01'])
def test_non_admin_user_governance_denied(release_db,people,who):
    c,h,_=people
    assert c.post('/v1/administration/users',headers=h(who),json={}).status_code==403

def test_disable_reactivate_and_role_change_preserve_identity_and_audit(release_db,people):
    c,h,path=people
    assert c.post('/v1/sign-in',headers=h('analyst02')).status_code==200
    before=c.get('/v1/session',headers=h('analyst02')).json['data'];assert before['last_sign_in_at']
    body={'username':'analyst02','display_name':'Second Analyst','role':'Risk/Compliance Analyst','status':'DISABLED','notes':'Controlled disable'}
    assert c.post('/v1/administration/users',headers=h('admin01'),json=body).status_code==200
    assert c.get('/v1/session',headers=h('analyst02')).status_code==401
    audit=c.get('/v1/audit-events',headers=h('admin01')).json['data'];assert any(x['action']=='USER_DISABLED' and x['actor']=='admin01' for x in audit)
    body.update(status='ACTIVE',role='Read-only/Auditor')
    assert c.post('/v1/administration/users',headers=h('admin01'),json=body).status_code==200
    after=c.get('/v1/session',headers=h('analyst02')).json['data'];assert after['user_id']==before['user_id'] and after['created_at']==before['created_at'] and after['role']=='Read-only/Auditor'
    assert c.post('/v1/reviews/1/assignment',headers=h('analyst02'),json={}).status_code==403

def test_private_enrollment_cannot_change_authority(release_db,people):
    import subprocess,sys
    from pathlib import Path
    backend=Path(__file__).resolve().parents[1]/'backend'
    command="import sys;sys.path.insert(0,"+repr(str(backend))+");import fintrust.local_users;assert 'fintrust.score' not in sys.modules"
    result=subprocess.run([sys.executable,'-c',command],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    c,h,path=people;body={'username':'analyst03','display_name':'Third','role':'Risk/Compliance Analyst','status':'ACTIVE','notes':'Named onboarding'}
    assert c.post('/v1/administration/users',headers=h('admin01'),json=body).status_code==200
    before=local_users.read_registry()['principals'][-1].copy()
    enrolled=local_users.provision_credential('analyst03','unique-private-synthetic-test-token-'+'x'*32)
    after=local_users.read_registry()['principals'][-1]
    assert enrolled['credential_provisioned'] and after['role']==before['role'] and after['accounts']==before['accounts'] and after['user_id']==before['user_id']
    assert 'unique-private' not in path.read_text()
    with pytest.raises(ValueError):local_users.provision_credential('analyst03','z'*64)
    with pytest.raises(PermissionError):local_users.provision_credential('missing','z'*64)

def test_claim_wrong_owner_complete_and_audit(release_db,people):
    c,h,_=people;e=event(release_db)
    assert assignment(c,h,e,'analyst01','analyst01').status_code==200
    assert assignment(c,h,e,'analyst02','analyst02',2).status_code==409
    assert decision(c,h,e,'analyst02').status_code==403
    assert decision(c,h,e,'admin01').status_code==403
    assert decision(c,h,e,'analyst01').status_code==200
    assert release_db[3]('SELECT actor_subject,reviewer_subject,after_status FROM risk_review_history ORDER BY version')==[('scoring-worker',None,'OPEN'),('analyst01','analyst01','UNDER_REVIEW'),('analyst01','analyst01','CLEARED')]

def test_authorized_reassign_stale_owner_and_release(release_db,people):
    c,h,_=people;e=event(release_db)
    assert assignment(c,h,e,'analyst01','analyst01').status_code==200
    assert assignment(c,h,e,'admin01','analyst02',2).status_code==200
    assert decision(c,h,e,'analyst01',3).status_code==403
    assert assignment(c,h,e,'admin01',None,3).status_code==200
    assert assignment(c,h,e,'analyst02','analyst02',4).status_code==200
    assert decision(c,h,e,'analyst02',5).status_code==200
    assert release_db[3]('SELECT count(*) FROM risk_review_history')==[(6,)]

@pytest.mark.parametrize('target',['admin01','auditor01','maintainer01','missing'])
def test_non_analyst_assignment_denied(release_db,people,target):
    c,h,_=people;e=event(release_db)
    assert assignment(c,h,e,'admin01',target).status_code==403

def test_disabled_assignee_rejected_existing_assignment_preserved(release_db,people):
    c,h,_=people;e=event(release_db)
    assert assignment(c,h,e,'admin01','analyst02').status_code==200
    assert c.post('/v1/administration/users',headers=h('admin01'),json={'username':'analyst02','display_name':'Second','role':'Risk/Compliance Analyst','status':'DISABLED','notes':'Disable assigned user'}).status_code==200
    rows=c.get('/v1/workflows/reviews?queue=open',headers=h('admin01')).json['data'];assert rows[0]['reviewer_subject']=='analyst02' and rows[0]['assignee_active'] is False
    assert assignment(c,h,e,'admin01',None,2).status_code==200
    assert assignment(c,h,e,'admin01','analyst02',3).status_code==403

def test_two_simultaneous_claims_have_one_owner(release_db,people):
    _,h,_=people;e=event(release_db)
    def claim(who):
        with api.app.test_client() as c:return assignment(c,h,e,who,who).status_code
    with ThreadPoolExecutor(2) as pool:codes=list(pool.map(claim,['analyst01','analyst02']))
    assert sorted(codes)==[200,409]
    assert release_db[3]('SELECT count(*) FROM risk_review_history')==[(2,)]

def test_queue_filters_age_and_optional_sla(release_db,people,monkeypatch):
    c,h,_=people;e=event(release_db)
    assert len(c.get('/v1/workflows/reviews?queue=unassigned',headers=h('analyst01')).json['data'])==1
    assert assignment(c,h,e,'analyst01','analyst01').status_code==200
    assert len(c.get('/v1/workflows/reviews?queue=mine',headers=h('analyst01')).json['data'])==1
    assert not c.get('/v1/workflows/reviews?queue=mine',headers=h('analyst02')).json['data']
    assert not c.get('/v1/workflows/reviews?queue=unassigned',headers=h('analyst02')).json['data']
    monkeypatch.delenv('FINTRUST_REVIEW_SLA_SECONDS',raising=False)
    assert c.get('/v1/workflows/reviews?queue=over_sla',headers=h('analyst01')).json['meta']['sla_configured'] is True
    monkeypatch.setenv('FINTRUST_REVIEW_SLA_ENABLED','false')
    assert c.get('/v1/workflows/reviews?queue=over_sla',headers=h('analyst01')).json['meta']['sla_configured'] is False
    monkeypatch.setenv('FINTRUST_REVIEW_SLA_ENABLED','true')
    now=datetime.now(timezone.utc);rows=[{'created_at':now-timedelta(seconds=90),'review_status':'OPEN','reviewer_subject':None,'risk':{'score':55,'risk_level':'High'}}]
    monkeypatch.setenv('FINTRUST_REVIEW_SLA_SECONDS','60');review_assignment.decorate(rows,now)
    assert rows[0]['age_seconds']==90 and rows[0]['over_sla']

@pytest.mark.parametrize('who',['admin01','auditor01','maintainer01'])
def test_non_analyst_correction_denied(release_db,people,who):
    c,h,_=people;run(feed([row(amount='bad')]))
    case=release_db[3]('SELECT quarantine_id::text FROM quarantine_cases')[0][0]
    assert c.post(f'/v1/quarantine/{case}/corrections',headers=h(who),json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Correction','candidate':row()}).status_code==403

@pytest.mark.parametrize('duplicate',[False,True])

def test_source_replacement_or_replay_cannot_overwrite_quarantine_history(release_db,people,duplicate):
    c,h,_=people;q=release_db[3];run(feed([row(amount='bad')]))
    case=q('SELECT quarantine_id::text FROM quarantine_cases')[0][0]
    original=q('SELECT safe_payload_key,safe_payload_version,reason_code,reason_detail FROM quarantine_cases WHERE quarantine_id=%s',(case,))
    path=f'/v1/quarantine/{case}'
    for candidate in (row(amount='0'),row()):
        assert c.post(path+'/corrections',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'action':'RESUBMIT','notes':'Source review','candidate':candidate}).status_code==403
    if duplicate:run(feed([row()],'raw/other-source.csv'))
    replacement=feed([row()],'raw/source-system-replacement.csv');run(replacement);run(replacement)
    data=c.get(path,headers=h('analyst01')).json['data']
    assert data['recovery_status']=='OPEN' and data['candidate']['amount']=='bad' and data['correction_history']==[]
    assert q('SELECT safe_payload_key,safe_payload_version,reason_code,reason_detail FROM quarantine_cases WHERE quarantine_id=%s',(case,))==original
    assert q('SELECT count(*) FROM transactions')==[(201,)]

def test_assignment_migration_reruns_and_detects_drift(release_db):
    conn,schema,_,q,_=release_db
    for version in (1,2,3,4):assert migrations.apply_local(conn,version,schema=schema)=='ALREADY_APPLIED'
    q('DROP INDEX risk_reviews_assignee_queue')
    with pytest.raises(migrations.SchemaDrift):migrations.apply_local(conn,4,schema=schema)

def test_assignment_idempotency_and_changed_request_denial(release_db,people):
    c,h,_=people;e=event(release_db)
    body={'request_id':str(uuid.uuid4()),'expected_version':1,'assignee':'analyst01','notes':'Idempotent claim'}
    path=f'/v1/reviews/{e}/assignment'
    assert c.post(path,headers=h('analyst01'),json=body).status_code==200
    again=c.post(path,headers=h('analyst01'),json=body);assert again.status_code==200 and again.json['data']['replayed']
    assert c.post(path,headers=h('analyst01'),json={**body,'notes':'Changed content'}).status_code==409
    assert release_db[3]('SELECT count(*) FROM risk_review_history')==[(2,)]

def test_assignment_scope_and_admin_not_decision_maker(release_db,people):
    c,h,p=people;e=event(release_db)
    registry=json.loads(p.read_text());registry['principals'][2]['accounts']=[str(uuid.uuid4())];p.write_text(json.dumps(registry))
    assert assignment(c,h,e,'admin01','analyst02').status_code==403
    assert assignment(c,h,e,'analyst02','analyst02').status_code==403
    assert decision(c,h,e,'admin01',1).status_code==403

def test_escalated_reassignment_preserves_prior_business_decision(release_db,people):
    c,h,_=people;e=event(release_db);q=release_db[3]
    assert assignment(c,h,e,'analyst01','analyst01').status_code==200
    response=c.post(f'/v1/reviews/{e}/transition',headers=h('analyst01'),json={'request_id':str(uuid.uuid4()),'expected_version':2,'status':'ESCALATED','resolution_code':'SPECIALIST_REVIEW','notes':'Specialist investigation needed'})
    assert response.status_code==200
    before=q('SELECT reviewed_by,reviewed_at,resolution_code FROM risk_reviews')
    assert assignment(c,h,e,'admin01','analyst02',3).status_code==200
    assert q('SELECT review_status,reviewer_subject FROM risk_reviews')==[('ESCALATED','analyst02')]
    assert q('SELECT reviewed_by,reviewed_at,resolution_code FROM risk_reviews')==before
    assert assignment(c,h,e,'admin01',None,4).status_code==409
    assert decision(c,h,e,'admin01',4).status_code==403
    history=c.get('/v1/audit-events',headers=h('admin01')).json['data']
    assert any(x['actor']=='admin01' and x['action']=='REVIEW_REASSIGNED' for x in history)

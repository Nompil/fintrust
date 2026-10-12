"""Real local SQL and browser business outcomes; no live AWS."""
import json,os,subprocess,threading
from pathlib import Path
import pytest
from werkzeug.serving import make_server
from fintrust import api,db
from tests.test_multi_user_operations import people,assignment,event
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row

def test_admin_reassigns_maintainer_role_without_inheriting_financial_authority(release_db,people):
    c,h,_=people
    before=c.get('/v1/session',headers=h('analyst02')).json['data']
    body={'username':'analyst02','display_name':'Second Analyst','role':'Maintainer','status':'ACTIVE','notes':'Controlled technical role reassignment'}
    response=c.post('/v1/administration/users',headers=h('admin01'),json=body)
    assert response.status_code==200,response.json
    after=c.get('/v1/session',headers=h('analyst02')).json['data']
    assert after['role']=='Maintainer' and after['user_id']==before['user_id']
    e=event(release_db)
    assert assignment(c,h,e,'analyst02','analyst02').status_code==403
    assert c.post('/v1/administration/users',headers=h('analyst02'),json=body).status_code==403
    audit=c.get('/v1/audit-events',headers=h('admin01')).json['data']
    assert any(x['action']=='USER_ROLE_CHANGED' and x['actor']=='admin01' and x['details']==body['notes'] for x in audit)
    s3=release_db[4]
    receipts=[json.loads(s3.get_object(Bucket='release1-safe',Key=o['Key'])['Body'].read()) for o in s3.list_objects_v2(Bucket='release1-safe',Prefix='quarantine/ui-events/')['Contents']]
    assert any(x['action']=='USER_ROLE_CHANGED' and x['before']['role']=='Risk/Compliance Analyst' and x['after']['role']=='Maintainer' for x in receipts)
    body.update(role='Risk/Compliance Analyst',notes='Restore reviewed Analyst role')
    assert c.post('/v1/administration/users',headers=h('admin01'),json=body).status_code==200
    assert c.get('/v1/session',headers=h('analyst02')).json['data']['user_id']==before['user_id']

@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'),reason='Explicit installed browser gate')
def test_three_review_outcomes_browser_database_and_audit(release_db,people,monkeypatch):
    results=run(feed([row(source_transaction_id=f'OUTCOME-{i}',amount=str(210000+i),country='US') for i in range(3)]))[:3]
    manifest=[{'event_id':r['risk_event_id'],'transaction_id':r['transaction_id'],'status':s} for r,s in zip(results,['CLEARED','CONFIRMED_RISK','ESCALATED'])]
    monkeypatch.setattr(db,'get_connection',release_db[2])
    root=Path(__file__).resolve().parents[1]
    out=Path(os.environ['FINTRUST_UI_COPY_EVIDENCE'])/'review-outcomes';out.mkdir(parents=True,exist_ok=True)
    (out/'inputs.json').write_text(json.dumps(manifest),encoding='utf8')
    server=make_server('127.0.0.1',0,api.app,threaded=True);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        result=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_scenario_outcomes.cjs'),f'http://127.0.0.1:{server.server_port}',str(out)],capture_output=True,text=True,timeout=180)
        assert result.returncode==0,result.stderr
        c,h,_=people;q=release_db[3]
        for case in manifest:
            assert q('SELECT review_status,reviewed_by FROM risk_reviews WHERE risk_event_id=%s',(case['event_id'],))==[(case['status'],'analyst01')]
            assert q('SELECT count(*) FROM transactions WHERE tx_id=%s',(case['transaction_id'],))==[(1,)]
            d=c.get(f"/v1/risk-events/{case['event_id']}",headers=h('analyst01')).json['data']
            assert d['review_status']==case['status'] and d['reviewed_at']
            assert len(d['review_history'])==3 and d['review_history'][-1]['actor_subject']=='analyst01'
            assert d['timeline_complete']
    finally:server.shutdown();t.join(timeout=10);server.server_close()

"""Presentation adapters plus actual API identity/scope; no AWS access."""
import json, os, subprocess, shutil
from pathlib import Path
import pytest
from tests.test_release1_end_to_end import release_db, authenticated_client, feed, run, row, ACCOUNT
from tests.test_frontend_workflows import local_receipts

ROOT=Path(__file__).resolve().parents[1]

def test_display_reference_and_safe_message_contract():
    node=os.environ.get("FINTRUST_NODE") or shutil.which("node")
    assert node and Path(node).is_file(), "Explicit Node prerequisite required for UX gate"
    program=r'''const d=require('./frontend/js/release1-display.js');const assert=require('node:assert/strict');
const id='20000000-0000-4000-8000-000000000005';assert.equal(d.reference('account_id',id),'ACC-0005');assert.equal(d.reference('risk_event_id',91),'RISK-0091');assert.equal(d.reference('risk_event_id','9007199254740993'),'RISK-9007199254740993');
for(const kind of ['tx_id','batch_id','risk_event_id']){const raw='aabbccdd-1234-4567-89ab-112233445566';const ref=d.reference(kind,raw);assert.equal(ref,d.reference(kind,raw.toUpperCase()));assert.notEqual(ref,raw);assert.equal(raw,'aabbccdd-1234-4567-89ab-112233445566');}
const ids=Array.from({length:10000},(_,i)=>'aabbccdd-1234-4567-89ab-'+i.toString(16).padStart(12,'0'));assert.equal(new Set(ids.map(x=>d.reference('tx_id',x))).size,10000);
assert.equal(d.value('risk_level',null),'Not assessed');assert.equal(d.value('source_transaction_id',null),'Not recorded');assert.equal(d.value('count',0),'0');
assert.equal(d.notice('File already processed','INFO','Ingestion Batches').title,'Duplicate file');
assert.equal(d.notice('File rejected. Bad CSV','ERROR','Rejected Uploads').title,'File rejected');
assert.equal(d.notice('Could not load','ERROR','Insights').title,'Insight unavailable');
assert.ok(!d.failure(404,'Insights').includes('Not Found'));assert.ok(d.failure(404,'Insights').includes('Refresh'));
console.log('Display references, UUID preservation, 10000 aliases, historical states and safe notification mappings passed.');'''
    result=subprocess.run([node,"-e",program],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize("role",["Risk/Compliance Analyst","Read-only/Auditor","Admin"])
def test_insights_current_route_real_values(role,release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client
    run(feed([row(),row(source_transaction_id="UX-RISK",amount="50000.01",country="US")]))
    r=client.get('/v1/release1/insights?days=all',headers=headers(role));assert r.status_code==200,r.json
    d=r.json['data'];assert all(isinstance(d[k],list) for k in ('activity','risk','rules','accounts','cross_border','quality','reviews','batch_outcomes'))
    count=release_db[3]('SELECT count(*) FROM transactions WHERE account_id=%s',(ACCOUNT,))[0][0]
    assert sum(x['count'] for x in d['activity'])==count
    assert sum(x['count'] for x in d['risk'])==2
    assert {x['label'] for x in d['accounts']}=={ACCOUNT}  # API identity remains UUID.
    events=client.get('/v1/workflows/risk-events',headers=headers(role)).json['data']
    stored=dict(release_db[3]('SELECT r.risk_event_id,p.result FROM risk_events r JOIN processed_transactions p USING(tx_id)'))
    assert events and all(e['risk']==stored.get(e['risk_event_id']) for e in events)


@pytest.mark.parametrize("role",["Risk/Compliance Analyst","Read-only/Auditor","Admin"])
def test_overview_zero_and_actual_technical_counts(role,release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client
    data=client.get('/v1/release1/overview',headers=headers(role)).json['data']
    assert data['technical_failures']==0 and data['open_reviews']==0 and data['duplicate_occurrences']==0
    run(feed([row(),row(),row(source_transaction_id='UX-BAD',amount='0')]))
    data=client.get('/v1/release1/overview',headers=headers(role)).json['data']
    assert data['new_ledger_entries']==1 and data['duplicate_occurrences']==1 and data['quarantined_rows']==1
    assert data['technical_failures']==release_db[3]('SELECT COALESCE(sum(failed_technical),0) FROM batch_reconciliation')[0][0]

def test_no_frontend_identity_switch_endpoint_and_current_assets(authenticated_client,local_receipts):
    client,headers=authenticated_client
    html=client.get('/release1').data.decode()
    assert 'release1-display.js?v=risk-investigation-1' in html
    assert 'operator-issued access token' in html
    assert not any('switch' in rule.rule or 'impersonat' in rule.rule for rule in client.application.url_map.iter_rules())
    for role in ('Risk/Compliance Analyst','Read-only/Auditor'):
        p=client.get('/v1/session',headers=headers(role)).json['data'];assert p['role']==role
    assert client.post('/v1/upload',headers=headers('Read-only/Auditor'),data={}).status_code==403

import uuid
from datetime import datetime, timedelta, timezone
from tests.test_release1_end_to_end import release_db, authenticated_client, feed, run, row, ACCOUNT


def ten_rows():
    start=datetime(2026,10,9,6,tzinfo=timezone.utc)
    rows=[row(source_transaction_id='LOW-'+str(i),merchant='Distinct synthetic merchant '+str(i),
              tx_date=(start+timedelta(minutes=30*i)).isoformat()) for i in range(8)]
    rows.append(row(source_transaction_id='HIGH-ONE',merchant='Synthetic imported equipment',amount='200000.01',country='US',tx_date='2026-10-09T09:45:00Z'))
    rows.append(row(source_transaction_id='SOURCE-REVIEW',amount='-75.00',tx_date='2026-10-09T09:50:00Z'))
    return rows


def test_ten_rows_reconcile_to_eight_low_one_high_one_quarantine(release_db,authenticated_client):
    client,headers=authenticated_client
    items=feed(ten_rows());run(items)
    batch=items[0]['batch']['batch_id']
    response=client.get('/v1/batches/'+batch,headers=headers('Risk/Compliance Analyst'))
    assert response.status_code==200,response.json
    summary=response.json['data']['batch']['row_summary']
    assert {k:summary[k] for k in ('rows_received','low','medium','high','quarantined','duplicates','technical_failures','pending','unassessed')}=={
        'rows_received':10,'low':8,'medium':0,'high':1,'quarantined':1,'duplicates':0,'technical_failures':0,'pending':0,'unassessed':0}
    assert summary['counts_consistent'] and summary['complete']
    assert 'not a finding of fraud' in summary['quarantine_note']
    q=release_db[3]
    assert q("SELECT result->>'score' FROM processed_transactions WHERE result->>'risk_level'='High'")==[('55',)]
    run(items)
    again=client.get('/v1/batches/'+batch,headers=headers('Risk/Compliance Analyst')).json['data']['batch']['row_summary']
    assert again==summary


def test_quarantine_report_preserves_original_issue_and_does_not_modify_ledger(release_db,authenticated_client):
    client,headers=authenticated_client
    items=feed(ten_rows());run(items);q=release_db[3]
    before=q('SELECT tx_id,amount FROM transactions ORDER BY tx_id')
    today=datetime.now(timezone(timedelta(hours=2))).date()
    response=client.get(f'/v1/reports/quarantine?date_timezone=Africa/Johannesburg&from={today}&to={today+timedelta(days=1)}',headers=headers('Risk/Compliance Analyst'))
    assert response.status_code==200,response.json
    assert len(response.json['data'])==1
    record=response.json['data'][0]
    assert record['reason_code']=='NEGATIVE_AMOUNT' and record['workflow_status']=='OPEN'
    assert 'safe_payload_key' not in record and 'safe_payload_version' not in record
    assert response.json['meta']['dataset']=='quarantine'
    assert 'not a fraud verdict' in response.json['meaning']
    assert q('SELECT tx_id,amount FROM transactions ORDER BY tx_id')==before
    identifier=record['quarantine_id']
    rejected=client.post('/v1/quarantine/'+identifier+'/corrections',headers=headers('Risk/Compliance Analyst'),json={
        'request_id':str(uuid.uuid4()),'action':'REJECT','notes':'Source system must confirm the sign and provide a replacement export','candidate':None})
    assert rejected.status_code==202,rejected.json
    assert q('SELECT tx_id,amount FROM transactions ORDER BY tx_id')==before
    report=client.get('/v1/reports/quarantine?status=REJECTED',headers=headers('Read-only/Auditor'))
    assert report.status_code==200 and len(report.json['data'])==1


def test_report_enforces_account_scope_and_date_boundaries(release_db,authenticated_client):
    client,headers=authenticated_client
    assert client.get('/v1/reports/quarantine?account_id=20000000-0000-4000-8000-000000000099',headers=headers('Risk/Compliance Analyst')).status_code==403
    assert client.get('/v1/reports/quarantine?from=2026-10-10&to=2026-10-09',headers=headers('Risk/Compliance Analyst')).status_code==400


def test_notes_are_append_only_and_cannot_supply_transaction_values(release_db,authenticated_client):
    client,headers=authenticated_client
    run(feed([row(amount='bad')]))
    q=release_db[3];case=str(q('SELECT quarantine_id FROM quarantine_cases')[0][0])
    original=q('SELECT safe_payload_key,safe_payload_version,reason_code,reason_detail FROM quarantine_cases')
    body={'request_id':str(uuid.uuid4()),'notes':'Source system must confirm the intended value; original evidence retained'}
    path=f'/v1/quarantine/{case}/notes'
    assert client.post(path,json=body,headers=headers('Read-only/Auditor')).status_code==403
    assert client.post(path,json={**body,'amount':'25.00'},headers=headers('Risk/Compliance Analyst')).status_code==400
    assert client.post(path,json=body,headers=headers('Risk/Compliance Analyst')).status_code==201
    replay=client.post(path,json=body,headers=headers('Risk/Compliance Analyst'))
    assert replay.status_code==201 and replay.json['data']['status']=='REPLAYED'
    assert client.post(path,json={**body,'notes':'Changed note'},headers=headers('Risk/Compliance Analyst')).status_code==409
    notes=client.get('/v1/quarantine/'+case,headers=headers('Read-only/Auditor')).json['data']['source_review_notes']['data']
    assert len(notes)==1 and notes[0]['notes']==body['notes']
    assert q('SELECT safe_payload_key,safe_payload_version,reason_code,reason_detail FROM quarantine_cases')==original
    assert q('SELECT count(*) FROM transactions')==[(200,)]
    assert q('SELECT count(*) FROM correction_outbox')==[(0,)]

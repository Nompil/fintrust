"""Uploaded source -> six work views -> investigation -> referral -> history.

Browser uses real authenticated HTTP and disposable PostgreSQL. AWS transports
are mocked and no original account, credential or financial row is changed.
"""
import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from fintrust import api, analyst_workflow
from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db, feed, file_bytes, run
from tests.test_release1_workflows import row, ACCOUNT


@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'), reason='Explicit installed Node/Playwright gate')
def test_uploaded_case_workspace_referral_and_ui_polish(release_db, people, monkeypatch):
    client, headers, _ = people
    s3, query = release_db[4], release_db[3]
    monkeypatch.setenv('FINTRUST_RELEASE1_UPLOAD', '1')
    monkeypatch.setenv('INPUT_BUCKET', 'synthetic-input')
    s3.create_bucket(Bucket='synthetic-input', CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
    s3.put_bucket_versioning(Bucket='synthetic-input', VersioningConfiguration={'Status':'Enabled'})
    run(feed([row(source_transaction_id='CASE-EXISTING-HIGH', amount='210003', tx_date='2026-10-09T07:00:00Z'),
              row(source_transaction_id='CASE-EXISTING-MEDIUM', amount='150000', tx_date='2026-10-09T07:10:00Z')], 'raw/prior-cases.csv'))
    fixed_clock = datetime.now(timezone.utc) + timedelta(hours=5)
    monkeypatch.setattr(analyst_workflow, 'now_utc', lambda: fixed_clock)
    out = Path(os.environ['FINTRUST_UI_COPY_EVIDENCE']) / 'case-workspace-journey'
    out.mkdir(parents=True, exist_ok=True)
    inputs = {
        'assigned_account':ACCOUNT,
        'high_filename':'fintrust_case_workspace_high_priority_source_2026_10_14.csv',
        'high_csv':file_bytes([row(source_transaction_id='CASE-UPLOADED-HIGH', amount='210001',
                                 country='US', merchant='Case investigation merchant', tx_date='2026-10-09T08:00:00Z')]).decode(),
        'invalid_filename':'invalid_rows_require_data_quality_work.csv',
        'invalid_csv':file_bytes([row(source_transaction_id='CASE-INVALID', amount='bad')]).decode(),
    }
    (out/'inputs.json').write_text(json.dumps(inputs), encoding='utf8')
    protected = query('SELECT row_to_json(t) FROM transactions t ORDER BY tx_id')
    server = make_server('127.0.0.1', 0, api.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run([os.environ['FINTRUST_NODE'], str(root/'tools/verify_case_workspace.cjs'),
            f'http://127.0.0.1:{server.server_port}', str(out)], capture_output=True, text=True, timeout=300)
        assert result.returncode == 0, result.stderr
        evidence = json.loads((out/'browser-result.json').read_text())
        assert evidence['status'] == 'PASSED'
        event, tx = query("SELECT r.risk_event_id,t.tx_id::text FROM transactions t JOIN risk_events r USING(tx_id) WHERE source_transaction_id='CASE-UPLOADED-HIGH'")[0]
        assert query('SELECT review_status,reviewer_subject,version FROM risk_reviews WHERE risk_event_id=%s', (event,)) == [('ESCALATED', 'analyst02', 5)]
        assert query('SELECT actor_subject,before_status,after_status FROM risk_review_history WHERE risk_event_id=%s ORDER BY version', (event,)) == [
            ('scoring-worker', None, 'OPEN'), ('analyst01', 'OPEN', 'UNDER_REVIEW'),
            ('analyst01', 'UNDER_REVIEW', 'UNDER_REVIEW'), ('analyst01', 'UNDER_REVIEW', 'ESCALATED'),
            ('admin01', 'ESCALATED', 'ESCALATED')]
        detail = client.get(f'/v1/risk-events/{event}', headers=headers('auditor01')).json['data']
        assert detail['referral_target'] == 'analyst:analyst02'
        assert detail['referral_requested_by'] == 'analyst01' and detail['referral_requested_at']
        assert detail['risk']['score'] == 55 and detail['risk']['rule_version'] == 'fintrust-r2-rules-2026-10-13'
        assert detail['sla_seconds'] == 7200 and detail['review_history'][-2]['actor_role'] == 'Risk/Compliance Analyst'
        assert query('SELECT row_to_json(t) FROM transactions t WHERE tx_id<>%s ORDER BY tx_id', (tx,)) == protected
        assert query("SELECT count(*) FROM transactions WHERE source_transaction_id='CASE-INVALID'") == [(0,)]
        assert query('SELECT count(*) FROM schema_migrations') == [(6,)]
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()

"""Evidence-scoped UX reads use real SQL; no frontend-only status fabrication."""
import io
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from fintrust import analyst_workflow

from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db, feed, file_bytes, run
from tests.test_release1_workflows import row, ACCOUNT


def test_quarantine_processing_run_filter_counts_and_clear_scope(release_db, people, monkeypatch):
    client, headers, _ = people
    monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD", "1")
    monkeypatch.setenv("INPUT_BUCKET", "synthetic-input")
    s3 = release_db[4]
    s3.create_bucket(Bucket="synthetic-input", CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
    s3.put_bucket_versioning(Bucket="synthetic-input", VersioningConfiguration={"Status": "Enabled"})
    run(feed([row(source_transaction_id="PREVIOUS-BAD", amount="bad")], "raw/old.csv"))
    filename = "current_processing_run_with_two_invalid_rows.csv"
    result = client.post("/v1/upload", headers=headers("analyst01"), data={"file":
        (io.BytesIO(file_bytes([row(source_transaction_id="CURRENT-A", amount="bad"),
                               row(source_transaction_id="CURRENT-B", amount="0")])), filename)})
    assert result.status_code == 200, result.json
    batch = result.json["data"]["batch_id"]
    filtered = client.get("/v1/workflows/quarantine?" + urlencode({"batch_id": batch, "limit": 1}), headers=headers("analyst01"))
    assert filtered.status_code == 200, filtered.json
    assert filtered.json["meta"]["total_count"] == 2
    assert filtered.json["meta"]["has_more"] is True
    assert len(filtered.json["data"]) == 1
    case = filtered.json["data"][0]
    assert case["batch_id"] == batch and case["filename"] == filename
    assert case["source_row"] in {2, 3} and case["reason_code"] == "INVALID_AMOUNT"
    all_rows = client.get("/v1/workflows/quarantine", headers=headers("analyst01")).json
    assert all_rows["meta"]["total_count"] == 3 and len(all_rows["data"]) == 3
    # Filtering changes the projection, not any recovery or ledger state.
    assert release_db[3]("SELECT count(*) FROM quarantine_corrections") == [(0,)]
    assert release_db[3]("SELECT count(*) FROM transactions") == [(200,)]


def test_pending_row_outcomes_reconcile_unprocessed_source_rows(release_db, people):
    client, headers, _ = people
    items = feed([row(source_transaction_id="FIRST"), row(source_transaction_id="SECOND"), row(source_transaction_id="THIRD")])
    run(items[:1])
    batch = items[0]["batch"]["batch_id"]
    # An internal feed has no original upload owner. Preserve its Admin-only
    # visibility while unprocessed rows have no proven account provenance.
    result = client.get(f"/v1/batches/{batch}?disposition=PENDING", headers=headers("admin01"))
    assert result.status_code == 200, result.json
    data = result.json["data"]
    assert [entry["source_row"] for entry in data["rows"]] == [3, 4]
    assert {entry["disposition"] for entry in data["rows"]} <= {"RECEIVED", "QUEUED"}
    state = data["batch"]
    assert state["rows_received"] == 3 and state["accepted"] == 1 and state["pending"] == 2
    assert state["display_status"] == "PROCESSING" and state["counts_consistent"]
    assert state.get("completed_at") is None


def test_insights_transaction_drilldown_preserves_all_evidence_filters(release_db, people):
    client, headers, _ = people
    run(feed([
        row(source_transaction_id="DRILL-LOW", amount="10", tx_date="2026-10-09T08:00:00Z"),
        row(source_transaction_id="DRILL-MEDIUM", amount="150000", tx_date="2026-10-09T08:10:00Z"),
        row(source_transaction_id="DRILL-HIGH", amount="150000", country="US", tx_date="2026-10-09T08:20:00Z"),
    ]))
    filters = {"account_id": ACCOUNT, "risk_level": "High", "scenario": "CROSS_BORDER",
               "review_status": "OPEN", "country": "US", "tx_type": "debit",
               "from": "2026-10-08T22:00:00Z", "to": "2026-10-09T22:00:00Z"}
    analytical = client.get("/v1/release1/insights?days=all&" + urlencode(filters), headers=headers("analyst01"))
    transactions = client.get("/v1/workflows/transactions?" + urlencode(filters), headers=headers("analyst01"))
    assert analytical.status_code == transactions.status_code == 200, (analytical.json, transactions.json)
    evidence = transactions.json["data"]
    assert [entry["source_transaction_id"] for entry in evidence] == ["DRILL-HIGH"]
    assert [entry["tx_id"] for entry in analytical.json["data"]["transactions"]] == [evidence[0]["tx_id"]]
    assert analytical.json["data"]["metrics"]["transactions"] == 1
    assert analytical.json["data"]["metrics"]["high_risk_rate"] == 100
    assert analytical.json["data"]["applied_filters"]["scenario"] == "CROSS_BORDER"
    for who in ("analyst01", "auditor01", "admin01"):
        denied = client.get("/v1/workflows/transactions?account_id=20000000-0000-4000-8000-000000000002", headers=headers(who))
        assert denied.status_code == 403
    assert release_db[3]("SELECT count(*) FROM risk_review_history") == [(2,)]


def test_sast_day_analytics_uses_same_time_window_as_transaction_evidence(release_db, people):
    client, headers, _ = people
    run(feed([
        row(source_transaction_id="SAST-IN", tx_date="2026-10-08T22:30:00Z"),
        row(source_transaction_id="SAST-OUT", tx_date="2026-10-08T21:30:00Z"),
    ]))
    # The explicit UTC instants correspond to midnight-to-midnight SAST, and
    # must be passed unchanged to both analytical and evidence endpoints.
    filters = {"from": "2026-10-08T22:00:00Z", "to": "2026-10-09T22:00:00Z", "risk_level": "Low"}
    insights = client.get("/v1/release1/insights?days=all&" + urlencode(filters), headers=headers("analyst01"))
    transactions = client.get("/v1/workflows/transactions?" + urlencode(filters), headers=headers("analyst01"))
    assert insights.status_code == transactions.status_code == 200, (insights.json, transactions.json)
    assert [t["source_transaction_id"] for t in transactions.json["data"]] == ["SAST-IN"]
    assert insights.json["data"]["metrics"]["transactions"] == 1
    assert insights.json["data"]["activity"] == [{"label": "2026-10-09", "count": 1}]


def test_queue_sla_filter_before_pagination_matches_overview_and_insights(release_db, people, monkeypatch):
    client, headers, _ = people
    results = run(feed([
        row(source_transaction_id="SLA-MEDIUM", amount="150000", tx_date="2026-10-09T08:00:00Z"),
        row(source_transaction_id="SLA-HIGH-A", amount="210005", tx_date="2026-10-09T08:10:00Z"),
        row(source_transaction_id="SLA-HIGH-B", amount="210006", tx_date="2026-10-09T08:20:00Z"),
    ]))
    original_history = release_db[3]("SELECT row_to_json(h) FROM risk_review_history h ORDER BY risk_event_id,version")
    observed = analyst_workflow.now_utc()
    monkeypatch.setattr(analyst_workflow, "now_utc", lambda: observed + timedelta(hours=3, minutes=30))
    soon = client.get('/v1/workflows/reviews?queue=due_soon&limit=1', headers=headers('analyst01')).json
    assert soon['meta']['total_count'] == 2 and soon['meta']['has_more']
    assert len(soon['data']) == 1 and soon['data'][0]['sla_state'] == 'DUE_SOON'
    overview = client.get('/v1/release1/overview', headers=headers('analyst01')).json['data']
    insights = client.get('/v1/release1/insights?days=all', headers=headers('analyst01')).json['data']['metrics']
    assert overview['reviews_due_soon'] == insights['reviews_due_soon'] == 2
    assert overview['reviews_over_sla'] == insights['reviews_over_sla'] == 0
    monkeypatch.setattr(analyst_workflow, "now_utc", lambda: observed + timedelta(hours=5))
    overdue = client.get('/v1/workflows/reviews?queue=over_sla&limit=1', headers=headers('analyst01')).json
    assert overdue['meta']['total_count'] == 2 and len(overdue['data']) == 1
    assert overdue['data'][0]['sla_state'] == 'OVERDUE'
    assert overdue['data'][0]['risk_event_id'] != results[0]['risk_event_id']
    overview = client.get('/v1/release1/overview', headers=headers('analyst01')).json['data']
    insights = client.get('/v1/release1/insights?days=all', headers=headers('analyst01')).json['data']['metrics']
    assert overview['reviews_over_sla'] == insights['reviews_over_sla'] == 2
    assert overview['reviews_due_soon'] == insights['reviews_due_soon'] == 0
    assert release_db[3]("SELECT row_to_json(h) FROM risk_review_history h ORDER BY risk_event_id,version") == original_history
    assert release_db[3]("SELECT review_status,count(*) FROM risk_reviews GROUP BY review_status") == [('OPEN', 3)]


def test_incomplete_modern_assessment_is_not_low_or_historical_in_aggregates(release_db, people):
    client, headers, _ = people
    result = run(feed([row(source_transaction_id="MISSING-ASSESSMENT-SCORE", amount="10")]))[0]
    tx = result['transaction_id']
    ledger = release_db[3]("SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s", (tx,))
    # Controlled corrupt-evidence fixture only: a recorded LOW label without
    # its score cannot count as an assessment or become a manufactured zero.
    release_db[3]("UPDATE processed_transactions SET result=result-'score' WHERE tx_id=%s", (tx,))
    response = client.get('/v1/transactions/' + tx, headers=headers('analyst01'))
    assert response.status_code == 200, response.json
    assert response.json['data']['assessment_state'] == 'NOT_RECORDED'
    assert response.json['data']['assessment_label'] == 'Not recorded'
    assert response.json['data']['review_state'] == 'NOT_RECORDED'
    assert response.json['data']['risk'].get('score') is None
    overview = client.get('/v1/release1/overview', headers=headers('analyst01')).json['data']
    insights = client.get('/v1/release1/insights?days=all', headers=headers('analyst01')).json['data']
    assert overview['risk_distribution'] == []
    assert insights['risk'] == [] and insights['metrics']['high_risk_rate'] is None
    assert insights['metrics']['historical_unscored'] == 40
    assert release_db[3]("SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s", (tx,)) == ledger


def test_escalated_owner_can_resume_without_giving_other_roles_decision_authority(release_db, people):
    client, headers, _ = people
    result = run(feed([row(source_transaction_id='RESUME-HIGH', amount='210000')]))[0]
    event = result['risk_event_id']
    ledger = release_db[3]("SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s", (result['transaction_id'],))
    assert client.post(f'/v1/reviews/{event}/assignment', headers=headers('analyst01'), json={
        'request_id': str(uuid.uuid4()), 'expected_version': 1, 'assignee': 'analyst01', 'notes': 'Claim evidence review'}).status_code == 200
    assert client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json={
        'request_id': str(uuid.uuid4()), 'expected_version': 2, 'status': 'ESCALATED',
        'resolution_code': 'SPECIALIST_REVIEW', 'notes': 'Specialist evidence review required'}).status_code == 200
    owner = client.get(f'/v1/risk-events/{event}', headers=headers('analyst01')).json['data']
    assert owner['allowed_actions']['resume'] is True and owner['allowed_actions']['decide'] is False
    assert owner['sla_seconds'] == 7200 and owner['escalated_at']
    for who in ('analyst02', 'admin01', 'auditor01'):
        read = client.get(f'/v1/risk-events/{event}', headers=headers(who))
        assert read.status_code == 200
        assert read.json['data']['allowed_actions']['resume'] is False
        denied = client.post(f'/v1/reviews/{event}/transition', headers=headers(who), json={
            'request_id': str(uuid.uuid4()), 'expected_version': 3, 'status': 'UNDER_REVIEW',
            'resolution_code': None, 'notes': 'Unauthorized resume attempt'})
        assert denied.status_code == 403
    resumed = client.post(f'/v1/reviews/{event}/transition', headers=headers('analyst01'), json={
        'request_id': str(uuid.uuid4()), 'expected_version': 3, 'status': 'UNDER_REVIEW',
        'resolution_code': None, 'notes': 'Specialist evidence received; resume investigation'})
    assert resumed.status_code == 200, resumed.json
    current = client.get(f'/v1/risk-events/{event}', headers=headers('analyst01')).json['data']
    assert current['reviewer_subject'] == 'analyst01' and current['allowed_actions']['note'] and current['allowed_actions']['decide']
    assert release_db[3]("SELECT actor_subject,before_status,after_status FROM risk_review_history WHERE risk_event_id=%s ORDER BY version", (event,)) == [
        ('scoring-worker', None, 'OPEN'), ('analyst01', 'OPEN', 'UNDER_REVIEW'),
        ('analyst01', 'UNDER_REVIEW', 'ESCALATED'), ('analyst01', 'ESCALATED', 'UNDER_REVIEW')]
    assert release_db[3]("SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s", (result['transaction_id'],)) == ledger

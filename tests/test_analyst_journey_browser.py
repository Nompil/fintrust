"""Controlled Analyst journeys: real HTTP, PostgreSQL and browser; mocked AWS.

The fixtures own their schema, synthetic identities and versioned source objects.
No preserved workspace or operator credential is used. Only the SLA read clock
advances; transaction, review and audit timestamps are never rewritten.
"""
import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from fintrust import api, analyst_workflow, release_workflow as worker
from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db, feed, file_bytes, run
from tests.test_release1_workflows import row, ACCOUNT


@pytest.mark.skipif(not os.getenv("FINTRUST_NODE"), reason="Explicit installed Node/Playwright gate")
def test_complete_analyst_journeys_browser_database_audit(release_db, people, monkeypatch):
    client, headers, _ = people
    query, s3 = release_db[3], release_db[4]
    monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD", "1")
    monkeypatch.setenv("INPUT_BUCKET", "synthetic-input")
    for variable in ("FINTRUST_REVIEW_SLA_SECONDS", "FINTRUST_REVIEW_MEDIUM_SLA_SECONDS",
                     "FINTRUST_REVIEW_HIGH_SLA_SECONDS", "FINTRUST_REVIEW_ESCALATED_SLA_SECONDS"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("FINTRUST_REVIEW_SLA_ENABLED", "true")
    s3.create_bucket(Bucket="synthetic-input", CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
    s3.put_bucket_versioning(Bucket="synthetic-input", VersioningConfiguration={"Status": "Enabled"})
    # An older visible quarantine row proves the upload deep link is a run filter.
    run(feed([row(source_transaction_id="JOURNEY-OLD-INVALID", amount="bad")], "raw/previous.csv"))
    sla_result = run(feed([row(source_transaction_id="JOURNEY-SLA", amount="210003",
                               merchant="Overdue merchant", tx_date="2026-10-09T07:00:00Z")], "raw/sla.csv"))[0]
    historical = query("SELECT tx_id::text FROM transactions WHERE account_id=%s AND raw_file='seed/week13-day2.csv' ORDER BY tx_id LIMIT 1", (ACCOUNT,))[0][0]
    frozen_now = datetime.now(timezone.utc) + timedelta(hours=5)

    monkeypatch.setattr(analyst_workflow, "now_utc", lambda: frozen_now)
    rows = [
        row(source_transaction_id="JOURNEY-LOW", amount="10", merchant="Normal shop", tx_date="2026-10-09T08:00:00Z"),
        row(source_transaction_id="JOURNEY-MEDIUM", amount="150000", merchant="Medium shop", tx_date="2026-10-09T08:10:00Z"),
        row(source_transaction_id="JOURNEY-HIGH", amount="210001", country="US", merchant="High shop", tx_date="2026-10-09T08:20:00Z"),
        row(source_transaction_id="JOURNEY-CORRECT", amount="bad", merchant="Correction shop", tx_date="2026-10-09T08:30:00Z"),
        row(source_transaction_id="JOURNEY-REJECT", amount="bad", merchant="Unrecoverable shop", tx_date="2026-10-09T08:40:00Z"),
    ]
    rows.append(dict(rows[0]))
    root = Path(__file__).resolve().parents[1]
    out = Path(os.environ["FINTRUST_UI_COPY_EVIDENCE"]) / "analyst-journeys"
    out.mkdir(parents=True, exist_ok=True)
    filename = "fintrust_analyst_workflow_acceptance_with_a_long_source_filename_and_versioned_risk_evidence_2026_10_13.csv"
    manifest = {"filename": filename, "csv": file_bytes(rows).decode(), "historical_tx": historical,
                "sla_event": sla_result["risk_event_id"], "sla_clock": frozen_now.isoformat()}
    (out / "inputs.json").write_text(json.dumps(manifest), encoding="utf-8")
    initial_historical = query("SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s", (historical,))
    stop, worker_errors = threading.Event(), []

    def drain():
        while not stop.wait(.1):
            try:
                worker.drain_corrections(limit=1)
            except Exception as error:
                worker_errors.append(type(error).__name__)
                return

    server = make_server("127.0.0.1", 0, api.app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    correction_thread = threading.Thread(target=drain, daemon=True)
    server_thread.start()
    correction_thread.start()
    try:
        result = subprocess.run(
            [os.environ["FINTRUST_NODE"], str(root / "tools/verify_analyst_journey.cjs"),
             f"http://127.0.0.1:{server.server_port}", str(out)],
            capture_output=True, text=True, timeout=300,
        )
        assert result.returncode == 0, result.stderr
        assert not worker_errors, worker_errors
        browser = json.loads((out / "browser-result.json").read_text())
        assert browser["status"] == "PASSED" and set(browser["scenarios"]) == set("ABCDEFG")
        expected = {"JOURNEY-LOW": (0, "Low", None), "JOURNEY-MEDIUM": (25, "Medium", "CLEARED"),
                    "JOURNEY-HIGH": (55, "High", "CONFIRMED_RISK")}
        actual = query("""SELECT t.source_transaction_id,(p.result->>'score')::int,p.result->>'risk_level',w.review_status
            FROM transactions t JOIN processed_transactions p USING(tx_id) LEFT JOIN risk_events r USING(tx_id)
            LEFT JOIN risk_reviews w USING(risk_event_id)
            WHERE t.source_transaction_id=ANY(%s)""", (list(expected),))
        assert {r[0]: r[1:] for r in actual} == expected
        assert query("SELECT count(*) FROM transactions WHERE source_transaction_id='JOURNEY-REJECT'") == [(0,)]
        assert query("SELECT workflow_status FROM quarantine_workflow WHERE quarantine_id=%s", (browser["rejected_case"],)) == [("REJECTED",)]
        assert query("SELECT correction_notes,submitted_by,action FROM quarantine_corrections WHERE quarantine_id=%s", (browser["rejected_case"],)) == [("Unrecoverable source evidence; reject without ledger entry", "analyst01", "REJECT")]
        assert query("SELECT reason_code FROM quarantine_cases WHERE quarantine_id=%s", (browser["corrected_case"],)) == [("INVALID_AMOUNT",)]
        assert query("SELECT submitted_by,action FROM quarantine_corrections WHERE quarantine_id=%s", (browser["corrected_case"],)) == []
        for source, outcome in (("JOURNEY-MEDIUM", "CLEARED"), ("JOURNEY-HIGH", "CONFIRMED_RISK")):
            event = query("SELECT risk_event_id FROM risk_events r JOIN transactions t USING(tx_id) WHERE source_transaction_id=%s", (source,))[0][0]
            history = query("SELECT actor_subject,before_status,after_status FROM risk_review_history WHERE risk_event_id=%s ORDER BY version", (event,))
            assert history == [("scoring-worker", None, "OPEN"), ("analyst01", "OPEN", "UNDER_REVIEW"),
                               ("analyst01", "UNDER_REVIEW", "UNDER_REVIEW"), ("analyst01", "UNDER_REVIEW", outcome)]
        assert query("SELECT row_to_json(t) FROM transactions t WHERE tx_id=%s", (historical,)) == initial_historical
        assert query("SELECT count(*) FROM processed_transactions WHERE tx_id=%s", (historical,)) == [(0,)]
        assert query("SELECT review_status,reviewer_subject FROM risk_reviews WHERE risk_event_id=%s", (sla_result["risk_event_id"],)) == [("OPEN", None)]
        run_state = client.get('/v1/batches/' + browser['batch_id'], headers=headers('analyst01')).json['data']['batch']
        assert tuple(run_state[k] for k in ("rows_received", "accepted", "quarantined", "duplicate", "failed_technical", "pending")) == (6, 3, 2, 1, 0, 0)
        # Source-review annotation does not create another processing run or ledger entry.
        assert run_state['counts_consistent']
        audit = client.get('/v1/audit-events?limit=100', headers=headers('auditor01')).json['data']
        assert {"REVIEW_CLAIMED", "REVIEW_NOTE_ADDED", "REVIEW_CLEARED", "REVIEW_CONFIRMED_RISK", "QUARANTINE_REJECT"} <= {e['action'] for e in audit}
    finally:
        stop.set()
        correction_thread.join(timeout=10)
        server.shutdown()
        server_thread.join(timeout=10)
        server.server_close()

> Supporting source retained for traceability. Use [Project Master](../docs/FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](../docs/FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

> Historical reference retained in place. Some implementation/status descriptions are superseded. Use the [current canonical guide](../docs/architecture.md) and [documentation inventory](../README.md) for current behavior and proposed disposition. No archive or deletion has occurred.

# Upcoming features and next steps

Current scope: Week 13 Days 1-3. Earlier planning records a 15 October 2026 submission target; the supplied brief specifies end of Week 14 and Week 16 presentations.

## Your next local exercises

Follow [the learning guide](learning_guide.md) in order: tests, database setup, connection check, database tests, CSV ingestion, replay, browser API calls and SQL inspection. Record your results in [daily progress](daily_log.md).

Database setup and connection checks succeeded on the persistent PostgreSQL server (200 transactions across five accounts). The current full suite passes 52 tests. The new dashboard and read-only smoke command are covered in the learning guide. Browser appearance, keyboard navigation and mobile interaction still need manual acceptance.

## Finish the current foundation

1. Extend the verified SQL examples to business cases: currency-specific totals, transfer direction, opening balances and real query plans. The six SQL files and seven PostgreSQL tests now pass locally; this is not RDS evidence.
2. Agree scoring weights and velocity semantics before connecting the scorer. Field names and validation now match the schema; scoring remains a prototype.
3. Implement connection reuse, customer-managed KMS/key policies, S3 access logging and the private-network service access plan. File-size and row-count bounds are implemented. Check SQL grants, VPC permissions, TLS and retention semantics.
4. Confirm the training account, region and budget; provision and test the foundation. Capture upload, valid rows, quarantine, duplicate replay, DLQ and alarm evidence.
5. Deploy the read API with authorization and verify health/400/404/pagination. Measure insights latency; the lesson's <50 ms target has not been demonstrated.

## Complete the later capstone

- Replace the direct load with the required FIFO/scoring path; persist risk records and daily insights; implement both queue failure paths.
- Add SES, monthly EventBridge reporting, monitoring dashboard, tracing and the final write API. Reconcile `/score` and nightly Step Functions requirements before implementation.
- Run the deployed end-to-end test, capture CI/AWS/API/billing evidence and complete the Well-Architected review.
- Verify private repository/facilitator access, then rehearse both technical and business presentations against demonstrated behavior.

Do not mark the final project complete because all module filenames exist. `alert.py` and `report.py` intentionally raise `NotImplementedError`; scoring remains a disconnected prototype.

## Working conventions

Daily local commits record verified milestones, as requested. Remote publishing remains a separate decision. Synthetic data and ignored credentials remain mandatory. Learning examples connect inputs, outputs and failures to each subsystem.

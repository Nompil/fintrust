> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Release 1 ingestion contract and dataset gate

**Bad file: reject the file. Bad row in a good file: quarantine the row. Good row: continue processing.**

Invalid files cannot safely satisfy the UTF-8 CSV contract and are rejected before any batch/row/financial work. Invalid business rows within an admitted CSV are quarantined individually, with reason, immutable safe evidence, file/batch/row provenance and correction workflow. A corrected row repeats validation, identity checks and scoring. Suspicious but valid transactions remain in the authoritative ledger with frozen scoring metadata; they never enter data quarantine merely because they are risky.

The two unchanged originals remain under tests/fixtures/e2e as evidence. Derived files, hashes, explicit test-only account/type/provenance/merchant mapping and independent expected totals are in tests/fixtures/e2e/release1. No upstream source integration is implied by these conventions.

Release 1 uses HIGH_AMOUNT >50000 and VERY_HIGH_AMOUNT >200000 in each transaction currency, with no FX conversion. Velocity is >5 accepted transactions in the closed five-minute event-time window including the current transaction. The sixth boundary transaction is tested at exactly 300 seconds; the next outside-window transaction is 300 seconds plus one microsecond later. The twelve four-minute-spaced original rows remain exploratory hour coverage; no hour rule is introduced.

Low valid records retain history, reporting and risk metadata. Medium and High enter OPEN review; only High is eligible for the current alert consumer. Similar distinct trusted references remain separate ledger records and can gain POSSIBLE_DUPLICATE_CHARGE. Exact identity/payload reuse is a benign duplicate occurrence. Material changes under the same trusted identity quarantine as DUPLICATE_IDENTITY_CONFLICT. Whole-file replay adds no financial entries, reviews or alerts.

Every admitted batch must reconcile received rows against accepted, quarantined, duplicate, technical-failed and pending dispositions. A batch with unresolved/mismatched counts cannot be COMPLETED. Upload notifications summarize the actual reconciliation, never raw parser, SQL or AWS details. Warnings and incomplete outcomes persist across navigation until acknowledged; acknowledgement does not resolve the underlying batch or remove its audit evidence.

Verification uses the actual HTTP upload adapter, real isolated loopback PostgreSQL, versioned mocked S3, mocked DynamoDB and mocked SES. Browser proof uses this actual backend, not hard-coded UI data. No AWS access or live migration occurs. Application/frontend changes require a new Linux Python 3.12 source-bound artifact; previous verified archives remain historical evidence.

## Current verification

Verified against source 12b0c94844b6ff1a6389beb99e1f87a51fedb598: 19 focused tests, 590 final Linux full-suite tests, zero failures/skips in CI, actual browser lifecycle passed. Exact artifact/source/download checks passed. Detailed results and hashes are in docs/EVIDENCE/12-e2e/release1-lifecycle/RESULT.md. No ingestion blocker remains; next is read-only AWS preflight. Do not infer live deployment from local or CI verification.

# FinTrust authoritative flow audit and implementation gap plan

Scope: actual source at the repository-hardening checkpoint; no AWS inventory or mutations in this task. Local verification is not live AWS integration. Existing AWS resource states are historical evidence, not freshly asserted here. Phase 2 adds durable lifecycle audit/API reads; frozen scoring, identity and review rules remain unchanged. Runtime module names and deployment handlers remain stable.

Release 1 actual flow: authenticated local upload -> mocked S3 -> direct consumer helper; cloud design: input S3 -> ingest file parsing -> FIFO candidate envelopes -> database-aware validation / quarantine OR accepted ledger+frozen scoring -> DynamoDB projection -> High-only alert delivery. Review work is created transactionally for Medium/High and does not wait for SES. Each scored transaction has a risk_events record, including Low. The requested diagram must not be treated as authority over these frozen semantics.

## Stage matrix

Source files below are under `backend/fintrust/` unless a different prefix is shown. UI is `frontend/release1.html` plus `frontend/js/release1.js` and `frontend/css/release1.css`. SQL remains under `sql/`. Status describes code/verification, not live completion.

| FLOW STAGE | SOURCE FILES / BACKEND | DATABASE | UI | TESTS | STATUS | GAP | PRIORITY |
|---|---|---|---|---|---|---|---|
| Transaction lifecycle | lifecycle.py, lifecycle_api.py, release_workflow.py | migration 003 append-only audit + existing domain histories | Backend timeline now shown in transaction and batch-row detail | test_transaction_lifecycle.py | Local implementation; focused/regression gates recorded below | No live rollout; automatic DLQ transport evidence deferred | P1 |
| CSV upload | api.py, operations.py, file_admission.py | ingestion_attempts; local upload receipts | Upload Transactions / Rejected Uploads | test_original_fixture_admission.py, test_frontend_workflows.py | Local verified; cloud upload handoff pending | Production intake authentication and S3 publication need deployment proof | P0 |
| Input / landing S3 | ingest.py, release_ingest.py, batches.py | Content/attempt identity in ingestion_batches | Upload result / source provenance | test_ingest.py, test_release1_end_to_end.py | Implemented; local AWS mocks | Bucket notification is a separate controlled wiring step | P0 |
| Ingest Lambda | ingest.py, release_ingest.py; infrastructure/ingest_deployment.py | No private SQL dependency in cloud ingest | Upload summary | test_stage5_ingest.py, test_release1_workflows.py | Implemented; deployment evidence historical | Current Release 1 package needs separate Linux/live gate after source move | P0 |
| Validation | validators.py, release_contract.py, release_workflow.py | Account existence checked against accounts | Quarantine reason/details | test_release1_workflows.py, test_release1_dataset_lifecycle.py | Implemented | Release 1 queues candidates BEFORE consumer DB-aware validation; target diagram must acknowledge this | P1 |
| Quarantine | quarantine.py, release_workflow.py | quarantine_cases; safe payload version in quarantine S3 | Quarantine detail / row corrections | test_release1_workflows.py, test_release1_end_to_end.py | Local verified | Safe S3 payload + SQL case are retryable separate effects; live access not proven here | P0 |
| Correction / revalidation | workflow_api.py, release_workflow.py | quarantine_corrections, correction_outbox | Correct / reject, RESUBMITTED pending | test_release1_end_to_end.py, test_release1_candidate.py | Local verified | Local drawer/form/outbox/worker completion and restart-safe evidence verified; live correction-worker scheduling remains gated; never direct ledger approval | P0 |
| SQS FIFO | release_ingest.py, score.py; infrastructure/messaging.py, processing.py | Immutable source envelope / outcome correlation | Batch evidence, Operations queue health | test_stage4_messaging.py, test_release1_workflows.py | Configured and mock-tested | Live S3 -> FIFO -> consumer mapping not demonstrated by direct local uploads | P0 |
| Scoring Lambda | score.py, rules.py, ledger.py | Per-account lock; frozen processed_transactions result | Risk / transaction detail | test_processing.py, test_score.py | Local verified | Private runtime IAM/TLS and event mapping remain separate deployment gates | P0 |
| LOW / MEDIUM / HIGH | rules.py, score.py, release_workflow.py | All accepted levels enter transactions; each scored result has risk_events; Medium/High get risk_reviews | Overview risk totals / Transactions / Review Queue | test_release1_workflows.py, test_presentation_ux_freeze.py | Local verified | Target diagram is simplified: risk_events are not exclusively High; risk does not reject valid financial data | P1 |
| Transaction identity / dedupe | jobs.py, ledger.py, batches.py | Unique source identity; fingerprint; immutable canonical tx_id | Duplicate occurrence / comparison evidence | test_release1_dataset_lifecycle.py, test_release1_workflows.py | Local verified | Do not replace source identity with row/file-centric assumptions; retain batch/row provenance | P1 |
| RDS transaction storage | db.py, ledger.py, migrations.py | sql/schema.sql -> migrations/001 -> migrations/002; history checksums | Transactions / Account History | test_release1_end_to_end.py, test_release1_workflows.py | Local verified; latest preflight evidence says empty live schema | Base bootstrap and incremental migrations require separate approval; no live SQL here | P0 |
| DynamoDB risk state | dynamo.py, release_workflow.py | Immutable TX# projection; projection_outbox retries in SQL | Stored risk and alert state | test_processing.py, test_processing.py | Mock verified | Live projection/stream mapping and pending-outbox worker proof required | P0 |
| Risk signals | rules.py, jobs.py | Frozen rule version and triggered_rules in processed_transactions | Risk detail / rule-frequency Insights | test_release1_workflows.py, test_release1_dataset_lifecycle.py | Local verified | Velocity remains >5 accepted transactions in 5 minutes; hourly exploration deferred | P3 |
| Risk events | score.py, workflow_api.py | risk_events created atomically with financial entry/result | Risk Events / related transaction | test_frontend_workflows.py, test_release1_end_to_end.py | Local verified | Risk event existence and investigation-worthy status must not be conflated | P2 |
| Alerts | alert_delivery.py, dynamo.py | DynamoDB claim + alerts receipt | Transaction delivery state / Operations | test_processing.py | Mock verified | SES timeout can produce UNKNOWN; do not blindly resend uncertain delivery | P0 |
| SES | alert_delivery.py; infrastructure/processing.py | External email; SQL receipt is supporting | Delivery state only; no inbox simulation | test_processing.py | Configured/mock only | Sender/recipient verification, sandbox/production approval and live delivery evidence pending | P0 |
| Review queue | release_workflow.py, workflow_api.py | risk_reviews durable at scoring commit | Review Queue | test_release1_end_to_end.py, test_role_workflow_ux.py | Local verified | Queue exists BEFORE successful SES; email failure must not hide review work | P1 |
| Review decisions | workflow_api.py, auth.py | risk_review_history; versioned transitions | OPEN -> UNDER_REVIEW -> CLEARED / CONFIRMED_RISK / ESCALATED | test_release1_candidate.py, test_release1_end_to_end.py | Local verified | No new decision rules or RBAC changes in this audit | P1 |
| Account history | query.py, workflow_api.py | Account/currency scoped transactions | Accounts -> Account History | test_frontend_workflows.py, browser gate | Local verified | Historical unscored rows remain Not assessed | P2 |
| API / query | api.py, query.py, workflow_api.py, auth.py | SQL authoritative; DynamoDB supporting state | All authorized workspaces | test_api.py, test_frontend_workflows.py | Local verified | Live authenticated API deployment remains a separate integration gate | P0 |
| Insights | visual_insights.py, frontend_workflows.py | Scoped SQL aggregates; no invented trend data | Eight charts with exact tables | test_presentation_ux_freeze.py, browser gate | Local verified | Charts lead transactions/risk/reviews; bounded history caveats retained | P2 |
| Reports / scheduled output | report.py, workflow_api.py; infrastructure/processing.py | SQL monthly movement -> S3 monthly JSON/CSV | Current authorized report-page exports | test_day4_day5.py, browser gate | Local/mock verified | Scheduled S3 outputs exist in backend but UI does not browse/download those objects | P1 |
| Audit | frontend_workflows.py, local_users.py, workflow_api.py | Review history, governance events, ingestion outcomes | Audit (Admin/Auditor) | test_role_workflow_ux.py, test_frontend_workflows.py | Local verified | Do not claim CloudTrail/enterprise identity integration from local audit records | P2 |
| Notifications | upload_notifications.py; frontend/js/release1.js | Upload/rejection history; in-memory UI notices | Notifications / persistent-until-ack banner | test_frontend_workflows.py, browser gate | Local verified | No durable cross-session notification inbox or email preference management | P3 |
| Failures / retry / DLQ | score.py, operations.py; infrastructure/sqs/replay_ingest_dlq.py | operations_requests, projection_outbox, correction_outbox | Maintainer Operations | test_release1_candidate.py, test_processing.py | Local/mock verified | Async failure destinations and FIFO DLQ are technical failures, not validation quarantine; live controlled redrive pending | P0 |
| Batch / reconciliation | batches.py, release_workflow.py, frontend_workflows.py | ingestion_records + batch_reconciliation; every outcome accounted for | Recent ingestion activity / Batch Detail | test_release1_dataset_lifecycle.py, browser gate | Local verified | Supporting provenance retained; rows pending/failed must not silently disappear | P1 |

## Backend capabilities without a complete UI path

- Scheduled monthly JSON/CSV in report S3: current Reports exports an authorized query page, not a generated report-object catalogue.
- Projection/correction outbox drain functions: Operations records bounded retry requests; actual worker completion is not an interactive synchronous UI guarantee.
- Immutable DynamoDB projection and alert-claim internals: selected delivery state is visible, but no raw operational-state editor is provided or appropriate.
- File-publication failure/control envelopes and cloud queue retries are richer than the local upload presentation; evidence must distinguish local direct processing from cloud transport.
- Notifications are session-scoped UI notices backed by selected ingestion history, not a durable enterprise notification service.

## Next local implementation phases (before AWS)

1. Transaction lifecycle: implement and verify authoritative processing/risk/review/delivery audit visibility (this Phase 2; see [contract](TRANSACTION_LIFECYCLE.md)).
2. Quarantine recovery: prove correction lineage, revalidation/dedupe and worker completion across failures.
3. Risk Event -> Alert -> Review Queue: prove High delivery and uncertain-send handling without blocking Medium/High reviews.
4. Run the complete local A/B/replay/error scenarios and verify reconciled API business outcomes.
5. Then prepare current Linux artifacts and controlled live bootstrap/integration approvals. Existing deployment gaps in the matrix remain separate from local domain completeness.

Preserve candidate-before-validation transport, all-level risk records and durable review-before-email. Do not change these semantics merely to match a picture. No AI or unrelated presentation features added.

## Phase 2 verification

62 focused lifecycle/domain/frozen-runner regression tests passed locally and 21 lifecycle tests passed on disposable PostgreSQL 16. Broader regression: 756 passed, 1 skipped, zero failures. The existing administrator-only role skip retains its separate prior PG16 proof. Existing domain/API focused run: 144 passed. SQL 001/002 and all 163 unrelated files preserved. See [sanitized evidence](../EVIDENCE/12-e2e/transaction-lifecycle/verification-summary.json).

## Analyst workbench UX correction — 13 October 2026

13 October 2026 | Analyst UX correction locally verified: 35 focused tests passed, full browser gate passed, final investigation browser passed. Regression: 823 full-suite passes / 1 expected administrator-only skip; one stale navigation harness failed, was corrected and its two checks passed on targeted rerun. Total: 824 checks verified. Quarantine correction stays in the investigation drawer through worker revalidation and accepted-transaction linkage. Risk review claim, note and Clear preserve queue context. Grouped navigation, Admin-only Users, batch rejected-upload history, business-first transaction details and ten backend-backed Insights charts are verified.

No schema or business-rule changes. Immutable identity/provenance, role/owner checks, independent alert delivery and accepted Low/Medium/High ledger semantics remain intact. Insights adds only parameterized read filters/aggregates; high-risk rate uses scored entries and quality counts disclose their separate bounded intake scope.

| Decision | Source | Why it applies | FinTrust use |
| --- | --- | --- | --- |
| Native tables with keyboard action buttons | https://www.w3.org/WAI/ARIA/apg/patterns/table/ | Dense investigation lists must remain accessible | Native table structure, visible focus, drawer focus restoration |
| Filtered SQL aggregates before detail pagination | https://www.postgresql.org/docs/16/sql-select.html | Counts must reflect authorized matching rows | Parameterized WHERE/GROUP BY, deterministic detail ordering |

Evidence: [verification summary](../EVIDENCE/12-e2e/analyst-ux-correction/verification-summary.json). Live AWS and current-source Linux gates remain separate.

## Workflow continuity and approved own-upload recovery - 13 October 2026

13 October 2026 | Workflow continuity and own-upload correction locally verified: 847 regression passed, 1 expected administrator-only skip, zero failures; final four-role browser passed; three investigation/missing-evidence/own-upload browser checks passed. Implementation: 209700a. AWS untouched; no schema change, credential reset or push.

Root cause of the reported quarantine 503: SQL pointers survived a local server restart, while the old in-memory mocked object versions did not. Exact original evidence is now persisted for future local uploads; missing historical originals return useful authorized metadata/audit and block corrections rather than fabricate values. The running port-5001 server was restarted with --reuse-auth, no reset or seed. Existing 204 ledger entries, four processed entries, two quarantine cases, zero corrections and three review-history rows were retained.

| Flow / requirement | Local proof | Boundary / outcome |
| --- | --- | --- |
| CSV admission and provenance | Real input/API/SQL four-role browser; A/B and exact A replay | First uploader recorded before worker processing; malformed files create receipts, not ledger rows. |
| Identity and duplicates | Existing identity, scenario and dataset suites retained | Canonical IDs remain immutable; same/cross-file rows and whole-file replay create no extra ledger entry; conflicts quarantine, similar genuine charges remain accepted. |
| Validation and scoring | Existing LOW/MEDIUM/HIGH and frozen rule tests pass | All valid risk levels remain in ledger. Velocity remains >5 accepted in the closed 5-minute window; hourly alternative deferred. |
| Quarantine recovery | Field correction -> outbox -> worker -> accepted link, timeline and actor | Original evidence required. Correction is pending until worker outcome; repeat validation and dedupe. |
| Own unknown-account rows | Nine authorization checks plus browser accepted-path proof | Original authenticated uploader only; assigned existing target account; no known-unassigned access or duplicate-file ownership transfer. |
| Risk investigation / review | Claim, note, Clear/Confirm/Escalate and multi-user checks retained | Atomic owner/version conflict; Admin governs access, Auditor reads, Maintainer handles technical recovery; no automated fraud verdict. |
| Alert and technical failure | Provider-outage, claim/idempotency and retry/outbox checks | Ledger remains available when delivery evidence is unavailable. SENT/ALERTED must be proven; no blind uncertain-send retry. |
| Batch reconciliation / timeline | Owned mixed-batch detail, per-row recorded timeline and scoped audit | Received = accepted + quarantined + duplicate + failed + pending; every outcome stays visible within authority. |
| Reports and account history | UTC inclusive-start/exclusive-end period + currency SQL checks; exports | Accepted ledger net movement per currency from zero, not current balance or FX. Export says current page; scheduled cloud delivery pending. |
| Local runtime continuity | Separate mock sessions restore exact versions and typed DynamoDB; server baseline retained | Ignored SQLite backing for local synthetic mocks only. Historic already-lost bytes are not fabricated. |
| Usability and evidence | 1100/1366/1920 layouts, drawer/form/recovered transaction screenshots | Single Details action, compact queue, human age, backend lifecycle, bounded technical detail, inline errors. |
| Cloud readiness | Local 20-scenario checkpoint remains verified; budgets preserved | Current-source Linux, live bootstrap/wiring/SES/DLQ/reports and live E2E remain approval gates. |

### Approved ownership authority

The authenticated local upload adapter records the first successful admission with a conditional If-None-Match write in the existing versioned quarantine audit bucket. Ownership is read from trusted server evidence, never CSV fields, request actor claims or UI labels. The receipt includes the source object version/checksum. A later duplicate uploader cannot replace it. Existing batches lacking ownership evidence are never retrospectively adopted by a replay. Unknown-account listing/detail, batch detail and row timeline share this authority; known unassigned accounts remain denied. Corrected account existence and assignment are checked before recording a new correction. Admin can oversee unknown cases and their correction audit but cannot correct financial data. Global Audit remains Admin/Auditor only; Analysts see their authorized recovery timeline.

This is a local admission/provenance extension, not a second transaction-state model, new account assignment or new schema. Cloud intake without trusted authenticated admission remains blocked for this exception. Missing original evidence still blocks new RESUBMIT and REJECT. Do not delete ignored build/local-runtime while preserving the database: it now backs synthetic original versions, receipts, projections and alert claims.

### Decisions supported by primary references

| Decision | Source | Why it applies | FinTrust use |
| --- | --- | --- | --- |
| Conditional first-admission ownership | https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html | Concurrent upload must not overwrite source authority | If-None-Match; first successful admission wins; replay cannot transfer ownership; local only |
| Retrieve exact evidence version | https://docs.aws.amazon.com/AmazonS3/latest/userguide/RetrievingObjectVersions.html | Audit pointer must refer to original bytes | Preserve VersionId; never replace absent pinned version with latest |
| Enforce authorization at service boundary | https://community.owasp.org/Access_Control | Hiding an action is insufficient authority | Active role, source owner, existing target assignment and direct endpoint denials |
| Preserve native tables / distinguish nonmodal detail | https://www.w3.org/WAI/ARIA/apg/patterns/table/ and https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ | Investigation should retain readable queue and keyboard access | Native tables; nonmodal aside; focus restoration; Escape/Close |
| Use database concurrency for decisions | https://www.postgresql.org/docs/16/applevel-consistency.html | Two users must not independently own one review | Existing row locks/version checks; no new review state model |

Evidence: docs/EVIDENCE/12-e2e/workflow-continuity/verification-summary.json and local-server-restart.json, regression XML and authenticated browser screenshots. Final code and evidence are local commits only. These results close the observed local workflow defects; they are not a claim of 100% production/cloud completion.

Final navigation/copy polish: `0056a59`. Recovered transactions activate Transactions and show accepted-ledger purpose; LOW entries use Risk Assessment. Three targeted browser checks passed; an interrupted investigation check stalled on a local database request and was rerun alone: 1 passed in 42.67 seconds. Earlier clean full-suite result remains 847 passed / 1 expected skip, with separate final UI checks, not a second full-suite claim.

## 13 October 2026 - Risk Model V2 and explainability

Risk Model V2 and explainable UX VERIFIED: 903 PASSED | 0 FAILED | 1 EXPECTED SKIP (904 collected, +56 checks versus baseline). Final focused model/CSV/browser pass: 75; eight previously affected checks passed after explicit V2 oracle updates. Seven in-suite browser gates plus the separate four-role CSV/report gate passed. Preserved financial/audit data and credentials are unchanged. No historical rescoring, AWS contact, push or Linux run.

Model: one amount band (0/15/25/40), velocity +25, cross-border +15, possible duplicate +20; cap 100. LOW 0-19, MEDIUM 20-39, HIGH 40-100. New version `fintrust-r2-rules-2026-10-13`; original currency, unchanged five-minute velocity, no FX.

New JSON snapshots preserve component measurements, configured/observed windows, related references, timing proximity, evaluation time and version. Replay returns the frozen result. Historical V1 results retain their own score/classification and missing evidence is not reconstructed. Percentage is configured priority, not probability of fraud.

Additive migration 006 changes only the existing review guard to handle frozen V1 and V2 classifications. Apply the reviewed guard before enabling V2 workers in any environment. Existing migrations and financial/audit rows are unchanged. No second state/score table, behavioural scoring, AI or production-capacity claim is introduced. Future dimensions and scalability hardening are labelled PLANNED in Master, Progress and the existing presentation PDF.

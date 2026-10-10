# Release 1 gap register

Continues checkpoint 3a5d979. Classification records the original release impact; status records actual progress. Local verification does not prove AWS deployment. Focused push/CI is approved; AWS actions remain prohibited. Actual CSV A/B import alone is pending external input.

| ID | Finding | Classification | Current status | Evidence |
|---|---|---|---|---|
| R1-01 | Strict CSV schema, complete parsing and bounded size | BLOCKER | FIXED_LOCAL | tests/test_release1_end_to_end.py::test_csv_shape_quotes_bom_reorder_and_late_malformed |
| R1-02 | Durable first receipt clock | RELEASE_1 | FIXED_LOCAL | tests/test_idempotency.py; first-receipt regression |
| R1-03 | Trusted versioned input bucket/prefix/event | BLOCKER | FIXED_LOCAL | strict intake event-boundary tests |
| R1-04 | Row outcome and financial commit atomicity | BLOCKER | FIXED_LOCAL | mixed, concurrent and projection-failure integration tests |
| R1-05 | Unambiguous batch state and disjoint accounting | BLOCKER | FIXED_LOCAL | test_sql_reconciliation_and_terminal_immutability; mixed end-to-end test |
| R1-06 | Multi-error deterministic strict validation wired to worker | RELEASE_1 | FIXED_LOCAL | validation scenarios and worker business-rejection tests |
| R1-07 | Inactive/closed account admission | RELEASE_1 | FIXED_LOCAL | test_unknown_inactive_and_invalid_rows_are_quarantine_not_dlq |
| R1-08 | Identity-content conflict is explicit | RELEASE_1 | FIXED_LOCAL | mixed-file and changed-occurrence tests |
| R1-09 | Concurrent financial identity protection | ALREADY_COVERED | VERIFIED_EXISTING | tests/data_quality/test_processing.py::test_concurrent_duplicates_produce_one_ledger_event |
| R1-10 | Genuine similar charge remains a financial entry | ALREADY_COVERED | VERIFIED_EXISTING | tests/test_release1_workflows.py::test_duplicate_charge_closed_window_edges |
| R1-11 | Five-minute velocity and risk boundaries | ALREADY_COVERED | VERIFIED_EXISTING | test_velocity_count_edges; velocity time-edge integration tests |
| R1-12 | Hourly velocity exploration | DEFERRED | DEFERRED | exploratory 10/11/12 spread over hour tests |
| R1-13 | Explainable frozen rule version | RELEASE_1 | FIXED_LOCAL | existing frozen replay and rule tests |
| R1-14 | Review API with identity/version/history | RELEASE_1 | FIXED_LOCAL | test_review_api_stale_idempotent_audit_and_ledger_immutable |
| R1-15 | Quarantine correction and reprocessing | RELEASE_1 | FIXED_LOCAL | test_correction_api_revalidates_deduplicates_and_preserves_original |
| R1-16 | Request idempotency/content mismatch | RELEASE_1 | FIXED_LOCAL | review and correction API replay/conflict tests |
| R1-17 | Business quarantine versus technical DLQ | RELEASE_1 | FIXED_LOCAL | unknown/inactive/future tests; FIFO partial failure tests |
| R1-18 | FIFO partial retry and DLQ limit | ALREADY_COVERED | VERIFIED_EXISTING | tests/test_processing.py::test_fifo_exhausted_retries_move_to_dlq |
| R1-19 | Controlled operator redrive | RELEASE_1 | DOCUMENTED_LOCAL_GATE | FIFO replay/poison tests; live redrive deferred until AWS approval |
| R1-20 | RDS-authoritative projection recovery | RELEASE_1 | FIXED_LOCAL | test_partial_batch_and_dynamo_failure_after_sql_retries |
| R1-21 | Conservative logical alert delivery | ALREADY_COVERED | VERIFIED_EXISTING | tests/data_quality/test_processing.py::test_uncertain_ses_response_blocks_duplicate_delivery; stream delivery tests |
| R1-22 | Backend authentication and account/role authorization | BLOCKER | FIXED_LOCAL | authentication and object-scope API tests |
| R1-23 | Mass assignment, filters, pagination and safe errors | RELEASE_1 | FIXED_LOCAL | review mass-assignment/filter/page tests; existing API error tests |
| R1-24 | Minimal analyst frontend and scoped reporting | RELEASE_1 | VERIFIED_LOCAL_BROWSER | HTTP contract tests; browser verification still required |
| R1-25 | Ordered migration tracking and drift detection | RELEASE_1 | FIXED_LOCAL | test_migration_order_rerun_and_catalog_drift; fresh/legacy/order/rollback tests |
| R1-26 | PostgreSQL 16 and least-privilege service-role gate | BLOCKER | BLOCKED_EXTERNAL_VERIFICATION | New migration/privilege tests must pass on PG16; prior runner CI is not evidence for changed 002 |
| R1-27 | Lambda connection/concurrency safety | ALREADY_COVERED | VERIFIED_EXISTING | database failure/retry tests; infrastructure concurrency tests |
| R1-28 | Safe S3 evidence and native dependency release gate | ALREADY_COVERED | VERIFIED_EXISTING | existing hardened-release and migration package CI evidence; new-source package not yet verified |
| R1-29 | Operational metrics, backlog visibility and runbooks | RELEASE_1 | FIXED_LOCAL | zero-row and projection-backlog tests |
| R1-30 | Governance and retention truthfulness | RELEASE_1 | DOCUMENTED_LOCAL_GATE | existing governance docs and quarantine tests; cloud retention not re-audited |
| R1-31 | Runtime/schema rollout ordering | BLOCKER | DOCUMENTED_LOCAL_GATE | compatibility test and protected 001/artifact checksum tests |
| R1-32 | Actual external CSV A/B acceptance evidence | BLOCKER | PENDING_EXTERNAL_FIXTURE_ONLY | Actual A/B files are absent; generated scenario tests do not prove their contents |
| R1-33 | Cloud federation/Cognito and production identity management | DEFERRED | DEFERRED | Local authentication tested; cloud federation future scope |
| R1-34 | Multi-region/HA/autoscaling and RDS Proxy | DEFERRED | DEFERRED | Existing architecture and stage cost plan |
| R1-35 | Refund/reversal/chargeback ledger semantics | DEFERRED | DEFERRED | reference validation scenarios |
| R1-36 | FX aggregation and actual balance accounting | DEFERRED | DEFERRED | existing report tests and scoped report API tests |
| R1-37 | Automatic ambiguous SES reclamation | DEFERRED | DEFERRED | uncertain SES tests |
| R1-38 | New-source Linux runtime package verification | BLOCKER | BLOCKED_EXTERNAL_VERIFICATION | New exact-source Linux CPython3.12 import/source-binding gate |

Original classifications: {'BLOCKER': 9, 'RELEASE_1': 16, 'ALREADY_COVERED': 7, 'DEFERRED': 6}

# Release 1 failure injection and evidence

All current tests use loopback dedicated PostgreSQL and mocked AWS transport.
No live fault injection or redrive is approved. A technical retry can remain
pending; that is different from pretending a financial row never existed.

| Injected failure | Required behavior | Retry/terminal interpretation | Evidence |
|---|---|---|---|
| RDS unavailable before ledger | No financial/risk commit, SQS invocation fails | Pending row; retry after DB recovery; DLQ after maxReceiveCount5 | test_rds_scoring_and_kms_failure_never_acknowledged; FIFO failures |
| Scoring configuration/exception | Atomic transaction rolls back | Pending technical failure; fix config, same identity replay | frozen-config test; existing scoring rollback tests |
| Dynamo fails after RDS | Ledger/outcome/review committed, projection outbox PENDING | Reuse frozen result, publish projection, then mark COMPLETED | test_partial_batch_and_dynamo_failure_after_sql_retries |
| Projection exists but mismatches SQL | Do not overwrite or rescore | Fail closed; inspect authoritative SQL result; operator incident | existing dynamo immutable projection tests |
| SQS send batch partially succeeds | No complete marker; invocation failure | Immutable first receipt and dedup IDs; safely repeat whole publication | test_publication_partial_failure_and_whole_file_attempt_audit |
| FIFO message poison/missing envelope identity | Stop at first failure; report remaining message IDs | Technical retry/DLQ; no business quarantine without trustworthy provenance | tests/test_processing.py FIFO poison/partial failure |
| Business-invalid amount/account/time | Versioned safe evidence and QUARANTINED outcome; successful ACK | No DLQ merely for invalid business data; later correction fully revalidates | test_unknown_inactive_and_invalid_rows_are_quarantine_not_dlq |
| DLQ max retry / bounded redrive | Native maxReceiveCount5; operator fixes cause first | Explicit <=20 messages, <=3 incident redrive cycles; no automatic infinite loops | test_fifo_exhausted_retries_move_to_dlq; operations runbook (live redrive not executed) |
| SES definite rejection | Financial ledger remains; logical alert FAILED | Controlled retry is permitted; no duplicate logical alert | existing SES rejection/replay tests |
| SES timeout or success followed by claim-write failure | Financial commit preserved, UNKNOWN/SENDING protected | No automatic resend; reconcile provider first | uncertain SES and SQL/Dynamo finish failure tests |
| KMS/S3 evidence denial | No false terminal quarantine ACK | Pending/retry; no new financial acceptance | test_rds_scoring_and_kms_failure_never_acknowledged |
| Correction projection failure | Correction outbox stays PENDING; original quarantine immutable | Retry same candidate/occurrence; no second financial entry | test_correction_failure_outbox_retries_and_no_sensitive_fields |
| Partially processed batch | Each occurrence counted once; pending remains visible | COMPLETED only after business partition resolves; side-effect backlog separate | mixed/partial reconciliation tests |
| Concurrent duplicate | Account lock and unique identity; one financial/risk result | Frozen replay; additional occurrence is DUPLICATE | concurrent worker and original ledger concurrency tests |
| Stale/concurrent analyst review | Expected version conflict, immutable history | HTTP409; refresh, do not overwrite | review API stale/idempotent history test |
| Reused request ID with altered values/actor/object | No second mutation | HTTP409; repeat must exactly match stored digest | review/correction request replay tests |
| Migration002 collision/partial schema | Whole migration transaction rolls back | No version002 recorded; preserve existing rows/evidence | migration order/partial/conflict rollback test |
| Post-migration catalog/source drift | Ordered harness refuses rerun | Investigate/forward fix; never override recorded checksum | migration catalogue drift test |

Evidence must include safe message/request/batch/row IDs, outcome counts, immutable
source version and error type. No credentials, browser tokens, raw PII or secret
values are preserved. Local failures and corrected reruns remain in ignored build
scratch; the tracked report records both, without claiming a failure was skipped.
PostgreSQL16 privileged execution and exact new-source Linux import gates remain
pending separately approved CI. Earlier migration-runner CI is not proof for002.

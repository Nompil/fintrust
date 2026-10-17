# Controlled integrated cloud demonstration

This proposal uses the existing shared Lambda quota (last observed as 10), with
no positive reserved slots. All defaults remain disabled. Enabling functions
releases four application functions into the shared pool; this is not a hard
per-function concurrency cap. The FIFO event source is bounded to two concurrent
consumers and one message per batch. Reporting remains independently disabled.

The additional one-minute EventBridge rule drains at most five authorized SQL
corrections and five pending projections per invocation. The existing worker
keeps financial identity/idempotency checks. Its exact rule permission, retries
and failure queue are explicit. This avoids a new paid queue/VPC endpoint.

The API receives a separately gated asynchronous upload path: authenticate with
Cognito, check known account scope before storage, store a versioned source file
and immutable admission record, then let S3 → ingest → FIFO → scoring perform the
financial work. Queued uploads do not claim to be accepted ledger rows. Raw S3
notification must be connected last, after downstream service checks pass.

Workforce display and review authority use read-only records in the existing
scope table. A bounded directory contains Cognito usernames/subjects; each entry
is rechecked against the active per-user scope record. No local password/token
registry is copied into Lambda, and the API has no directory write permission.
Cognito administration stays an operator action; local user-governance endpoints
remain local-only. Do not advertise a cloud user editor as implemented.

`runtime-inventory.json` is a read-only snapshot, not validation of live execution.
It exposed missing runtime permissions for first alert claims, cloud upload
receipts, and ingest receipt reads. Supplements must preserve existing policies,
pass policy validation, and be read back before controlled activation. The S3
gateway also needs prefix-scoped listing; no new paid interface endpoint is needed.

Gate activation on database initialization/cleanup, the final immutable package,
runtime permission checks, Cognito enrollment/scopes and bounded service tests.
Do not upgrade Basic Support or depend on the pending quota case to claim success.
Costs are usage-dependent; the budget notification threshold is not a spending cap.
After the presentation, disable notifications, consumers, schedules and function
execution in that order and stop RDS where supported, preserving all data.

# Release 1 local workflows, recovery and release gates

This milestone is LOCAL implementation and synthetic-data verification only.
No AWS calls, live RDS changes, new artifact uploads, pushes or trigger/concurrency
activation are authorized. Existing deployed Stage 1?5 state was not re-audited.
AWS Integration remains In Progress. The historical verified ZIP is unchanged;
it is not a deployable representation of the new source.

## Normal feed and compatibility

New intake is enabled by `FINTRUST_RELEASE1=1`, requires `INPUT_BUCKET`,
`INPUT_PREFIX` (default raw/), a FIFO `TRANSACTION_QUEUE_URL` and versioned
`QUARANTINE_BUCKET`. It accepts completed ObjectCreated CSV versions only.
No source credentials are put into environment variables or messages.
The normal feed requires upstream namespace/reference, timezone-bearing ISO time,
explicit currency/country and the frozen rule configuration. Existing v1/v2 job
contracts and the local teaching loader remain legacy compatibility paths;
they do not claim strict Release 1 semantics. The authenticated legacy upload
route requires Admin and `FINTRUST_LOCAL_DEMO=1`; it is not a cloud activation path.
Workers must be deployed/migrated before version3 messages can be published.

Outside-VPC intake fully parses a <=1 MiB, <=5000-row CSV before queue publication.
Each row <=32 KiB is a version3 envelope; business-invalid rows still reach the
private worker and are acknowledged only after safe, versioned evidence and SQL
outcome commit. Malformed envelopes are technical poison and retry/DLQ.
SQS batch partial success is a failure; retries use immutable receipt metadata.
Source object versions, attempts and record ordinals (not physical text lines)
remain traceable. UTF8 BOM and quoted commas work; header case/drift/duplicates or
unsupported delimiters fail the whole file. Blank physical lines are not CSV
records. The parser never attempts to reinterpret shifted columns.

SQL row outcomes, risk event, frozen result, review and projection outbox commit
together. Failed Dynamo publication leaves a PENDING projection outbox; use
`release_workflow.rebuild_projection(tx_id)` under the worker's controlled local
context to republish the immutable result. A mismatch in an existing projection
fails closed and requires incident review, never silent overwrite.
A missing frozen result for an existing ledger identity is an incident and is
quarantined, never rescored automatically. Accounts must be active/monitoring for
new admissions. Benign frozen replays remain valid after an account closes.
Late arrival uses history known at admission; prior decisions never change.

## Analyst API and correction

`/release1` is the minimal local workspace. Backend authentication always applies
to data/mutation endpoints; public static pages are not authenticated data.
The local auth registry named by `FINTRUST_AUTH_FILE` is an operator-controlled
ignored JSON file with principals: subject, role, assigned account UUIDs and
`token_sha256`. Use independently generated >=256-bit opaque tokens, distribute
privately, hash them before storing, and revoke by removing their registry entry.
Never put this file or tokens in Git, ZIPs, screenshots or logs. Browser keeps the
token only in memory and clears it on sign out; it is not saved to localStorage.
Production identity federation/token issuance remains separately designed; no
Cognito is created or claimed. These local credentials are not DB/master secrets.

Admin can review/reopen/correct/reject/read audit; Analyst can review/correct/reject
within assigned accounts, but cannot reopen terminal CLEARED/CONFIRMED cases or
modify another analyst's active review. Auditor reads only. HTTP role/subject
headers and JSON actor fields cannot assign authority. Unknown-account cases
require Admin to assign an eligible account within their account scope.
Admin sees global ingestion health, while financial/review data remain scoped.

Review mutations require a UUID request ID, expected integer version, valid
transition, notes and matching resolution code. A repeated request must match
actor/object/content digest. A stale version/conflicting reused request returns
409; refresh instead of changing financial facts. The history trigger appends
under a dedicated non-login owner; API role has no direct history INSERT/UPDATE/
DELETE or financial INSERT/UPDATE/DELETE. The proposed grants in
`infrastructure/rds/release1_permissions.sql` still require PG16 service-role
verification. No grants have been applied to live RDS.

Correction creates a new versioned allowlisted JSON candidate with correction ID,
never alters original evidence and never approves directly into the ledger.
Original data is readable only through the authorized, version-pinned quarantine
detail API. Atomic SQL submission adds correction history, a new batch/occurrence
and PENDING correction outbox. `release_workflow.drain_corrections(limit=10)` is the
bounded local worker execution path; it revalidates, dedupes and scores using the
same strict worker. Failed infrastructure leaves PENDING; replay is idempotent.
Still-invalid candidate creates new quarantine; original case reopens. ACCEPTED or
DUPLICATE resolves the case. A second unresolved correction or correction after
rejection/resolution is refused. Payloads written before SQL failure can leave
unreferenced S3 versions; retain them for incident evidence, then clean up only
under separately approved retention controls. No S3 upload occurs in this phase.

The future private worker can poll the SQL correction outbox using existing RDS
connectivity and access S3/DynamoDB through existing gateway endpoints. No SQS send,
Secrets Manager retrieval, NAT or new interface endpoint is needed by the drain.
Its approved invocation/scheduling, scoped IAM and package are a later deployment
checkpoint, not a resource created here. Local role policies can be proposed
using `infrastructure/iam/create_roles.py --release1` (existing required arguments
still apply). API adds only exact quarantine evidence-read and correction-write
prefixes; scorer adds the Release1 evidence-write prefix. Access Analyzer must be
run in the later AWS-approved read-only checkpoint; no validation claim here.

## Failures and bounded redrive

Business-invalid rows are quarantine, never DLQ solely due to validation. For a
technical poison message, capture message ID, source version/batch/row and error
TYPE (not payload/credential). First correct the cause. Inspect an explicit set
of at most20 messages; use at most3 manually approved redrive cycles per incident,
then stop/escalate. Queue native maxReceiveCount remains5. Do not blindly redrive
whole DLQs or rewrite message identity. Reprocessing terminal occurrences cannot
add financial rows; incomplete accounting remains pending until reconciled.
No automatic redrive automation is claimed or deployed. SENDING/UNKNOWN SES
attempts require provider reconciliation. RETRYING is a display/operational label
for an intentional retry of FAILED, not an unsafe reclaim of ambiguous delivery.
SES failure never rolls back a financial commit. Exactly-once email delivery is
not promised; one logical alert claim and conservative ambiguity handling are.

## Observability and governance

Local `/v1/metrics` exposes assigned-account accepted/high-risk, review backlog/
oldest case and projection backlog; Admin additionally sees per-state batch and
row outcome totals. Structured runtime logs must include safe IDs, status, counts,
latency and error type, never candidate payloads, tokens/master credentials or
customer names/identity numbers. Empty/header-only files are explicit failures,
not unnoticed successful zero-row processing. Monitor batch pending count and
counts_consistent, PENDING correction/projection outboxes, failed/partial batches,
quarantine rates, oldest review, SQS oldest age/depth, DLQ visible count, Lambda
errors/throttles/duration and SES FAILED/SENDING/UNKNOWN age. Suggested demo runbook
triggers: any DLQ/invalid reconciliation/FAILED batch -> investigate immediately;
nonzero pending/projection/correction older than15min -> pause further input and
reconcile; OPEN review older than24h -> analyst handoff; any uncertain alert ->
provider review before resend. Cloud metric/alarm wiring is designed, not deployed.

Only synthetic demo data is approved. Allowlisted merchant/source/account values
must themselves be synthetic; allowlisting alone does not magically remove PII.
No evidence should contain raw customer PII or credentials. Existing Stage2 S3
versioning/encryption/lifecycle is previously verified, not re-inspected here.
SQL ledger/audit/quarantine retention and expiry enforcement are DESIGNED: retain
for the capstone review; later purge/export requires an approved policy. SQL
history is append-only with no automatic deletion. Glacier/live lifecycle proof
must come from the approved inventory; do not infer a Glacier archive exists.
No new fixed-cost AWS resource is proposed or created in this local milestone.
Future invocations, row/control SQS requests, evidence/version storage and Dynamo
writes are usage-based. Existing AWS standing costs are unchanged; use the existing
cost plan/alerts, not credits as permission to activate.

## Mandatory release order and recovery

1. Exact new source passes Linux CPython3.12 and PostgreSQL16 gates, including
   fresh/legacy/order/rerun/conflict/transactional rollback and service privileges.
2. Freeze migration002 checksum/catalog and business schema; keep001 identity-only.
3. Backend and local frontend/E2E green; import actual external CSV A/B and freeze
   per-row manifest/hashes. Constructed scenarios do not prove unseen artifacts.
4. Separately approved read-only live preflight, then approved snapshot.
5. Apply001 through its verified runner, then002 through a separately reviewed
   runner/administrator path. Current historical runner only supports001.
6. Apply reviewed minimal workflow grants; verify schema/source/catalog/ownership.
7. Deploy exact new verified runtime/package with concurrency disabled/unwired.
8. Controlled smoke tests and outcome/projection/review/alert reconciliation.
9. Separate approval for concurrency activation, then trigger wiring.
10. Full AWS end-to-end evidence and cleanup/cost checkpoint.

Migration tracking in `fintrust/migrations.py` is a LOCAL-only loopback test harness,
not a live RDS runner. SQL transaction failure leaves no partial002/version entry.
Existing applied source/catalog mismatch fails closed. Privileges are independently
verified; approved post-migration owner/grant changes are not catalogue drift.
Never edit an applied checksum, forcibly mark a migration applied or DROP financial
history to recover. Preserve failed evidence and use a reviewed forward fix.

Old code can read the additive new schema, but it cannot create Release1 operational
outcomes. Therefore old-runtime fallback requires intake/triggers paused and a
reconciliation plan; do not keep publishing v3 jobs into an old worker. New runtime
requires verified001/002/grants before use. There is no destructive down migration.
Historical ZIP `cf9c18a5...dd6654` remains untouched and is superseded by source changes
only after a new reviewed CI artifact exists. No new package was rebuilt here.

## Capability scope

| Capability | Status | Classification | Evidence |
|---|---|---|---|
| Ingestion/validation | IMPLEMENTED + VERIFIED (local) | BLOCKER/RELEASE_1 | strict intake/worker tests |
| Duplicate protection/cross-file idempotency | IMPLEMENTED + VERIFIED (local) | ALREADY_COVERED/RELEASE_1 | concurrent/frozen identity tests |
| Quarantine/correction/reprocessing | IMPLEMENTED + VERIFIED (local) | RELEASE_1 | versioned evidence, correction-outbox tests |
| Risk scoring | IMPLEMENTED + VERIFIED (local) | ALREADY_COVERED/RELEASE_1 | amount/velocity/time/double-charge boundaries |
| Review | IMPLEMENTED + VERIFIED (local) | RELEASE_1 | stale/replay/audit/ledger tests and browser |
| Alerting | IMPLEMENTED + VERIFIED (mocked local boundary) | ALREADY_COVERED | SES replay/ambiguity tests |
| Reconciliation | IMPLEMENTED + VERIFIED (local) | BLOCKER | mixed/partial/retry terminal-outcome tests |
| API/RBAC | IMPLEMENTED + VERIFIED (local) | BLOCKER/RELEASE_1 | real token/scope/mass-assignment tests |
| Frontend | IMPLEMENTED + VERIFIED (local browser) | RELEASE_1 | browser-result.json and synthetic screenshots |
| Reporting | IMPLEMENTED + VERIFIED (local) | RELEASE_1 | account/currency report tests; no balance/FX claim |
| Observability | IMPLEMENTED + VERIFIED (local); cloud alarms DESIGNED | RELEASE_1 | metrics tests and runbooks |
| Governance | DESIGNED; safe evidence IMPLEMENTED + VERIFIED | RELEASE_1 | safe payload tests; retention implementation limits above |
| Migrations | IMPLEMENTED + VERIFIED (PG18.6); PG16 BLOCKED | BLOCKER | ordered local migration tests; pending dedicated PG16 gate |
| CI/new runtime package | IMPLEMENTED + NOT VERIFIED | BLOCKER | prepared CI job; focused push/CI approved, result recorded in closeout evidence |
| AWS Integration | BLOCKED for this release; prior stages verified | BLOCKER | no new AWS access/deploy authorized |

Deferred: hourly velocity, refund/reversal/chargeback accounting, FX/current balance
engine, automatic uncertain-SES retry, federation/Cognito, HA/multi-region/proxy and
production-scale lifecycle automation. These are not silently implemented here.


## Exact next local review step

`python tools/serve_release1_demo.py --role Admin --seed-scenarios`

This creates only the labelled isolated schema `fintrust_release1_demo` in the
already configured dedicated loopback test DB, prompts privately for a local
opaque access token, stores its hash in ignored `.env.release1-auth.json`, and
serves `http://127.0.0.1:5001/release1`. Generated rows are labelled constructed
scenarios, not CSV A/B. Use separate tokens/roles for later Analyst/Auditor sessions.
Do not screenshot tokens. This is not a cloud deployment or least-privilege proof.

The optional demo uses in-memory AWS mocks: original safe payload evidence and
projections do not persist across process restarts. Old demo cases whose mocked
versions no longer exist correctly fail closed; use a new constructed scenario
for a new session. Do not present the optional demo as durable evidence. The
versioned real-S3 contract is tested separately with mocked service semantics;
live RDS/S3 durability requires later approved AWS evidence. Do not automatically
reset a demo schema or discard its audit merely to hide missing mock evidence.

The user approved the focused push/CI for PG16 service privileges and exact-source Linux package verification on 2026-10-10. Results are recorded in the closeout evidence. No AWS action is approved.

Reports use bounded account/currency pagination. Non-admin batch views expose only batches whose every recorded row belongs to assigned accounts; unresolved/unknown and mixed-scope batches are Admin-only.

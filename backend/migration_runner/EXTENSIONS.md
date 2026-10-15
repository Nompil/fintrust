# Controlled migration 003–006 runner

This is a separate migration-tool candidate. It does not modify the application
release, scoring, canonical SQL, existing cloud resources or the original seven
phase archives. No migration runs on import or during packaging.

## Fixed operations and authority

| Package phase | Allowed operation | Database connection |
| --- | --- | --- |
| bootstrap_extensions | bootstrap_extensions | Existing administrator transport; installs fixed helpers only |
| iam_extensions | migrate003, migrate004, migrate005, migrate006, verify_extensions | Fixed IAM migration login; explicit master-secret deny |
| cleanup_extensions | cleanup_extensions | Administrator transport; removes helpers and temporary workflow-owner CREATE |

There is no directory discovery or automatic loop applying arbitrary SQL files.
The four version/file/SHA-256 bindings are explicit in extensions.py. An invocation
accepts only operation and canonical UUID request_id, never SQL, DSN, host, schema,
version overrides or credentials. Deploying a new file in sql/migrations does not
make it executable. Invoke a reviewed numeric Lambda version, never $LATEST.

Bootstrap requires a verified 001/002 history, the expected non-login workflow
owner and the exact existing ledger CHECK. It transactionally adds a CHECK for
versions 001–006 before removing the inspected 001/002 CHECK. Existing history
rows are preserved. It grants the login SELECT/INSERT on that ledger, not UPDATE
or DELETE, owner membership or schema CREATE. Administrator SET access is removed
before commit. Helpers have no arguments, a pinned body and owner/search_path,
and no PUBLIC execute grant. The executor checks their actual definitions and
ACLs before invocation.

Run migrate003 → migrate004 → migrate005 → migrate006 explicitly, then
verify_extensions. Each helper performs only its bound SQL and drops itself in
the same transaction. Each version requires its verified predecessor. The history
catalog accounts for deliberate guard evolution without overwriting old snapshots.
After 006, rerunning any of the four operations validates the latest catalog and
returns ALREADY_APPLIED without DDL. The old 002 executor remains conservative and
refuses a history containing later versions; do not substitute it for this verifier.

The handler owns commit/rollback. Fixed SQL wrappers are removed before helper
installation, so DDL, helper removal, postchecks and history insertion share one
transaction. Statement and lock timeouts remain 15 seconds and 2 seconds. A
commit_outcome_unknown result requires reconciliation; there is no automatic retry.

## Migration review

| Migration | Schema/behavior change | Dependencies | Destructive/irreversible considerations |
| --- | --- | --- | --- |
| 003 | Adds transaction_lifecycle_events, identity sequence, primary/unique/foreign-key/check constraints, lifecycle_business_once index, validate_lifecycle_event function and two audit triggers | Verified 002 ingestion_records and reject_history_change | No backfill or financial DML. CREATE objects are transactional. Future identity-sequence increments are ordinary PostgreSQL sequence behavior, not promised to roll back like table rows. |
| 004 | Replaces guard_review_transition to permit controlled assignment/reassignment/release; adds risk_reviews_assignee_queue | Verified 003 and existing 002 reviews/history | No row rewrite or drop. Ordinary CREATE INDEX can lock/block writes; existing timeouts bound the attempt. Changes future review behavior after commit. |
| 005 | Replaces the same guard to allow the assigned investigator to append notes while UNDER_REVIEW | Verified 004 | No new table/column or historical note rewrite. Changes future permitted transitions after commit. |
| 006 | Replaces that guard's INSERT eligibility: known V1 Medium/High at score ≥40; known V2 Medium/High at score ≥20; legacy events without result retain ≥40 | Verified 005, processed_transactions.result and risk_events | No historical rescoring, backfill, threshold configuration change or financial DML. Unknown recorded rule versions are rejected. |

Raw SQL is not the idempotency API: 003 has CREATE statements and 004 creates an
index without IF NOT EXISTS. Use the runner's source/history/catalog checks.
005/006 can replace a function if executed directly, so do not replay them outside
the controlled runner. There is no automatic down-migration after a successful
commit; any reversal requires separate review of current application dependencies.

Cleanup removes unused helpers and workflow-owner schema CREATE, retaining the
persistent owner and committed schema/history. Complete the separately reviewed
temporary-login and AWS IAM/network cleanup as well. A fresh bootstrap intentionally
refuses partial/applied extension state: after an interrupted rollout, reconcile
history and remaining helpers before an explicit resume; never auto-repair drift.

## Local verification

tools/check_extensions_pg16.py requires Linux and exact PostgreSQL 16.15 on an
explicit disposable loopback database. It first rehearses the existing 001/002
path, then calls the real new Lambda handlers with local test-only connection
adapters. Production host, TLS validation, IAM connection code and session guards
are not weakened. Local rds_iam role membership is a simulation, not cloud IAM.

Checks cover all four applications and reruns, forced failure after DDL and after
ledger INSERT, partial states, out-of-order operations, changed helpers/PUBLIC
execute, catalog drift, denied arbitrary SQL/DDL/financial updates, immutable
history, lifecycle transitions, assignment, notes and nine versioned eligibility
cases. Historical financial facts are seeded before 001 hardening. Per-migration
row-content hashes prove preservation of six financial tables plus existing
reviews and history. Test behavior probes run in rolled-back transactions.

The ownership-only 001 fixture cannot insert new risk facts afterward without
additional runtime privileges because of referenced-table foreign-key checks.
The rehearsal does not widen those grants to hide this. Live runtime privileges
and application writes must be reconciled and tested independently before activation.

tools/record_extension_verification.py binds the exact rehearsed source hashes,
zero-skip focused tests and Linux-imported ZIPs. The new manual CI workflow uses
PostgreSQL 16.15 and has no AWS credentials or deployment step. It is prepared
locally; no hosted run or live deployment is implied.

# Release 1 base-schema bootstrap review

Presentation parent remains `5b5bb50f4bf02bca518940675f9b476bd8750a67`, unchanged. The separately requested UX correction changes application source and must have its own release/artifact decision. No AWS login, secret retrieval, RDS contact, live SQL, snapshot, package build or Git push occurs in this review. The 157 pre-existing recovery files remain excluded.

## Authoritative artifacts and order

1. **Base:** `sql/schema.sql`, exactly the content before `-- Additive identity hardening.`. This includes the six base tables, existing indexes and Phase 1 alert-delivery upgrades. It excludes the duplicated convenience identity tail. `sql/bootstrap/release1-base-manifest.json` binds this section by checksum.
2. **001:** `sql/migrations/001_transaction_identity.sql`. Additive transaction identity columns/checks and partial source-identity uniqueness; fingerprints are deliberately not unique.
3. **002:** `sql/migrations/002_operational_workflows.sql`. Ten workflow tables, two workflow views and immutable-evidence/transition/reconciliation triggers. No synthetic seed insertion.
4. Runtime permissions: separately reviewed `infrastructure/rds/permissions.sql` and `release1_permissions.sql`, after schema verification. These must not give application identities DDL powers.

`sql/seed.sql` is optional synthetic test/demo data only, never part of live bootstrap. `sql/views.sql` and `sql/procedure.sql` are legacy reporting/manual-flag artifacts: the current Python application has no references to `v_account_*` or `flag_account`. They are not silently added to the Release 1 live chain. The additive tail in `sql/schema.sql` is a monolithic local convenience, not a competing migration authority. The untracked `infrastructure/rds/schema.sql` is preserved and is not promoted into a second base authority.

## Minimal deterministic base composition

`python tools/render_release1_base.py --output build/database-bootstrap/release1-base.sql`

This renders SQL locally; it never connects to a database. It verifies the base checksum and exact section boundary, wraps the DDL in a transaction and refuses any nonextension application relation already present in `public`. Base rerun therefore refuses cleanly; it does not guess how to repair partial/drifted state. No seeds, identity migration, workflow migration or runtime grants are folded into it.

The proposed first live write is this reviewed rendered base transaction, executed by the separately approved private administrator/bootstrap path only after fresh read-only empty-schema/ownership/extension preflight and PostgreSQL 16 verification. **Do not execute it now.** The existing temporary-identity runner SQL requires `public.transactions` already to exist, so it cannot bootstrap an empty RDS database. The runner must be explicitly prepared and verified for base creation before a live write is approved.

## Preconditions, preservation and versioning

001 requires an owned `transactions` table with the original account/amount/currency/date/type/raw-file facts. It does not create those tables. Existing historical rows retain their facts and nullable new identity fields. Existing conflicting source identifiers cause unique-index creation to fail; never delete or coerce rows to proceed.

002 requires the verified 001 identity state plus base customers/accounts/transactions/risk_events/alerts/processed_transactions. Its raw SQL creates tables/functions/triggers without rerun guards: raw rerun fails rather than being a no-op. `fintrust.migrations.apply_local` composes the reviewed SQL, serializes execution with a transaction advisory lock, and records version/source checksum/catalog checksum/applied time. Verified individual reruns return ALREADY_APPLIED and reject recorded source/catalog changes. Raw migration SQL alone does not create history: no fabricated historical entries are allowed. The Operations page reads this history.

Base contains PK/FK ownership relationships, positive NUMERIC amounts, permitted currencies/types, account/customer identity and alert states PENDING/SENDING/SENT/FAILED/UNKNOWN. 001 constrains source-reference/system consistency and source-row/fingerprint shape. 002 constrains review states OPEN/UNDER_REVIEW/CLEARED/CONFIRMED_RISK/ESCALATED, row outcomes, correction outboxes and operation receipts. Backend role restrictions remain stricter than the database transition graph. Source inventory is in `docs/EVIDENCE/05-rds/release1-base-source-review.json`; observed PostgreSQL 16 object counts are not yet available.

## Recovery and privileges

Base rendering and raw 001/002 each have transactional BEGIN/COMMIT boundaries; a failure rolls back that stage. The migration harness owns one transaction per migration and strips only the outer transaction statements. There is no approved destructive down-migration. After a previously committed stage, rollback of a later stage does not remove earlier committed objects. Partial unknown state, wrong types/nullability, conflicting index definitions or history mismatch require manual review; no automatic repair. IF NOT EXISTS alone is not schema verification.

Initial base creation requires schema CREATE, extension creation if needed, and ownership of created objects. The PostgreSQL administrator/bootstrap identity owns base DDL; temporary IAM-auth migration roles and narrow ownership/helper grants are separate from runtime roles. Existing PG16 role rehearsal tools are `tools/check_migration_roles_pg16.py`, `tools/check_workflows_pg16.py` and `tools/check_release1_roles_pg16.py`; no new privilege broadening is proposed. A disposable PG16 administrator is needed to prove role creation, grants, cleanup and denial of runtime DDL.

## Required execution gate — BLOCKED

This host has PostgreSQL **18.6** and a nonadministrator dedicated test account. It cannot provide the requested PostgreSQL 16 empty-database and service-role proof. Docker is unavailable; no installed WSL distribution or Linux PG16 execution path has been established in this checkpoint. Existing CI uses `postgres:16`, but this new local source is unpushed. Running an older remote CI commit would not verify these changes, and the user prohibits push and application artifact rebuild in this task.

The existing local application suite demonstrates the base-section -> 001 -> 002 chain on its own isolated local schemas. That evidence must not be relabeled PostgreSQL 16. Offline renderer checks are source-composition tests only.

Before live readiness can be marked VERIFIED, run the proposed base transaction on a fresh disposable PG16 database, then 001 and 002 with recorded history; verify exact catalog/constraints/indexes, seed-free state and approved synthetic row/amount/account preservation in a second disposable case; exercise full/individual reruns and missing/partial tables/indexes/type/nullability/history drift; run all three PG16 role gates and the full Linux/PostgreSQL suite. No AWS/live database is a substitute for this missing proof. A separate push/CI approval or provisioned disposable local PG16 administrator is required.

| Stage | Artifact | Preconditions | Executor | Privileges | Verified | Recovery | Live-ready |
|---|---|---|---|---|---|---|---|
| Base schema | Checksum-bound base section | Empty public schema | Approved bootstrap administrator | Schema CREATE/object ownership; extension if needed | BLOCKED | Transaction rollback; rerun refuses | BLOCKED |
| 001 | Reviewed identity SQL | Verified base and ownership | Approved migration identity | ALTER and scoped index/helper grants | BLOCKED | Transaction rollback; recorded rerun/drift check | BLOCKED |
| 002 | Reviewed workflow SQL | Verified 001 and ownership | Approved workflow migration identity | Scoped CREATE/ownership/helper grants | BLOCKED | Transaction rollback; no automatic drift repair | BLOCKED |

FINTRUST BASE SCHEMA BOOTSTRAP BLOCKED — disposable PostgreSQL 16 administrator and current-source Linux/CI execution are unavailable under the no-push boundary

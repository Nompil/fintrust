# Private RDS migration path - ready for design review

Status: **PRIVATE RDS MIGRATION PATH READY FOR REVIEW**. This is a design and
read-only preflight preparation checkpoint, not authorization to deploy or execute.
The runner is NOT implemented, packaged, deployed or invoked. No live SQL, secret
retrieval, snapshot, IAM/network mutation or application deployment occurred.
Read-only AWS metadata was collected on 2026-10-09 (Africa/Johannesburg date).
Live schema, owners, grants, row counts and migration state remain **UNKNOWN**.

The verified application ZIP remains unchanged: source `5385c581e76ae1c0d486e569b6beb4c6b67d548c`,
[CI 37850256137](https://github.com/Nompil/fintrust/actions/runs/37850256137), SHA256
`cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654`.
385 tests passed with no failures/skips. This does not verify the future migration runner.

## Connectivity findings

Inventory identity was `arn:aws:iam::966467878406:user/fintrust-inventory`.
Evidence: [private-migration-path](../docs/EVIDENCE/05-rds/private-migration-path/rds.json).

| Item | Read-only live result |
|---|---|
| DB | `fintrust-ledger-dev`, database `fintrust`, available, PostgreSQL 16.15 |
| Capacity | db.t4g.micro, Single-AZ, 20 GiB gp3, encrypted, deletion protection on |
| Endpoint | `fintrust-ledger-dev.cv84aee6u6up.af-south-1.rds.amazonaws.com:5432` |
| Resource ID | `db-QZ3JN4H22YOMU7VLI22RL2IUYQ` |
| VPC | `vpc-0aba008bb360f5147` |
| DB subnet group | `fintrust-db-dev` |
| DB subnets | `subnet-04dc0f576867d7a6c` (af-south-1a), `subnet-084deb13f49a36064` (af-south-1b) |
| Application subnets | `subnet-0c2d87e8a83361e30`, `subnet-0328276227fa30ead` |
| DB SG | `sg-01644a4c9f2c44162`; sole ingress TCP 5432 from app SG |
| App SG | `sg-0850bd798bb9505e2`; egress 5432 to DB SG, 443 to S3/DynamoDB prefix lists; no ingress |
| Routes | Local VPC routes; application routes additionally use S3/DynamoDB gateway endpoints; no default internet route |
| Endpoints | Only S3 and DynamoDB gateways, both available; no Secrets Manager/SSM interface endpoint |
| Authentication/TLS | IAM auth enabled; `fintrust-postgres16-dev` in sync; `rds.force_ssl=1` |
| Backup | One-day retention; latest restorable time recorded in rds.json (must refresh before execution) |
| Secret | RDS-managed master secret active; username `fintrust_admin`; value NOT retrieved |
| Existing compute | Regional Lambda inventory contains only `fintrust-ingest-dev`, outside VPC; concurrency 0. No EC2 instance in this VPC |

The repo defines future scoring/API/report VPC functions but these are not deployed.
There is no implemented migration/bootstrap Lambda or EC2 bastion in the inspected
code/live inventory. No existing SSM runner on EC2 exists in this VPC. CloudShell
VPC environments and external hybrid SSM nodes were not inventoried; do not claim
account-wide absence. No existing approved private laptop/VPN path is recorded.
The earlier bootstrap note proposed a new bootstrap SG; reuse the existing app SG
instead. No DB ingress change is needed. Recheck NACLs, subnet capacity and DNS
attributes during runner implementation; SGs/routes alone do not prove a DB handshake.

## Alternatives

| Approach | Reachability, credentials, TLS, cost and suitability |
|---|---|
| A. Dedicated temporary VPC Lambda - preferred | Reuse app subnets/SG, direct TLS 5432, no NAT/public ingress/endpoint. Separate audited package and narrow role, fixed operations, synchronous invocation, one connection. Small request/compute/log usage; delete after use. Read-only first, approved DDL later; transactional rollback and snapshot recovery. Credential bootstrap described below is essential. |
| B. Reuse application Lambda - reject | Only ingest exists and it is outside VPC. Adding network access, DDL credentials and a migration mode would expand its role and alter reviewed runtime/package boundaries. Future scoring role must not own tables. Lambda cost remains small but cleanup/rollback and audit separation worsen. |
| C. EC2 + SSM - reject for this task | Could reach RDS with app SG, TLS and IAM DB token or secret. No runner exists. Private SSM control needs endpoints (ssm/ssmmessages and any applicable region/agent dependencies) or network egress. Adds instance/EBS, agent/IAM, endpoint charges, OS maintenance and cleanup; conflicts with the current no-NAT/no-interface-endpoint plan. |
| D. Default CloudShell/local laptop - reject direct access | Neither has a route into this VPC. Public RDS, broad ingress or improvised tunnels are unacceptable. TLS and an IAM token cannot create a network route. |
| D2. CloudShell VPC environment - viable fallback, not selected | A configured VPC environment can reach RDS with the app SG without NAT for the DB connection. It needs its own IAM/ENI setup and region availability check. In this subnet it cannot fetch Secrets Manager or arbitrary packages from public APIs; IAM DB login must already exist or credentials must be handed in. Ephemeral shell/tool transfer and interactive privileged SQL are harder to pin and audit than fixed reviewed Lambda operations. No claim that CloudShell inherently cannot reach private RDS. |
| E. RDS Data API - not applicable | This instance is standard RDS PostgreSQL, not an Aurora Data API cluster. No HTTP SQL path exists for it; changing to Aurora is an unnecessary architecture/cost change. |
| F. Existing repo SQL/local tools | Canonical SQL and local tests are useful inputs, not a network bridge. `tools/local.py` deliberately restricts itself to loopback practice databases. The untracked `infrastructure/rds/schema.sql` is not adopted; do not execute it. |

Sources: [Lambda VPC](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html),
[SSM private connectivity](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html),
[CloudShell VPC](https://docs.aws.amazon.com/cloudshell/latest/userguide/using-cshell-in-vpc.html),
[Data API scope](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/data-api.html).

## Selected architecture and credential bootstrap

Prepare a separate `fintrust-migration-dev` Lambda (proposed name), Python 3.12
x86_64, 512 MiB, 300-second timeout, no URL, no triggers, no async destinations,
no extensions, no tracing, no provisioned concurrency. Start at reserved concurrency
0. Only after separate approval allow this temporary function concurrency 1 for
controlled synchronous requests; application ingest remains at 0. If account
concurrency quotas cannot support that reservation, stop for review, do not relax it.
Reuse both application subnets and `sg-0850bd798bb9505e2`. Deploy a precreated
14-day log group `/aws/lambda/fintrust-migration-dev`, dedicated execution role and
explicit policies. No new SG, endpoint, EC2, NAT or RDS instance is selected.

Initially build a **read-only-only** runner version. It must have no DDL operation
or arbitrary SQL input. The approved immutable code/version/checksum, migration
SQL checksum, endpoint, DB, schema, account and region are pinned by the controller.
A later DDL runner version requires separate review after live preflight. Do not
bundle migration control into the verified application ZIP or rebuild that ZIP.

IAM auth needs a PostgreSQL login plus `rds_iam` and matching `rds-db:connect`;
enabling the instance feature alone does not create them. Owner/grant state is
unknown, so do not assume an IAM principal can bootstrap itself. See
[AWS database account setup](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.DBAccounts.html).

For the first inspection only, retain the existing repo proposal: an approved,
scripted controller on the administrator workstation uses an MFA-backed identity
to retrieve the exact RDS master secret, validates its username/target metadata,
and sends credentials only in memory through a synchronous Lambda Invoke SDK
request over HTTPS. The controller is a reviewed tool, not manual SQL improvisation.
It must not accept arbitrary SQL, dump SDK debug output, shell arguments, files,
environment variables, CLI history, notebook state, events, DSNs or exception
messages containing credentials. Disable SDK invocation retries. Do not use the
Lambda console's saved test events, async invocation, DLQs or LogType=Tail.
Runner logs only allowlisted request/phase/hash/status/SQLSTATE metadata. Explicitly
catch failures and never return raw DB/SDK exceptions or the input event. CloudTrail
is metadata evidence, not a place to save the secret-bearing payload. Redaction and
failure-path tests are mandatory before approving this credential handoff.

This is a sensitive bootstrap exception: master credentials exist transiently in
controller/runner memory and master privileges could be abused by faulty code.
TLS and read-only transactions do not turn the master into a least-privilege login.
Approve that narrow first connection explicitly; never give it to application code.
If this handoff is rejected, stop: a separately approved temporary Secrets Manager
interface endpoint (with SG changes/cost) is the alternative, not an implicit fallback.
Gateway endpoints do not provide Secrets Manager access. See
[Secrets Manager endpoint](https://docs.aws.amazon.com/secretsmanager/latest/userguide/vpc-endpoint-overview.html).

Use psycopg2 directly in the runner, not `fintrust.db`: application configuration
correctly requires IAM auth in Lambda and its password path is inappropriate here.
Bundle reviewed psycopg2 Linux CPython 3.12 wheels and the current public RDS CA;
verify the runner separately under Linux. Require `sslmode=verify-full`, the actual
RDS DNS endpoint above, port 5432, connect_timeout=5; never use an IP alias or
`sslmode=require` as a certificate/hostname-verification substitute. Return only
SSL protocol/cipher and client verification mode, never credentials/cert private data.

## IAM design for later implementation (no policies attached)

- Controller: `secretsmanager:GetSecretValue` and `DescribeSecret` only on
  `arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn`;
  `lambda:InvokeFunction` only the approved qualified migration function version;
  scoped RDS/CloudFormation/Lambda metadata reads to verify bindings. Region
  af-south-1. No application invocation, S3 writes or arbitrary secret listing.
  Check current secret encryption metadata/key policy; do not add broad KMS decrypt.
  Customer-key encryption, if discovered, requires exact-key decrypt via Secrets
  Manager/context conditions separately. No secret value was read this turn.
- Migration execution role: Lambda service trust; exact log-group stream creation
  and event writes; Lambda-required EC2 ENI actions only:
  CreateNetworkInterface, DescribeNetworkInterfaces, DescribeSubnets,
  DeleteNetworkInterface, AssignPrivateIpAddresses, UnassignPrivateIpAddresses.
  AWS documents Resource=* for this VPC permission set; restrict requested region.
  Add AWS's explicit Deny on these actions for calls whose
  `lambda:SourceFunctionArn` is the migration function, so function code cannot
  exercise its ENI permissions. Do not use an unproven CalledVia condition for
  Lambda service ENI calls. No Secrets Manager, SSM, KMS, S3, SQS or DynamoDB data
  permission is needed in the runner for the in-memory bootstrap route.
- After database login provisioning approval, add only
  `rds-db:connect` on
  `arn:aws:rds-db:af-south-1:966467878406:dbuser:db-QZ3JN4H22YOMU7VLI22RL2IUYQ/fintrust_migrate_dev`.
  Tokens are signed locally; there is no RDS API/STS call from inside the VPC.
- Separate runner deployment/cleanup identity: scope Lambda create/read/update/
  version/concurrency/delete to the proposed function, logs create/tag/retention
  to its exact group, PassRole only its execution role with PassedToService=lambda,
  and VPC/subnet/SG conditions where supported. IAM bootstrap remains administrator
  controlled. Bind to the approved runner artifact, not the hardened application ZIP.
  Snapshot permissions are a separate approval, never in the runner execution role.

Exact deployable JSON/CloudFormation is deferred until design and credential
handoff approval, per "Do not build it yet". Access Analyzer, template validation,
Linux imports, region/resource condition checks and redaction tests will be required
for that implementation; none is claimed for a runner that does not yet exist.

## Read-only database preflight contract

New scripts: [catalog phase A](../sql/preflight/001_transaction_identity_catalog.sql)
and [aggregate phase B](../sql/preflight/001_transaction_identity_data.sql).
Each uses REPEATABLE READ READ ONLY, 2-second lock and 15-second statement limits,
then ROLLBACK. These are prepared inputs for the private runner, not laptop commands
against RDS. Phase A deliberately works even when `transactions` is absent.
Phase B runs only after the six required base tables and base column types pass review.
Use separate fresh connections for the two phases; freeze writers before comparing
counts, since separate snapshots need not otherwise match. Runner must retrieve the
single JSON SELECT result before executing ROLLBACK and always roll back/close on error.

Capture database/version/current and session identity, target public schema and
controlled pg_catalog search_path, TLS state, tables/sequences and ownership,
all column types/nullability/defaults/generated flags, constraints/validation,
index definitions/predicates/validity/readiness, ACLs/column grants/default ACLs,
role attributes/memberships, views, triggers/RLS and other sessions without SQL text.
Inspect effective CONNECT/USAGE/SELECT rights for the future logins using
`has_database_privilege`, `has_schema_privilege`, `has_table_privilege` and
`has_column_privilege` once their existence is confirmed. Catalog grants visible
to a restricted user may be incomplete: insufficient visibility is UNKNOWN, not PASS.
No pg_authid/password hashes or financial/customer rows are exported.

| Finding | Required disposition |
|---|---|
| Base transactions/accounts/customers/risk_events/alerts/processed_transactions missing | BOOTSTRAP REQUIRED. Stop; 001 does not create tables, views, grants or seed data. Review canonical baseline deployment separately. Never auto-run schema.sql/seed.sql or an untracked SQL file. |
| All seven new columns and both named indexes absent | NOT APPLIED, provided baseline schema is correct. Check all rows/constraints before DDL. |
| Some new objects present | PARTIAL. Compare every existing definition; proceed only for an exact compatible subset with valid data. Any mismatch stops. |
| Seven columns and two names present | CANDIDATE COMPLETE, not proof. Require all exact definitions below and valid CHECK/index state before recording FULLY APPLIED. |
| Wrong types/defaults/nullability, missing/wrong CHECK, wrong index, invalid index, unexpected trigger/RLS | BLOCKED - definition drift. The migration's IF NOT EXISTS does not repair it. No automatic drop/recreate. |

Expected nullable/no-default additions: source_system varchar(100),
source_transaction_id varchar(200), transaction_fingerprint char(64), batch_id uuid,
file_sha256 char(64), source_row integer, country char(2). CHECKs must enforce lowercase
64-hex fingerprints/file hashes, source_row>=2, and the exact named nonblank-source
identity condition in 001. Existing CHECK names can differ; compare expressions and
validation, not just names. Both indexes must be valid/ready btree indexes on public.transactions:
unique (source_system,account_id,source_transaction_id), and nonunique
(account_id,merchant,currency,amount,tx_date), each WHERE source_transaction_id IS NOT NULL.
A fingerprint unique constraint is not intended. Existing base defaults/PK/FK and
raw_file TEXT/processed_transactions are compatibility requirements too.

Phase B returns counts for the six tables, duplicate reliable-identity groups,
invalid nonblank-source identities, fingerprints/file hashes and source rows. JSON
field access tolerates absent new columns on legacy rows; it is bounded by timeout
and must not be used as an unbounded large-table scan. Review table sizes first.
Zero violating rows and stable before/after counts are mandatory. An access denial,
timeout, connection failure or partial output fails closed; do not record empty data
as success. Full migration state remains a reviewed catalog/data conclusion, not
an automatic verdict based on object counts.

## Migration safety and database identity

001 contains BEGIN/COMMIT, seven ADD COLUMN IF NOT EXISTS operations, a guarded
CHECK, and two CREATE INDEX IF NOT EXISTS operations. No DELETE/UPDATE/backfill,
destructive DDL, table creation, FK or forced defaults. Fully legacy rows receive
NULL values, remain outside partial uniqueness, and satisfy the new nullable CHECKs.
However existing partial data CAN cause CHECK/unique-index failure. A local test
now proves duplicate preexisting source references fail and roll the DDL back.
The rerun is safe only with matching definitions/data; another test proves a wrong
existing column/index silently survives IF NOT EXISTS, hence the catalog gate.

PostgreSQL ALTER TABLE requires table ownership, not a grantable generic ALTER
privilege. SELECT/INSERT grants do not suffice. Preferred DDL identity:
`fintrust_migrate_dev` LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION,
NOBYPASSRLS, with rds_iam and temporary SET ROLE access to a narrow NOLOGIN table
owner. It must not inherit fintrust_admin/rds_superuser or any runtime login.
Grant CONNECT on fintrust and schema USAGE plus required preflight SELECT; no
PUBLIC-wide grants. The login owns no persistent objects.

If an existing narrow owner of transactions exists, grant temporary membership
with PG16 SET enabled, INHERIT/ADMIN disabled, then SET ROLE for the exact migration.
If transactions is owned by the master/broad admin, do NOT grant that broad role.
After separate approval, use the bootstrap administrator to create
`fintrust_transactions_owner` NOLOGIN, transfer only public.transactions ownership,
preserving ACLs, and grant temporary SET membership to fintrust_migrate_dev. The
new owner needs schema CREATE for ownership transfer; grant only during transfer
and revoke afterward. Review ownership/dependency effects and record before/after
ACLs; this is an additional controlled bootstrap change, not hidden inside 001.
The narrow NOLOGIN owner remains after cleanup; revoke/drop only the temporary
login, never the persistent table owner or its objects. If ownership cannot be
changed safely, stop for explicit administrator-executed fixed-DDL exception review.
Do not claim the master is needed for every future migration.

Runtime SQL roles stay nonowners. `infrastructure/rds/permissions.sql` defines
service grants, but provisioning is not part of 001. Cloud logins are only
fintrust_scoring_dev, fintrust_api_dev and fintrust_report_dev with corresponding
service groups and rds_iam. Existing live memberships/grants are unknown. Never
apply the whole permissions.sql blindly: it revokes/regrants across public tables.
Generate and review a minimal grant delta after preflight. Existing table-level
SELECT/INSERT grants include added columns; column-specific grants need review.
Views keep their recorded owners; new migrations/indexes must not change runtime
ownership. Password bootstrap and schema/bootstrap provisioning are separate gates.

ALTER TABLE takes strong locks, usually ACCESS EXCLUSIVE for these additions;
locks persist through COMMIT. Ordinary CREATE INDEX blocks writers; in this combined
transaction earlier ALTER locks can also block readers. Do not switch to CONCURRENTLY
inside this transaction. Fixed session advisory lock for this migration prevents
cooperating runners racing but does not stop other writers. Recheck active sessions,
freeze all producers/consumers, acquire the table maintenance lock, and recheck
catalog/data inside the same transaction before DDL. The future runner must handle
001's explicit BEGIN/COMMIT correctly, not nest transactions or split a DO block on
semicolons. Require 5-second lock timeout, 60-second per-statement timeout and
60-second idle-in-transaction timeout, with a controller deadline shorter than the
300-second Lambda ceiling. One connection, no automatic retries after ambiguity.

For a few hundred rows, expect seconds, but live count/size and t4g.micro headroom
are unknown; this is not a measured latency guarantee. IAM auth adds memory demand
on a small instance. Monitor free memory/CPU/connection headroom in the execution
window and stop on stress rather than resize automatically. Concurrency=0 ingest
helps but alone does not prove a maintenance window: verify queues/consumers,
other SQL sessions, schedulers and manual writers. [Locking](https://www.postgresql.org/docs/16/sql-altertable.html),
[index behavior](https://www.postgresql.org/docs/16/sql-createindex.html),
[IAM auth resource implications](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html).

## Backup and recovery checkpoint

Recommend an explicitly approved manual snapshot of fintrust-ledger-dev immediately
before any bootstrap ownership/grant or schema write, after read-only preflight and
writer freeze. Proposed name `fintrust-ledger-dev-pre-identity-<UTC timestamp>`.
Wait for available; record ARN, creation time, source instance/resource ID, engine,
encryption, tags and restore settings. Recheck the latest restorable time/one-day
backup setting; automated backup alone is not an exact pre-migration checkpoint.
Single-AZ snapshots can briefly suspend I/O. Manual snapshots persist until deleted
and may cost money. Obtain retention/cleanup approval (propose seven days after
successful verification), do not silently delete the snapshot or original DB.

Before COMMIT, error/timeout means rollback; confirm the connection ended and compare
catalog/count evidence. A client timeout or lost response can happen after COMMIT:
status is UNKNOWN until fresh read-only preflight reconciles it; do not retry blindly.
After COMMIT, prefer restoring old code while retaining additive columns/indexes.
No automatic DROP COLUMN/index downgrade script: it can destroy new identity data.
If restoration is necessary, a snapshot creates a NEW separately approved private
DB with a new endpoint/resource ID/credential and IAM mapping plan, not an in-place
undo. Specify the existing subnet group/DB SG, encryption, TLS parameter group and
nonpublic settings explicitly; do not accept default networking. Reconcile writes
since snapshot before cutover; approve added RDS cost and cleanup separately.
[Snapshot](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateSnapshot.html),
[restore](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_RestoreFromSnapshot.html).

## Runtime compatibility and deployment order

The new models/validators carry the seven fields; ingest emits source/batch identity
and audits/quarantines to S3 but its cloud queue path never accesses RDS. Ledger and
scoring require the new columns AND the preexisting processed_transactions replay
store; scoring also needs account-row locking, risk_events INSERT/sequence access,
and later DynamoDB publication. Duplicate source references reuse frozen results;
conflicts fail. Similar charges with distinct references remain and are risk-scored.
DynamoDB TX#UUID is a projection after SQL commit, not a schema migration target.
API pagination and reports still use compatible original fields/types; cross-check
monthly SQL, views and any local-loader paths against the actual baseline. Existing
Linux tests establish code compatibility, not live schema/grants. Shared ZIP handlers
do not mean scoring/API/report are deployed. Do not enable ingest into an unreviewed
consumer pipeline simply because its own imports and DB migration pass.

1. Approve this design and sensitive credential handoff; implement/test/review the
   separate read-only runner, exact IAM/template/package, redaction and cleanup.
2. Approve runner infrastructure; deploy disabled, verify pinned network/package,
   then separately authorize one synchronous read-only preflight (temporary runner
   concurrency 1 only). Application concurrency stays 0, triggers unwired.
3. Review live catalog/counts. If baseline absent/incompatible, stop for a separate
   canonical schema/bootstrap/roles plan. Do not apply 001 to an empty database.
4. Freeze writers, approve/create/wait for snapshot and capture restore checkpoint.
5. Approve the precise owner/login/grant bootstrap if required. Provision the narrow
   IAM DB migration identity, verify TLS/privileges, remove master credential access
   from the controller once bootstrap no longer needs it.
6. Review/package/authorize the fixed DDL runner version; recheck preflight under
   lock, execute 001 once, verify catalog, validation/index state and unchanged
   row counts. Controlled rerun only after reconciliation and explicit approval,
   comparing complete schema definitions/counts and preserving all rows.
7. Verify application-role permissions and compatible read queries without customer
   row output. Remove DDL membership, set temporary login NOLOGIN/revoke rds_iam,
   finish runner cleanup, preserve evidence/snapshot.
8. Separately review/update hardened runtime IAM and release policy/template to the
   verified Linux hash. Upload that unchanged ZIP only after upload approval, verify
   checksum/encryption/exact S3 VersionId, then prepare/review code UPDATE change set.
9. Approve code update with concurrency 0/triggers unwired; verify CodeSha256, version,
   handler/config/IAM and no new triggers. A real invocation cannot succeed with
   concurrency 0: static checks are not a smoke test.
10. Separate approval temporarily permits minimal concurrency for a controlled smoke
    test with triggers still unwired. Specify synthetic inputs, allowed downstream
    effects/cleanup and queue-consumer readiness; no ad hoc writes. Return to 0 after
    the test. Only later approve sustained activation and then trigger wiring.

## Costs, cleanup and evidence

Lambda on-demand has no idle instance charge; requests, execution, logs and temporary
code storage are usage based. No provisioned concurrency or network endpoint standing
charge is proposed. Example capacity bound: four full 300-second calls at 512 MiB
are 600 GB-seconds plus requests and initialization/log usage; multiply by the
current af-south-1 rate before execution. Typically cents for such a short session,
not a guaranteed Free Tier entitlement. Existing RDS, managed secret and S3/KMS
charges continue. Snapshot storage and any restore instance are the material added
cost risks. No credits were consumed by a deployed runner because none exists.
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[RDS backup pricing](https://aws.amazon.com/rds/postgresql/pricing/).

Cleanup order: reconcile outcome; revoke migration owner's temporary membership,
NOLOGIN/revoke IAM auth and drop the temporary DB login only after checking it owns
nothing; disable runner; delete its approved function/versions; wait for managed
VPC ENI cleanup before deleting execution-role permissions/role. Lambda may need
up to 20 minutes for ENI cleanup; do not manually remove shared ENIs. Remove controller
secret/invoke permissions, approved temporary runner artifact, then retain sanitized
14-day logs/evidence or delete on separate approval. Never DROP OWNED CASCADE, delete
existing subnets/SGs/DB or remove the persistent narrow NOLOGIN owner. Snapshot
cleanup needs its own approved retention decision. Residual logs, snapshot and code
objects can retain usage costs even after the runner is gone.

Evidence filenames planned below must not be populated with fabricated success:

| Directory | Files and contents |
|---|---|
| docs/EVIDENCE/05-rds/ | `11-private-preflight-catalog.json`, `12-private-preflight-counts.json`: version/TLS/owners/ACLs/schema/aggregate-only results, request IDs and script hashes |
| same | `13-pre-identity-backup.json`: approved snapshot available and restore settings; `14-migration-execution.json`: mode/hash/request ID/SQLSTATE/transaction outcome, no SQL parameters or credentials |
| same | `15-post-migration-catalog.json`, `16-row-count-comparison.json`, `17-migration-rerun.json`: exact checks/indexes, counts and approved idempotent rerun result |
| same | `18-migration-runner-cleanup.json`: DB-role membership removal, function/role/ENI and retained snapshot/log disposition |
| docs/EVIDENCE/12-e2e/ | `01-hardened-schema-compatibility.json`, `02-hardened-release-binding.json`, `03-controlled-smoke.json`: live role checks/read compatibility, artifact/version binding and separately approved smoke evidence |

Current actual evidence is only metadata JSON and local preflight test results in
`docs/EVIDENCE/05-rds/private-migration-path/`. Production SQL is unchanged. The two
preflight scripts and local tests are preparation, not an executable AWS runner.
Review-ready is not execution-ready: the next user decision is approval of the
no-new-endpoint, transient-credential read-only runner design. Live schema preflight,
bootstrap privileges, snapshot and DDL remain later explicit gates.

## Local validation result

Seven focused PostgreSQL tests passed, zero failed/skipped, in 3.10 seconds on
Windows Python 3.14.7 / PostgreSQL 18.6. Each test used an isolated schema in the
existing loopback-only fintrust_local_test database; all temporary schemas were
removed. Coverage: absent baseline, 200 legacy rows, partial identity duplicates
and atomic rollback, exact rerun/row preservation, conflicting existing types/
index definitions, invalid partial values and READ ONLY write rejection.
An initial catalog-column typo was corrected before this passing run.
These checks are not Linux/PostgreSQL 16 runner proof. The future runner must pass
that target validation separately. The application artifact SHA256 remains cf9c18a5...
and was not rebuilt. No IAM/template changes were made, so no new Access Analyzer
or CloudFormation validation is claimed. See summary.json and local-preflight-tests.xml.

For existing service roles, the future runner must also execute this read-only
privilege query after the catalog check (no rows for an absent role is a blocker):

```sql
SELECT r.rolname, c.relname,
       has_database_privilege(r.oid, current_database(), 'CONNECT') AS db_connect,
       has_schema_privilege(r.oid, n.oid, 'USAGE') AS schema_usage,
       has_table_privilege(r.oid, c.oid, 'SELECT') AS table_select,
       has_table_privilege(r.oid, c.oid, 'INSERT') AS table_insert,
       has_table_privilege(r.oid, c.oid, 'UPDATE') AS table_update,
       has_column_privilege(r.oid, c.oid, a.attnum, 'SELECT') AS account_select,
       has_column_privilege(r.oid, c.oid, a.attnum, 'UPDATE') AS account_lock_update
FROM pg_roles r
CROSS JOIN pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attname='account_id'
WHERE r.rolname IN ('fintrust_scoring_dev','fintrust_api_dev','fintrust_report_dev')
  AND n.nspname='public' AND c.relkind='r'
ORDER BY r.rolname, c.relname;
```

Check `has_sequence_privilege` for scoring's risk_events_risk_event_id_seq USAGE.
The catalog ACL/membership report must also confirm these runtime roles lack
ownership, broad inherited administration, and schema CREATE. Only a later live
connection under each exact IAM login proves its authentication and effective
query privileges; owner impersonation in local CI does not prove RDS IAM login.

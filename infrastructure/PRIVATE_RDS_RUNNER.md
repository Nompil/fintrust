# Temporary private RDS runner — LOCAL PREPARATION ONLY

Continues approved design commit `24ef12eeac07a12801e96672dd4941f8a9b9e716`.
No AWS resources/policies were changed; no live secret was retrieved and no live
SQL was executed. This is not permission to deploy. The application ZIP remains
`cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654`.

## Current gate

**PRIVATE RDS MIGRATION RUNNER CI FAILED** at the remaining schema-CREATE
boundary. [Latest CI 37898074673](https://github.com/Nompil/fintrust/actions/runs/37898074673),
source `ab0a70e30606378f15b1662f2af804592e8499e7`, used Ubuntu 24.04 x86_64,
Python 3.12.15 and disposable PostgreSQL 16.15. **446 tests passed, 0 failed,
0 skipped**. Local focused checks: 60 passed; following ACL correction: 15
infrastructure checks passed.

The separate rehearsal reproduced the original invalid ADMIN self-grant, then
successfully completed corrected bootstrap under the non-superuser creator.
It proved migration delegation denial, DDL denial without SET ROLE, unrelated
DDL/schema CREATE denial and SQL-failure rollback. It subsequently failed running
the fixed migration with `permission denied for schema public`: index creation
requires CREATE on the containing schema. Cleanup and migration rerun were not
reached in this run; they are not claimed verified.

The owner currently lacks schema CREATE intentionally. Granting it would permit
unrelated object creation as well, conflicting with the approved restriction.
No permission was broadened. A separately reviewed narrow index-creation design
is required, such as a temporary fixed, parameterless SECURITY DEFINER helper
with qualified object names, trusted search_path, exclusive invocation by the
migration login, no PUBLIC EXECUTE, exact index-definition checks and administrator
cleanup. That alternative is only a proposal, not implemented or verified.

The gate remains blocking, with the unchanged privilege rehearsal still required.
Runner packaging/import stages were not reached; neither verification flag is
true. No AWS account access occurred and the application ZIP remains unchanged.
[Evidence summary](../docs/EVIDENCE/05-rds/migration-runner-ci/37898074673/summary.json)
records exactly which assertions completed and which gates did not.

The user accepted reuse of the existing app SG, including its S3/DynamoDB HTTPS
prefix-list egress. No dedicated replacement runner SG or DB SG modification is
approved. The temporary HTTPS client SG supplies the endpoint path without
removing existing app SG allows. The VPC has no NAT/general internet route;
runtime IAM receives no unnecessary S3/DynamoDB application-data permissions;
Secrets Manager IAM and endpoint policies retain exact bootstrap scope. The
runner and temporary privileges must be removed afterward. This is an accepted
network tradeoff, **not strict endpoint-and-DB-only network isolation**.

Local verification: **59 focused tests passed (0 skipped)**; **443 regression tests
passed, 1 skipped**. The skipped existing service-role test requires a disposable
PostgreSQL administrator; no local administrator access was requested or broadened.
New isolated test schemas were removed. Four candidate archives passed static
layout/ELF/ABI/source-binding checks; actual Linux imports and PG16 role rehearsal
remain unexecuted. Full results and exact four artifact hashes are in the local
[summary](../docs/EVIDENCE/05-rds/migration-runner-local/summary.json).

## Implementation and phase separation

`migration_runner/` is independent of all permanent application handlers.
Each version receives only `{ "operation": "preflight", "request_id": "<UUID>" }`.
Extra fields, unknown operations, credentials, SQL text, paths, hostnames and
arbitrary parameters are rejected before credential retrieval. Fixed targets:
`fintrust-ledger-dev.cv84aee6u6up.af-south-1.rds.amazonaws.com:5432`, DB `fintrust`.

| Archive/handler module | Allowed operations | Credential |
|---|---|---|
| fintrust-migration-preflight.zip / preflight_entry | preflight only | Master secret, read-only SQL |
| fintrust-migration-bootstrap.zip / bootstrap_entry | bootstrap only | Master secret, separate approval |
| fintrust-migration-iam.zip / iam_entry | preflight, migrate, verify, cleanup-check | fintrust_migrate_dev IAM token |
| fintrust-migration-cleanup.zip / cleanup_entry | cleanup only | Master secret, separate cleanup approval |

Handler suffix is `.lambda_handler`; runtime Python 3.12/x86_64, 512 MiB, timeout
300s. No event mappings, URL, async configuration, DLQ, tracing or provisioned
concurrency. Every prepared template has reserved concurrency **0**. Invokes must
be synchronous, qualified to a reviewed published version, without LogType=Tail.
A later approval must separately authorize temporary concurrency 1 and its exact
invocation; do not replay automatically after a timeout or commit ambiguity.

The IAM archive excludes `admin.py`, all administrator entry points and bootstrap
SQL. Administrator archives include only their own phase SQL. A Lambda execution
role is shared across versions, so a policy change alone does not isolate old
versions: revoke qualified invoke grants, stop concurrency, drain invocations and
remove old versions before re-enabling master-secret access for final cleanup.

### Connections, preflight and atomic migration

All production connections pin `sslmode=verify-full`, bundled RDS CA, hostname,
port and database; connect timeout 5s, statement timeout 15s, lock timeout 2s,
idle-in-transaction timeout 30s. A session check requires PostgreSQL **16.x**, the
expected session user/database and `pg_stat_ssl.ssl=true`. No local-test fallback
is shipped. Local tests substitute only their isolated schema/role/target guards.

The existing catalog and aggregate preflight SQL is integrated into a runner-owned
REPEATABLE READ / READ ONLY transaction. Results identify missing base, absent,
partial, correct or conflicting migration; count duplicates/invalid values and
legacy rows. Missing/unsafe base tables skip the data query. Only counts and
catalog metadata leave the DB. Defaults, CHECK/index SQL and other potentially
sensitive expressions are hashed before output; table/column ACL metadata is reported; names/types/owners/memberships are
metadata. No row samples, customer identifiers or raw exception messages leave.
Use the known canonical SQL to compare definition hashes; do not log raw catalogs.
A successful preflight means the read completed; its assessment may still block DDL.

Only the source-hash-bound `sql/migrations/001_transaction_identity.sql` is supported.
The existing file is unchanged. The runner removes its fixed BEGIN/COMMIT wrappers
and owns the transaction: SET LOCAL ROLE narrow owner, lock transactions ACCESS
EXCLUSIVE, assess existing definitions/data, execute fixed DDL, check exact columns,
validated CHECK definitions and complete unique/nonunique index definitions, then
compare transaction row counts before commit. It rejects unsafe partial inline
constraints instead of assuming ADD COLUMN IF NOT EXISTS repairs them. Failed
checks roll back all DDL. A failed commit is `commit_outcome_unknown`, never success
or an automatic retry. Review live evidence before retrying.

### Credential lifecycle and PostgreSQL privileges

Administrator phases call GetSecretValue directly through the proposed endpoint,
for the exact RDS-managed secret in the approved design, VersionStage=AWSCURRENT.
Returned ARN/username/stage are checked. The password is used only in request-local
memory and the closed DB connection. No event/env/file/global cache or response
contains it. Reference release is not claimed as secure Python zeroization.

The IAM phase locally signs a 900-second token with Lambda-provided execution-role
credentials. The signer was tested with dummy credentials and network blocked.
No SDK AssumeRole or secret fetch is needed. The DB connection verifies the exact
login, rds_iam membership and absence of superuser/CREATEROLE/CREATEDB/BYPASSRLS/
automatic inheritance. This does not prove real RDS IAM authentication before the
separately approved live handshake.

`sql/bootstrap/temporary_identity.sql` refuses existing maintenance roles or
unexpected table ownership. It creates passwordless `fintrust_migrate_dev` with
NOINHERIT, no administration attributes and connection limit 1; grants rds_iam,
CONNECT, schema USAGE and SELECT on transactions for identity checks. The five
other tables grant SELECT only on their primary-key column, sufficient for COUNT(*).
Only `public.transactions` changes owner to persistent NOLOGIN
`fintrust_transactions_owner`. Temporary schema CREATE for ownership transfer is
revoked in the same transaction. Migration membership has SET TRUE, INHERIT FALSE,
ADMIN FALSE. The owner receives SELECT only on the primary-key column of the five other tables
for fixed aggregate postchecks, removed at cleanup. Ownership necessarily conveys broad DDL and the
ability to regrant table privileges; it cannot be reduced to one ALTER operation
with GRANT. Fixed signed code, phase IAM, qualified invocation and review are controls.

PostgreSQL 16 role-creator administration matters: the master retains the automatically supplied creator ADMIN membership
but SET FALSE/INHERIT FALSE on the new owner so it can manage cleanup membership.
The temporary login never gets ADMIN or master/rds_superuser membership. The
master's owner SET capability is briefly restored in the fixed cleanup transaction
to revoke the transactions SELECT grant as its post-transfer grantor, then removed.
This avoids assuming table ownership/ACL grantor rules disappear after transfer.

`remove_temporary_identity.sql` refuses active migration sessions or unexpected
owned relations, sets NOLOGIN, revokes memberships and exact grants, and drops only
the migration login. Other dependencies make DROP ROLE fail and roll back. Never
DROP OWNED/CASCADE or remove the permanent owner, data, application roles or secret.
The CI-only PG16 rehearsal exercises bootstrap -> owner-authenticated DDL/rerun ->
cleanup as a nonsuperuser CREATEROLE administrator. Its local rds_iam stand-in tests
SQL membership, not AWS's authentication implementation.

## Networking and resource counts

Offline renderer: `python -m infrastructure.migration`.

- Network stack: **fintrust-migration-network-dev**, 4 resources: EndpointSecurityGroup
  (EC2 SG), ClientSecurityGroup (EC2 SG), EndpointIngress (SG ingress), SecretsEndpoint
  (Interface VPCE for `com.amazonaws.af-south-1.secretsmanager`).
- Existing VPC `vpc-0aba008bb360f5147`; runner and endpoint use ONLY
  `subnet-0c2d87e8a83361e30` / af-south-1a. No second subnet is implicit. Private DNS
  enabled. If this AZ cannot be used, stop; a two-AZ change needs review/cost update.
- Client SG only adds TCP443 to endpoint SG. Endpoint ingress accepts TCP443 only
  from client SG. Endpoint SG has AWS's localhost-only egress placeholder to suppress
  EC2's automatic allow-all rule; responses are stateful. It is not a public route.
  [CloudFormation default-egress semantics](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-securitygroup.html).
- Runner also uses existing app SG `sg-0850bd798bb9505e2` to reach existing DB SG
  `sg-01644a4c9f2c44162` on5432. Existing app/DB rules are not modified. The extra
  existing service-prefix routes and strict-egress review item are described above.
- Runner stack: **fintrust-migration-runner-dev**, 3 resources: RunnerLogs (14-day
  log group, Retain), Runner (Lambda), RunnerVersion (qualified version + CodeSha256).
  Execution IAM role/boundary are separate administrator bootstrap, not CFN resources.
  This preserves `--resource-types` restriction without conflicting NAMED_IAM capabilities.
- No NAT/public IP, RDS change, KMS endpoint, S3 bucket, new secret or trigger.

## IAM review documents

Generated under `build/migration-runner/review/`; canonical source is
`infrastructure/migration.py`. They are proposals, not Access Analyzer/live-verified.

1. `FinTrustMigrationBoundary`: administrator-created managed maximum-permissions
   boundary. Exact secret through actual endpoint + AWSCURRENT, exact DB user connect,
   exact log streams; required Lambda ENI actions. No runtime secret writes or app
   S3/SQS/DynamoDB access. No explicit KMS decrypt for the existing AWS-managed
   Secrets Manager key; stop if metadata changes to a customer key.
2. `fintrust-migration-dev` role: Lambda trust only, mandatory boundary. Its inline
   `FinTrustMigrationRuntime` is generated separately per phase. IAM phase explicitly
   denies master GetSecretValue; administrator phases have no rds-db:connect grant.
   Both identity and endpoint policies restrict exact secret; actual endpoint ID
   must replace the review sentinel before any attachment.
3. ENI actions CreateNetworkInterface, DescribeNetworkInterfaces, DescribeSubnets,
   DeleteNetworkInterface, AssignPrivateIpAddresses, UnassignPrivateIpAddresses use
   region-limited Resource=* per Lambda's contract. Matching Deny when
   lambda:SourceFunctionArn is this runner prevents code from using service ENI rights.
4. `FinTrustMigrationDeployment`: scoped two-stack CFN, exact function/log/PassRole,
   owned temporary SG/endpoint operations, required regional reads. No Invoke,
   upload, DB lifecycle, IAM role/boundary management or application policy edits.
   Use a separately approved operator role: the Stage 1 deployer's explicit endpoint
   attachment Deny must not be weakened or bypassed by adding Allow statements.
5. `FinTrustMigrationBootstrap`: administrator-only review specification for the
   named boundary/role and inline policy lifecycle. IAM cannot inspect the supplied
   policy/trust JSON for least privilege; administrator content review is mandatory.
   Keep this off the deployer role. It cannot edit boundary versions or remove the
   role's permissions boundary. No workload region restriction is misapplied to
   these global IAM bootstrap operations.
6. Package-read addendum: `artifact_policy(sha, version, phase)` binds exact S3 object
   and VersionId, plus exact S3 KMS key via S3. S3 Bucket Keys require bucket-context
   decryption scope; the exact versioned S3 grant restricts accessible code objects.
   This is deployer code-download permission, not runner secret-decryption permission.
7. Controller InvokeFunction permission must name only the approved numeric qualified
   version. No broad function ARN or wildcard versions. No controller GetSecretValue.

Templates are read-only rendered locally, with no policy attachments, AWS validation
calls or deployment. An Access Analyzer and CloudFormation validation checkpoint
remains before AWS execution. Do not infer effective provider authorization from
static policy tests; preserve the earlier Stage 5 lessons.

## Artifact and validation workflow

Four separate archives, source bindings, sizes, hex/Base64 hashes and target flags
are recorded in `docs/EVIDENCE/05-rds/migration-runner-local/summary.json`.
Current builds reuse only pinned production dependency files from the already
verified application ZIP, read-only. No application code is copied. psycopg2-binary
2.9.13 supplies the CPython312 extension and bundled libpq; ELF64/x86_64 and all
archive paths/source hashes are checked. Windows .pyd/.dll and application modules
are rejected. New ZIPs have **linux_execution_verified=false** until real imports.

`.github/workflows/migration-runner.yml` is manual only and has no AWS credentials,
OIDC or deployment steps. After separate push/run approval it installs pinned deps,
runs full tests on PostgreSQL16, exercises actual role/ownership cleanup semantics,
builds only migration archives, imports actual extracted ZIPs on Linux3.12 and in
the Lambda3.12 image with networking disabled, then records green target flags.
Image digest is recorded. Failed tests/role checks/imports cannot publish a verified
artifact. CI-built hashes may differ; review/bind the actual green CI ZIP, never
substitute the local candidate's hash or existing application's green result.

## Exact future approval sequence — commands are NOT executed

First obtain Linux/PG16 gate evidence and resolve the SG egress review item. Refresh
inventory metadata (identity, secret ARN/key, RDS state, subnet/AZ/IP/DNS/NACLs, SGs,
endpoint absence) without GetSecretValue. Finalize endpoint/IAM/template validation.

1. Review network change set named `fintrust-migration-network-review` for only the
   four additions above. Separate approval to execute; record endpoint and client SG
   IDs. No Lambda invocation or DB change belongs in this step.
2. Bind actual endpoint ID locally:
   `python -m infrastructure.migration --endpoint-id <verified-vpce-id>`.
   Administrator reviews/creates FinTrustMigrationBoundary from boundary-review.json,
   role from execution-trust.json with that permissions boundary and Project/Environment/
   Purpose tags, and preflight-runtime-policy-review.json as FinTrustMigrationRuntime.
   Inspect effective role/boundary; attach scoped deployment and exact artifact-read
   permissions only after review. No policy version broadening.
3. After explicit upload approval, upload only the green CI preflight ZIP at
   `deployment/migration/<sha256>/fintrust-migration-preflight.zip` in the existing
   reports bucket, SSE-KMS using the existing S3 key. Verify VersionId, checksum,
   encryption and source binding; generate exact `artifact_policy` addendum.
4. Create `fintrust-migration-runner-preflight-review` on fintrust-migration-runner-dev
   from preflight-template.json. Required parameters are EndpointId, ClientSecurityGroupId,
   CodeKey, CodeObjectVersion and CodeSha256 (Base64); no default artifact version.
   Use only resource types AWS::Lambda::Function AWS::Lambda::Version AWS::Logs::LogGroup,
   and Project=FinTrust Environment=dev Purpose=temporary-migration tags. Review exactly
   three additions and disabled concurrency; separate execution approval.
5. Separately approve one qualified, synchronous preflight invocation and temporary
   concurrency1. Immediately return concurrency0 after it completes. Save only
   sanitized JSON result. **STOP FOR REVIEW.** No snapshot, role creation or DDL yet.
6. If live catalog/data agree with the design, separately approve snapshot and wait
   until available. Review its cost/retention. Approve bootstrap archive/version and
   fixed role/ownership SQL; unknown existing roles/owners stop rather than adapt.
7. Close master sessions, disable/drain Lambda, remove old qualified invoke grants
   and administrator versions; replace runtime policy with IAM phase (explicit
   master-secret Deny), deploy separately verified IAM archive and publish version.
   Prove denied master access using authorization metadata/simulation, never by
   fetching a secret for a negative test. Approve IAM handshake/DDL/verification
   separately, review counts/definitions, then disable concurrency again.
8. For final admin cleanup: drain/remove IAM version and invoke grants BEFORE master
   access returns. Approve fixed cleanup archive/version + endpoint-bound master
   policy, run once, check revocation/drop, remove Allow/restore Deny and disable.
9. Delete approved runner stack/function/versions; retain sanitized14-day logs under
   policy. Wait for managed Lambda ENIs before deleting its role/boundary. Delete
   temporary endpoint/network stack, confirm endpoint ENI removal and SG removal.
   Remove temporary controller/deployer/bootstrap policies and code versions by exact
   reviewed identifier. Preserve the RDS-managed secret/rotation, permanent owner,
   all application infrastructure, historical application artifact and evidence.
10. Hardened application upload/deployment/activation remains a separate release.

## Cost and recovery

One endpoint AZ costs $0.01309/hour: four hours $0.05236, 24h $0.31416, 730h $9.55570,
plus $0.01/GB first-PB processing, Lambda/log/API usage and applicable transfer/taxes.
Two endpoint AZs would double the standing component. Existing RDS/secret/S3/KMS
costs continue. Snapshot/restore costs need separate approval. No free-credit
coverage or automatic spending cap is assumed. Delete the endpoint after the bounded
session; keep it only if explicit recovery needs justify continued hourly cost.

A failed CREATE can leave the Retain log group; inspect physical existence, data,
tags and ownership before administrator-approved cleanup/reuse. ROLLBACK_COMPLETE
requires reviewed stack deletion before fresh CREATE with the same stack name.
Do not delete unverified leftovers automatically. Never delete shared ENIs; keep
execution-role ENI permissions until Lambda finishes cleanup. Data DDL failures
roll back; uncertain commit/network timeouts require read-only reconciliation,
not blind retry. Role/drop cleanup failure rolls back and needs catalog review.
No cleanup helper auto-deletes AWS resources or shuts down existing RDS.

## PostgreSQL 16 creator-grant correction (CI rerun pending)

The first failing statement was:
`GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN TRUE`.
A non-superuser CREATEROLE creator already receives a bootstrap-superuser grant
with ADMIN TRUE, SET FALSE, INHERIT FALSE. The explicit self-grant attempted to
add a circular administrator delegation; PostgreSQL 16 rejected it. All four
owner-to-administrator SET toggles (bootstrap and cleanup) now specify ADMIN FALSE.
The existing bootstrap-superuser administration edge is retained for the creator
so it can grant/revoke memberships and drop its temporary role; no new ADMIN
option is delegated. The migration login never receives ADMIN or CREATEROLE.

Role graph, expressed as `grantor -> granted role -> member`:

| Phase | Edge | ADMIN / INHERIT / SET |
|---|---|---|
| Automatic on owner creation | bootstrap superuser -> fintrust_transactions_owner -> fintrust_admin | true / false / false |
| Automatic on login creation | bootstrap superuser -> fintrust_migrate_dev -> fintrust_admin | true / false / false |
| Bootstrap | fintrust_admin -> rds_iam -> fintrust_migrate_dev | false / false / true (NOINHERIT login default) |
| Bootstrap, before ownership transfer | fintrust_admin -> fintrust_transactions_owner -> fintrust_admin | false / false / true |
| Bootstrap, migration access | fintrust_admin -> fintrust_transactions_owner -> fintrust_migrate_dev | false / false / true |
| Bootstrap, disable master SET path | fintrust_admin -> fintrust_transactions_owner -> fintrust_admin | false / false / false |
| Cleanup, temporary master SET path | fintrust_admin -> fintrust_transactions_owner -> fintrust_admin | false / false / true |
| Cleanup, restore master SET restriction | fintrust_admin -> fintrust_transactions_owner -> fintrust_admin | false / false / false |

The existing application/runtime roles receive no membership from this correction.
SET ROLE to the non-login owner is required for migration DDL and fixed index
creation; it does not authorize unrelated table DDL or schema CREATE. Table
ownership inherently permits management of the transactions table; it is not a
column-level DDL sandbox. Cleanup revokes both login memberships, ACLs and CONNECT,
then drops the temporary login. The original administrator keeps its creator
administration edge; cleanup does not pretend to deprivilege the existing master.

The CI rehearsal explicitly reproduces the original invalid grant in a savepoint,
then runs the corrected SQL under a non-superuser creator. It checks no onward
delegation, denial of DDL before SET ROLE, unrelated DDL/schema CREATE denials,
transactional rollback, two migration executions and partial indexes, 200 rows,
login removal, master SET removal and unchanged runtime-probe permissions.
Vanilla PostgreSQL role membership does not prove RDS IAM authentication.

References: [PostgreSQL 16 role attributes](https://www.postgresql.org/docs/16/role-attributes.html)
and [GRANT](https://www.postgresql.org/docs/16/sql-grant.html).

The first corrected rerun, 37896426512, reproduced the original ADMIN failure
successfully and progressed through corrected membership grants. It then exposed
`permission denied for table transactions` within bootstrap: the post-transfer
REVOKE still ran as the NOINHERIT administrator. Bootstrap now explicitly uses
SET LOCAL ROLE to the new owner for that existing ACL operation and RESET ROLE
before continuing role administration. No new privilege is granted. Ownership
still inherently permits the owner to regrant DML; the REVOKE is not a DML sandbox.

### Remaining schema CREATE boundary

CI 37898074673 passed corrected bootstrap and the isolation/rollback assertions,
then failed before migration completion. PostgreSQL 16 index creation explicitly
checks CREATE on the table namespace, in addition to ownership:
[PostgreSQL 16 indexcmds.c](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/backend/commands/indexcmds.c).
The owner-role grant alone is insufficient. Keeping schema CREATE revoked means
this exact migration cannot yet complete; granting it would also allow unrelated
schema objects. No migration ZIPs are verified, no cleanup completion is claimed,
and no AWS operation is approved. Resolve the scoped index path before a new CI run.

## Fixed index capability implementation (target CI pending)

| Option | Capability exposed to migration login | Recovery/audit | Decision |
|---|---|---|---|
| Temporary schema CREATE on login | Any object creation in public during the grant | Simple revoke, but unrelated DDL becomes possible | Rejected |
| SET ROLE into schema-privileged owner | Same broad schema capability through membership | Extra role cleanup does not restrict what caller can execute | Rejected |
| Parameterless SECURITY DEFINER helper | Only the two fixed index statements through EXECUTE | Transactional DDL, explicit function/role cleanup; more code to review | Selected |

All three use supported PostgreSQL 16 features. The selected mechanism does not
require superuser or RDS extensions; actual RDS identity/TLS/IAM behaviour still
requires separately approved live preflight. No AWS operation is approved here.

`fintrust_index_builder` is NOLOGIN, NOINHERIT, NOSUPERUSER, NOCREATEDB,
NOCREATEROLE, NOREPLICATION and NOBYPASSRLS. It holds schema USAGE/CREATE and
inherits only `fintrust_transactions_owner` for the index ownership check.
Schema CREATE itself is not index-specific: isolation comes from **no membership
or SET access for the migration login**, and a fixed definer function. The role
is not accessible by application roles. The existing bootstrap administrator has
the automatic creator ADMIN edge, and toggles its own non-admin SET edge solely
for transferring function ownership/ACLs and cleanup.

`public.fintrust_create_identity_indexes()` takes zero arguments and has
`search_path=pg_catalog,pg_temp`. PUBLIC execution is revoked in the bootstrap
transaction; the only caller grant is to `fintrust_migrate_dev`. Unexpected default
function grants fail bootstrap. It verifies session/database/definer identity,
locks public.transactions, checks heap/table ownership/RLS/triggers and built-in
indexed column types/collations, and rejects conflicting existing index names or
definitions. No dynamic SQL is used. The two CREATE INDEX statements are compared
to the canonical migration in tests. The function drops itself after creating or
accepting the exact indexes; postcheck failure rolls back that DROP as well.

The canonical `001_transaction_identity.sql` is **unchanged**. The runner checks
its existing SHA256, splits at its fixed index section, runs column/check DDL as
the transaction owner, resets to the login to call the helper, then SETs the owner
for exact-definition/count postchecks. This is explicit privilege orchestration,
not omission of index statements. No CREATE INDEX CONCURRENTLY is used. A fully
verified rerun is a no-op because successful execution removed the helper. An
incorrect/partial state never bypasses preflight checks. All column/index DDL,
helper self-removal and postchecks share one caller transaction.

Administrator cleanup drops a restored helper after an aborted transaction,
revokes helper schema/membership grants, drops the helper role, revokes migration
memberships/ACLs and drops the login. The permanent NOLOGIN transaction owner
remains. No objects should be owned by either disposable login/helper role after
cleanup; indexes remain owned by the transaction table owner.

Local focused suite: 63 passed, 0 failed/skipped. Exact PostgreSQL 16 privilege
checks run first in the same CI workflow, then the complete regression, four
archive builds and Linux import gates. No check was removed. The authoritative
flags remain false until that run completes. Next after green: **business-rule /
schema freeze**, not AWS execution or live migration.

See [PostgreSQL SECURITY DEFINER guidance](https://www.postgresql.org/docs/16/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).

The hostile-temp-name rehearsal exposed an implicit PostgreSQL pg_temp search-path
priority in the transaction setup (run 37929161604). The runner now explicitly
places pg_temp last: pg_catalog, public, pg_temp. The helper already used a pinned
path and fully qualified public.transactions. The temp-shadow test is retained.

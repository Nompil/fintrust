> CI continuation: approved source `2fb8ec4` was pushed and manual runner CI
> [37895291574](https://github.com/Nompil/fintrust/actions/runs/37895291574) ran.
> Regression: 444 passed, 0 failed, 0 skipped on Linux/Python 3.12/PostgreSQL 16.15.
> Exact bootstrap privilege rehearsal failed with `ADMIN option cannot be granted
> back to your own grantor`; packaging and Linux imports did not run. AWS execution
> remains blocked. Existing app SG egress is an accepted documented tradeoff;
> no dedicated replacement SG or DB SG changes are approved. See PRIVATE_RDS_RUNNER.md.

# Private RDS migration path - secure bootstrap ready for review

Status: **PRIVATE RDS BOOTSTRAP PATH READY FOR REVIEW**. This is a design and
read-only preflight preparation checkpoint, not authorization to deploy or execute.
This revision supersedes commit 78b2ceb's controller-to-Lambda password-payload
proposal: that handoff is now explicitly prohibited. A temporary Secrets Manager
interface endpoint is proposed instead and needs cost/security approval.
Local implementation now exists; see [runner checkpoint](PRIVATE_RDS_RUNNER.md).
Its separate ZIPs are not yet Linux/PG16 execution-verified. No runner is deployed
or invoked. No live SQL, secret retrieval, snapshot, IAM/network mutation or
application deployment occurred. The original design below remains subject to
the implementation checkpoint and its SG-egress review item.
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
instead. Add a separate temporary HTTPS client SG and endpoint SG as described
below. No DB ingress change is needed. Recheck NACLs, subnet capacity and DNS
attributes during runner implementation; SGs/routes alone do not prove a DB handshake.

## Alternatives

| Approach | Reachability, credentials, TLS, cost and suitability |
|---|---|
| A. Temporary Secrets Manager endpoint + dedicated Lambda - preferred | Direct private HTTPS secret retrieval, then verified PostgreSQL TLS. Adds one interface endpoint in one AZ and two narrowly scoped SGs; no NAT/public ingress. Fixed operations, exact secret IAM and endpoint policy, read-only first. Endpoint hourly/data charges plus small Lambda/log/API usage; remove after the bounded bootstrap/migration/admin-cleanup session. |
| B. Reuse application Lambda - reject | Only ingest exists and it is outside VPC. Adding network access, DDL credentials and a migration mode would expand its role and alter reviewed runtime/package boundaries. Future scoring role must not own tables. Lambda cost remains small but cleanup/rollback and audit separation worsen. |
| C. EC2 + SSM - reject for this task | Could reach RDS with app SG, TLS and IAM DB token or secret. No runner exists. Private SSM control needs endpoints (ssm/ssmmessages and any applicable region/agent dependencies) or network egress. Adds instance/EBS, agent/IAM, endpoint charges, OS maintenance and cleanup; conflicts with the current no-NAT/no-interface-endpoint plan. |
| D. Default CloudShell/local laptop - reject direct access | Neither has a route into this VPC. Public RDS, broad ingress or improvised tunnels are unacceptable. TLS and an IAM token cannot create a network route. |
| D2. CloudShell VPC environment - not selected | Can reach private RDS when configured for this VPC; however it has the same missing Secrets Manager route. Under the no-secret-payload/history rule it still needs the temporary interface endpoint unless an IAM DB login already exists. Ephemeral tools, interactive administration and credential handling add complexity. Its free compute does not solve bootstrap or eliminate endpoint cost. |
| E. RDS Data API - not applicable | This instance is standard RDS PostgreSQL, not an Aurora Data API cluster. No HTTP SQL path exists for it; changing to Aurora is an unnecessary architecture/cost change. |
| A2. Outside-VPC controller + private runner - orchestration only | Controller sends a nonsecret operation/request ID and invokes the approved runner version; it has no GetSecretValue permission. Supplying the master password/token in the event is rejected. A controller reaching Secrets Manager does not bridge the private runner network. Staging an encrypted secret in S3/SSM/Lambda configuration creates another credential copy and is not selected. |
| F. Existing repo SQL/local tools | Canonical SQL and local tests are useful inputs, not a network bridge. `tools/local.py` deliberately restricts itself to loopback practice databases. The untracked `infrastructure/rds/schema.sql` is not adopted; do not execute it. |

Sources: [Lambda VPC](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html),
[SSM private connectivity](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html),
[CloudShell VPC](https://docs.aws.amazon.com/cloudshell/latest/userguide/using-cshell-in-vpc.html),
[Data API scope](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/data-api.html).

## Selected architecture and credential bootstrap

Metadata-only checks on 2026-10-09 establish the exact relationship:

- DB ARN: `arn:aws:rds:af-south-1:966467878406:db:fintrust-ledger-dev`.
- Master username: `fintrust_admin`; RDS MasterUserSecret status active.
- Secret ARN: `arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn`.
- DescribeSecret reports OwningService=rds, rotation enabled and
  aws:rds:primaryDBInstanceArn pointing to that exact DB. No secret value was read.
- Secret encryption key: `arn:aws:kms:af-south-1:966467878406:key/c68acc77-115b-4da5-80be-9ea69291da19`,
  Enabled, KeyManager=AWS, default Secrets Manager key. DescribeSecret's null
  KmsKeyId is expected for aws/secretsmanager; it does not mean unencrypted.
  This is distinct from the DB storage key and the customer-managed S3 key.
- Only S3 and DynamoDB gateways exist. They do not route Secrets Manager traffic.
  The recorded app routes have no default egress and app SG permits HTTPS only
  to those service prefix lists. Current placement cannot retrieve the secret.
- DNS support and DNS hostnames are enabled. Secrets Manager's interface service
  `com.amazonaws.af-south-1.secretsmanager` is available in af-south-1a/b/c with
  private DNS `secretsmanager.af-south-1.amazonaws.com` and endpoint-policy support.

Evidence: [bootstrap metadata](../docs/EVIDENCE/05-rds/private-bootstrap-path/summary.json).
The earlier metadata/preflight evidence remains historical and unmodified.

### Exact proposed network path

Use the existing VPC `vpc-0aba008bb360f5147`. For this temporary task, select ONLY
application subnet `subnet-0c2d87e8a83361e30` (af-south-1a) for both runner and endpoint.
This deliberately trades multi-AZ availability for minimum temporary cost; if that
AZ is unavailable, stop/review rather than silently create a second endpoint ENI.
No public IP, NAT, IGW, default route or RDS accessibility change is needed.

1. Create one **Interface** endpoint for com.amazonaws.af-south-1.secretsmanager,
   IPv4, private DNS enabled, exact restricted endpoint policy below.
2. Create temporary `fintrust-migration-client-dev` SG: no inbound rules; its only
   egress is TCP 443 to the temporary endpoint SG. Explicitly remove the default
   all-egress rule in the eventual template; tags Project=FinTrust, Environment=dev.
3. Create temporary `fintrust-migration-secrets-endpoint-dev` SG: ingress TCP 443
   only from that client SG; no open egress rule is required for stateful responses.
   Ensure the final template removes default all-egress (do not assume an omitted
   property does this). No CIDR-wide permissions. Endpoint uses only this SG.
4. Runner attaches BOTH existing app SG `sg-0850bd798bb9505e2` and temporary client
   SG. Security-group permissions combine: existing 5432-to-DB connectivity remains,
   temporary client SG adds only HTTPS to endpoint ENIs. Existing app/DB SGs are
   not edited. Extra app-SG S3/DynamoDB routes do not grant IAM data permissions.
5. Regional Secrets Manager DNS resolves to the private endpoint ENI. SDK request
   goes Lambda ENI -> endpoint SG TCP443 -> PrivateLink -> Secrets Manager.
   Response is returned over the same TLS connection. Secrets Manager performs
   KMS decryption server-side; no Lambda-to-KMS endpoint or client decrypt call.
6. psycopg2 connects Lambda ENI -> existing DB SG TCP5432 -> private RDS endpoint
   with sslmode=verify-full and the bundled RDS CA. Verify NACL ephemeral-return
   rules, subnet free IPs, DNS resolution and peer certificate in the later
   approved connectivity test; endpoint existence alone is not handshake proof.

[AWS private secret access](https://docs.aws.amazon.com/secretsmanager/latest/userguide/vpc-endpoint-overview.html),
[endpoint prerequisites](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html),
[secret encryption](https://docs.aws.amazon.com/secretsmanager/latest/userguide/security-encryption.html).

### Credential lifecycle and IAM signing

The future `fintrust-migration-dev` function calls GetSecretValue itself, using
its Lambda-provided execution-role credentials and the fixed secret ARN with
VersionStage=AWSCURRENT. Validate returned ARN, nonempty credential structure and
username=fintrust_admin against pinned deployment metadata. Do not trust a
caller-supplied DB hostname or secret ARN. Keep password only in request-local
memory, pass it directly to psycopg2, close the DB connection and release references
in finally. Python does not guarantee secure memory zeroization; no such claim is made.
No global credential cache, extension cache, /tmp secret file or returned password.
Rotation can change AWSCURRENT: a failed authentication stops for reconciliation;
never print credentials or automatically repeat DDL after a connection ambiguity.

Controller sends ONLY an allowlisted operation and correlation ID to an approved
qualified function version. It neither retrieves nor forwards passwords/tokens.
Disable payload/debug/DSN logging and tracing; no async invokes, saved console test
credentials, DLQs or LogType=Tail. Catch errors and emit sanitized phase, SQLSTATE,
request ID and outcome only. Test failures and redaction with sentinel secrets
before deployment. CloudTrail/GetSecretValue metadata and sanitized DB results
provide evidence without credential contents. Explicitly reject hardcoded passwords,
Git secrets, passwords in Lambda environment (even encrypted at rest), invocation
payloads, logs/evidence, public RDS and NAT solely for migration.

IAM tokens are local SigV4 presigned connection strings valid for 15 minutes at
connection establishment. Inspection of pinned botocore 1.43.104 and an offline
check with explicit dummy credentials and HTTP/DNS/socket connects blocked proved
signing makes no AWS API request. No real token was generated or retained.
The signer needs already-available valid AWS credentials; assume-role/profile/SSO
credential discovery can require networking elsewhere. Use the credentials supplied
to Lambda, with no SDK AssumeRole or credential-provider network dependency inside
the VPC. IAM signing does not create a DB user, grant rds_iam, grant table ownership
or prove RDS authentication. Instance IAM auth is already enabled, but the live
PostgreSQL users/privileges remain unknown.
[Token use](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.Connecting.Python.html),
[required DB account](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.DBAccounts.html),
[GetSecretValue permissions](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html),
[Secrets Manager authorization conditions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_secretsmanager.html).

Initially implement a read-only-only runner version (Python 3.12/x86_64, 512 MiB,
300 seconds, one connection), precreated 14-day logs, reserved concurrency 0,
no URL/triggers/provisioned concurrency. Later approval permits temporary runner
concurrency 1 only. Application ingest remains 0 and unwired. The first live SQL
operation is the reviewed read-only preflight, not role creation or migration.
Owner/bootstrap SQL needs a separate review, snapshot and execution approval.

## Exact IAM scope for later implementation (design only)

Proposed role ARN: `arn:aws:iam::966467878406:role/fintrust-migration-dev`, trusted
only by lambda.amazonaws.com for sts:AssumeRole. No controller GetSecretValue grant.
The endpoint ID is not yet allocated: `__APPROVED_SECRETS_VPCE_ID__` below MUST become
the created stack's verified endpoint Ref, never `*` or StringEqualsIfExists.
These JSON statements are review specifications, not attached policy files.

Bootstrap-only execution-role statement:

```json
{
  "Sid": "ReadOnlyRdsMasterThroughTemporaryEndpoint",
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "af-south-1",
      "aws:SourceVpce": "__APPROVED_SECRETS_VPCE_ID__",
      "secretsmanager:VersionStage": "AWSCURRENT"
    }
  }
}
```

The runner needs no DescribeSecret/RDS API call: the operator verifies metadata
read-only outside the VPC and binds nonsecret configuration. Endpoint policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "OnlyMigrationRoleAndMasterSecret",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "secretsmanager:GetSecretValue",
    "Resource": "arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn",
    "Condition": {
      "ArnEquals": {"aws:PrincipalArn": "arn:aws:iam::966467878406:role/fintrust-migration-dev"}
    }
  }]
}
```

Principal=* is constrained to the exact role by aws:PrincipalArn; this endpoint
policy does not independently grant the role secret access. Both policy layers
must permit it; existing SCPs/boundaries/explicit denies must also be checked.
No resource-policy mutation on the RDS-managed secret is proposed. The current
AWS-managed Secrets Manager key requires no additional customer-key policy or
explicit kms:Decrypt grant in this design; no broad KMS grant is added. If future
metadata indicates a customer-managed key, stop and separately scope decrypt to
that key, via Secrets Manager and the exact SecretARN encryption context.

Base execution permissions retained across phases:

- logs:CreateLogStream and logs:PutLogEvents only on
  `arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-migration-dev:log-stream:*`,
  region af-south-1; precreated group avoids CreateLogGroup in runtime.
- ec2:CreateNetworkInterface, ec2:DescribeNetworkInterfaces, ec2:DescribeSubnets,
  ec2:DeleteNetworkInterface, ec2:AssignPrivateIpAddresses,
  ec2:UnassignPrivateIpAddresses on Resource=* with RequestedRegion=af-south-1,
  per Lambda's documented VPC permission contract. Add an explicit Deny for these
  actions when lambda:SourceFunctionArn equals
  `arn:aws:lambda:af-south-1:966467878406:function:fintrust-migration-dev`, preventing
  function code from using service ENI permissions. No unproven CalledVia check.
- After approved DB-login provisioning, only rds-db:connect on
  `arn:aws:rds-db:af-south-1:966467878406:dbuser:db-QZ3JN4H22YOMU7VLI22RL2IUYQ/fintrust_migrate_dev`.
  Regional/account scope is in this exact ARN; no wildcard DB login/resource ID.
- No S3/SQS/DynamoDB/SSM data operations, secret writes, secret listing, rotation,
  EC2 instances, RDS lifecycle or snapshot permissions in the runner role.

Controller: lambda:InvokeFunction on the single reviewed qualified runner version
only, plus approved nonsecret status/configuration reads. Use its MFA-backed
operator session. AWS bootstrap administrator owns endpoint/SG creation and
cleanup, execution-role policy/trust provisioning and exact-function PassRole
(iam:PassedToService=lambda.amazonaws.com). Existing Stage 1 policy explicitly
denies endpoint subnet/SG attachment: do not attach an Allow and expect it to
override that Deny or weaken Stage 1. Use the separately approved bootstrap
administrator or scoped bootstrap role for the endpoint resources. Future deployer
policy must enumerate the reviewed Create/Modify/DeleteVpcEndpoint, temporary
Create/DeleteSecurityGroup, exact ingress/egress rule and tagging operations,
scoped to this VPC, service, temporary resources/tags and region where supported;
read actions use * only when AWS requires it. No such policy is generated/attached
in this documentation-only task. Its final JSON, resource dependencies and IAM
validation are a required implementation review, not implied approval here.

## Package/native dependency verification before execution

Yes: psycopg2 and its Linux native extension/libpq dependencies are required.
The project pins psycopg2-binary==2.9.13; retain that reviewed family rather than
silently switching to psycopg v3. Use direct psycopg2 connection code: importing
fintrust.db for bootstrap would conflict with the application's IAM-only policy.
Build the separate minimal runner on Linux CPython 3.12 x86_64 using compatible
manylinux wheels (not the Windows interpreter's native package). Package handler,
reviewed SQL, CA and the dependencies actually used, excluding tests/dev material.

Required later checks: inspect ELF/x86_64 and CPython ABI, import psycopg2 and
psycopg2._psycopg/libpq from the extracted exact ZIP in Linux/Python 3.12 (also use
Lambda's Python 3.12 runtime environment for OS-library compatibility), execute
read-only/migration contract tests against disposable PostgreSQL 16.15, then
certificate/hostname verification, secret-redaction and network-denial tests.
Integration tests must inject fake secret data and mock AWS transport; never pull
real secrets in CI. Confirm no credentials in ZIP/config, scan logs/output with
sentinels on every error path, hash and manifest-bind that runner ZIP. These are
future acceptance gates, not tests already performed. Existing 385-pass application
CI and its verified ZIP do not certify a new runner. Existing seven local preflight
SQL tests on PostgreSQL 18 remain useful but are not PostgreSQL 16 runner proof.

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

1. Approve this revised design and temporary endpoint cost; implement/test/review the
   separate read-only runner, endpoint/SGs, exact IAM/template/package, redaction and cleanup.
2. Approve runner infrastructure; deploy disabled, verify pinned network/package,
   verify private secret retrieval/target binding, then separately authorize one synchronous read-only preflight (temporary runner
   concurrency 1 only). Application concurrency stays 0, triggers unwired.
3. Review live catalog/counts. If baseline absent/incompatible, stop for a separate
   canonical schema/bootstrap/roles plan. Do not apply 001 to an empty database.
4. Freeze writers, approve/create/wait for snapshot and capture restore checkpoint.
5. Approve the precise owner/login/grant bootstrap if required. Provision the narrow
   IAM DB migration identity, verify TLS/privileges, remove bootstrap secret access
   from the runner once bootstrap no longer needs it (lifecycle below).
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
code storage are usage based. No provisioned concurrency is proposed. One temporary Secrets Manager endpoint
adds an hourly charge until deleted, even when the runner is idle. Example capacity bound: four full 300-second calls at 512 MiB
are 600 GB-seconds plus requests and initialization/log usage; multiply by the
current af-south-1 rate before execution. Typically cents for such a short session,
not a guaranteed Free Tier entitlement. Existing RDS, managed secret and S3/KMS
charges continue. See the exact temporary endpoint estimate below. Snapshot storage and any restore instance are the material added
cost risks. No credits were consumed by a deployed runner because none exists.
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[RDS backup pricing](https://aws.amazon.com/rds/postgresql/pricing/).

Cleanup order: reconcile outcome; revoke migration owner's temporary membership,
NOLOGIN/revoke IAM auth and drop the temporary DB login only after checking it owns
nothing; disable runner; delete its approved function/versions; wait for managed
VPC ENI cleanup before deleting execution-role permissions/role. Lambda may need
up to 20 minutes for ENI cleanup; do not manually remove shared ENIs. Remove runner bootstrap secret permissions and controller invoke permissions,
remove the temporary endpoint/SGs in the order below and the approved temporary runner artifact, then retain sanitized
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

Current actual evidence is metadata JSON and prior local preflight test results in
`docs/EVIDENCE/05-rds/private-migration-path/`, plus metadata, pricing and offline
signing checks in `docs/EVIDENCE/05-rds/private-bootstrap-path/`. Production SQL is unchanged. The two
preflight scripts and local tests are preparation, not an executable AWS runner.
Review-ready is not execution-ready: the next user decision is approval of the
temporary Secrets Manager endpoint and direct-fetch read-only runner design. Live schema preflight,
bootstrap privileges, snapshot and DDL remain later explicit gates.

## Prior local validation result (commit 78b2ceb; not rerun for this documentation change)

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

## Bootstrap role provisioning and removal of master access

After the read-only catalog is reviewed and backup approved, the fixed bootstrap
operation uses the master connection to create the passwordless login:

```sql
CREATE ROLE fintrust_migrate_dev LOGIN NOINHERIT NOSUPERUSER NOCREATEDB
  NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1;
GRANT rds_iam TO fintrust_migrate_dev;
GRANT CONNECT ON DATABASE fintrust TO fintrust_migrate_dev;
GRANT USAGE ON SCHEMA public TO fintrust_migrate_dev;
```

This is a design example, not permission to run it. If the role exists, stop and
compare attributes/memberships instead of blindly altering it. Do not grant rds_iam
to the master; retain RDS-managed password authentication for that service identity.
Grant narrowly required SELECT for preflight on the six FinTrust tables (not all
schemas); grant no application write privileges to the migration login. DDL still
requires ownership as explained above. Prefer an existing narrow NOLOGIN owner;
otherwise separately approve transfer of only public.transactions to
fintrust_transactions_owner. Grant temporary membership with SET TRUE, INHERIT FALSE,
ADMIN FALSE on PostgreSQL 16, then SET ROLE only during fixed migration DDL. Never
grant fintrust_admin or rds_superuser membership. If baseline tables are absent,
stop for a separate schema/bootstrap plan; the role example does not authorize it.

After provisioning, verify a NEW IAM-token/TLS connection as fintrust_migrate_dev
and its exact privileges. Master access is then removed before normal migration:

1. End master session; close all connections and discard request-local secret.
   Record success metadata only. Disable runner concurrency and wait for zero
   in-flight invocations and no runner DB sessions before changing phases.
2. Remove the role's bootstrap GetSecretValue Allow and add an explicit Deny for
   that action on the exact master secret as defense against another attached Allow.
   Keep only the exact rds-db:connect grant and necessary ENI/log permissions.
3. Deploy a reviewed IAM-only runner version with no password-fetch path. Controller
   may invoke only this version; withdraw invocation permission to old bootstrap
   versions and remove them after evidence capture. Configuration/version changes
   must replace the previous execution environment; do not claim del() zeroizes it.
   Test secret access is denied without returning/logging any value, and prove an
   IAM DB connection works. No SDK AssumeRole, Secrets Manager or KMS call is needed
   for the subsequent token-authenticated DB connection.
4. Retain the endpoint and its two SGs only for the bounded maintenance session.
   During IAM-only migration/verification, the execution-role Deny prevents master
   retrieval. The endpoint policy remains restricted to this role and exact secret;
   it is not an alternate credential path for the controller or other functions.
5. After migration/verification, disable concurrency and reconcile all DB sessions.
   The migration login cannot remove itself: separately approve the fixed admin
   cleanup version. Remove the IAM-only version's invoke permission and version,
   deploy only the reviewed cleanup code, and only then replace the secret Deny
   with the exact endpoint-restricted bootstrap Allow for that cleanup operation.
   Never re-enable secret retrieval while migration code remains invokable. The
   administrator revokes SET membership and rds_iam, sets fintrust_migrate_dev
   NOLOGIN, checks dependencies/owned objects, and drops the empty temporary login.
   Never DROP OWNED CASCADE or remove the persistent NOLOGIN owner/table.
6. Close the final master session; disable concurrency and wait for zero invocations.
   Remove the bootstrap Allow and restore its explicit secret Deny. Delete the
   approved function/versions and wait for Lambda ENI release before removing
   execution-role ENI permissions/role. Delete the Secrets Manager endpoint, wait
   for its ENI removal, revoke the two SG rules referencing each other and delete
   only the temporary SGs after no ENIs reference them. Do not delete shared ENIs
   or the existing app/DB SGs. Remove qualified controller invoke permissions.
7. Keep the RDS-managed secret, automatic rotation and AWS-managed key untouched.
   No new password copy, forced rotation or secret deletion is proposed. If any
   outcome is uncertain, disable tooling, record remaining hourly costs and seek
   reconciliation rather than destroy the only administrative recovery path.

To avoid ambiguity in that lifecycle, the preferred session sequence is bootstrap
-> revoke master access -> IAM-only migration/verification -> separately approved
fixed administrator cleanup -> revoke master access again -> remove endpoint,
client/endpoint SGs, function/versions and execution role after ENI cleanup.
During the middle IAM-only phase the endpoint remains for the bounded session but
no runner master-secret access is allowed. The administrator cleanup connection is
an explicit last bootstrap operation, not use of the master for DDL migration.
The first approval remains read-only preflight only; no role creation/cleanup DDL
is bundled into that invocation.

## Temporary endpoint cost and evidence

Official public af-south-1 AmazonVPC catalogue, retrieved 2026-10-09:
`AFS1-VpcEndpoint-Hours` SKU `8ZMGRUS7QT5EM7NR`: **USD 0.01309 per AZ-hour**;
first-PB endpoint data processing **USD 0.01/GB**. This is the interface endpoint
rate, not the similarly named Gateway Load Balancer/resource/tunnel rates.
One AZ: 4 hours USD 0.05236; 24 hours USD 0.31416; 730 hours USD 9.55570 if forgotten.
Partial endpoint-hours are billed as full hours. Two AZs double the hourly component.
Choose a four-hour maintenance window and same-session cleanup; this is an operating
budget, not an automatic billing cap. Taxes, Lambda/log/Secrets Manager API usage,
existing secret storage and any cross-AZ DB transfer/snapshot charges are additional.
No new secret or KMS key is created. Keeping runner and endpoint in af-south-1a avoids
cross-AZ secret retrieval. No Free Tier/credit coverage is assumed.
[Regional catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/af-south-1/index.json),
[PrivateLink billing](https://aws.amazon.com/privatelink/pricing/).

Current evidence is metadata/local-signing/design only in
`docs/EVIDENCE/05-rds/private-bootstrap-path/`; no secret/token is stored there.
Future evidence: endpoint ID/private DNS/SG policy review, pinned runner hash and
redaction tests, sanitized GetSecretValue request ID (not SecretString), TLS and
SQL read-only proof, approved role/ownership delta, IAM login verification,
secret-permission removal, explicit admin cleanup, endpoint/SG/role deletion.
The historical 78b2ceb no-endpoint/payload design and its evidence remain in Git;
this revision is authoritative. Existing uncommitted deployment notes are not edited.
No endpoint, function, role, policy or database mutation was performed this turn.

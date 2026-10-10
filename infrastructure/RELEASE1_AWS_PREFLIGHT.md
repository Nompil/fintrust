# Release 1 AWS inventory and private RDS preflight checkpoint

Status: **READ-ONLY AWS INVENTORY COMPLETE, 2026-10-10**. Live resource metadata now
confirms the existing infrastructure and the undeployed Release 1 components. Database
schema/migration state remains unknown: no live SQL or private runner invocation occurred.
The IAM user ARN does not independently prove MFA for the current inventory login.
No AWS mutation, secret retrieval, live SQL, application change, artifact rebuild or push.

Continues source `12b0c94844b6ff1a6389beb99e1f87a51fedb598`, evidence `8fb2c6e`,
CI `38066413745`: 590 passed, zero failed/skipped. The verified Release 1 artifact
remains SHA256 `0ad342f40447751bf105e88d2ac1d473f6423394c1e01b3b4b921287a5d84b45`.
These historical test results do not prove any live AWS state.

## Identity and inventory execution boundary

The initial browser login expired; the user reauthenticated and the subsequent STS
call succeeded as `arn:aws:iam::966467878406:user/fintrust-inventory`, account
`966467878406`, with all workload inspections explicitly in `af-south-1`. The initial
read-only retry returned: `Your session has expired. Please reauthenticate using aws login`.
Evidence: `docs/EVIDENCE/02-iam/release1-inventory-session-check.json`.
User reauthentication: `aws login --profile fintrust-inventory`.
Then resume with:

```bash
aws sts get-caller-identity --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Require account `966467878406` before all resource inspection. Explicitly select
`af-south-1` on every regional call. Do not fall back to admin credentials. An STS
assumed-role ARN proves the caller role, not MFA; record MFA only if session evidence
independently proves it. Inspect IAM user MFA/access-key metadata if permitted, never
credential values. No long-lived keys are created. AccessDenied means UNVERIFIED,
not absent; an authorized not-found response means absent. Preserve timestamps,
profile, operation, region and sanitized error for each output.

Use read-only describe/get/list APIs below, scoped by exact stack/name/ARN or FinTrust
tag/name when discovery is necessary. Do not read object content, queue messages,
secret values, log contents or Lambda code download URLs. Record Lambda environment
**names only**. Redact SES email identities, retaining verification state and identity
kind or a stable hash. Restrict saved outputs to FinTrust resources. Do not dump
account-wide unrelated resources into evidence.

| Folder | Read-only inspection scope |
| --- | --- |
| 02-iam | STS identity; exact deployment/runtime role trust, attached/default policy documents, boundaries; existing user MFA/access-key metadata |
| 04-network | EC2 describe VPC/subnets/routes/security groups/endpoints/NAT gateways/attached internet gateways, filtered to verified FinTrust VPC; four private subnets in two AZs, DNS, no public/NAT route |
| 06-s3-kms | Exact raw/quarantine/reports bucket GetBucketEncryption/Versioning/Policy/PublicAccessBlock/PolicyStatus/Location; KMS DescribeKey/GetKeyPolicy/GetKeyRotationStatus/ListResourceTags on verified key |
| 05-rds | DescribeDBInstances fintrust-ledger-dev; its DB subnet group and parameter groups, DescribeDBParameters force_ssl, secret DescribeSecret metadata only; DB/secret KMS relationship |
| 07-sqs-dynamodb | DescribeTable fintrust-risk-dev, TTL/PITR/stream metadata and tags; GetQueueUrl/GetQueueAttributes/ListQueueTags for the five exact Stage 4 queues, encryption/redrive/visibility/retention/counts |
| 08-lambda | ListFunctions filtered fintrust-, GetFunctionConfiguration with environment values removed, GetFunctionConcurrency, ListEventSourceMappings scoped to each function, GetFunctionEventInvokeConfig, ListTags; code hash from configuration |
| 09-api | REST and HTTP API discovery filtered FinTrust name/tags; selected API resources/routes/methods/stages/integrations/authorizers/deployments only |
| 10-monitoring | EventBridge FinTrust rules and targets/state; exact Lambda log-group retention/tags; FinTrust alarms/dashboards, tracing from Lambda configuration; SES GetAccount plus redacted identity verification metadata |

For Lambda CLI output, project before printing/saving, for example:

```bash
aws lambda get-function-configuration --function-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --query '{Name:FunctionName,State:State,Runtime:Runtime,Architecture:Architectures,Handler:Handler,Memory:MemorySize,Timeout:Timeout,CodeSize:CodeSize,CodeSha256:CodeSha256,Role:Role,Vpc:VpcConfig,EnvironmentNames:keys(Environment.Variables || `{}`),Tracing:TracingConfig}' --no-cli-pager
```

Do not save unprojected `get-function` output: it contains a code download URL.
S3 intended buckets: `fintrust-raw-966467878406-af-south-1-dev`,
`fintrust-quarantine-966467878406-af-south-1-dev`,
`fintrust-reports-966467878406-af-south-1-dev`; confirm stack outputs first.
Queue names: `fintrust-transactions-dev.fifo`, `fintrust-transactions-dlq-dev.fifo`,
`fintrust-ingest-failures-dev`, `fintrust-report-failures-dev`, `fintrust-alert-failures-dev`.

## Expected versus actual Release 1

Actual states below come from fresh approved read-only CLI responses. Each existing
evidence folder contains `release1-live-inventory.json`. No inspection was denied.
Authorized not-found responses establish absence of the exact temporary roles/stacks
and ingest resource policy/function URL; they are not permission failures. Missing
future Release 1 components are deployment gaps, not unexplained earlier-stage drift.

| Component | Expected Release 1 state | Actual AWS state | Match | Action required |
| --- | --- | --- | --- | --- |
| Identity | Approved read-only inventory/account/region; no keys | fintrust-inventory IAM user; account966467878406; af-south-1; zero keys; MFA device configured | Yes; session MFA not independently proven | Retain user/profile evidence |
| Existing stacks | Stages1-4 verified and historical ingest | All five stacks CREATE_COMPLETE | Yes | No resource changes |
| Network | Four private subnets/two AZs, narrow DB5432, S3/Dynamo gateways, no NAT/public route | Four subnets af-south-1a/1b; public-IP mapping false; app443 gateway prefixes and DB5432 only; no NAT/IGW; two gateways available | Yes | Proposed temporary Secrets endpoint separately approved |
| S3/KMS | Three private/versioned CMK-encrypted buckets | All three versioned, SSE-KMS+bucket keys, all public blocks, nonpublic policies; enabled365-day-rotation CMK | Yes | Screenshot controls; no upload |
| RDS | PG16.15 t4g.micro20GiB gp3/private/Single-AZ/IAM/TLS/aws-rds key | available; all settings match; deletion protection; backups1day; TLS group in-sync | Yes | Live SQL still separate gate |
| Secret | RDS-managed credential through private endpoint for runner | Active RDS-owned secret; AWSCURRENT; seven-day rotation; aws/secretsmanager key; no Secrets endpoint | Credential exists; retrieval path not deployed | Create approved private path later; never retrieve value now |
| Dynamo | fintrust-risk-dev on-demand account_id/score_date, NEW_IMAGE stream | ACTIVE, PAY_PER_REQUEST, exact keys, stream enabled; default AWS-owned encryption; approximate ItemCount0 | Yes | Scoring/stream consumer not deployed |
| SQS | Five queues, transaction FIFO+FIFO DLQ, managed encryption | All five exist, SSE-SQS; transaction visibility720s/retention4days/maxReceive5; DLQ14-days/byQueue; all three approximate counts0 per queue | Yes | No receive/redrive |
| Ingest | Verified new candidate, separate runtime/activation gates | Historical SHA d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62, Python3.12/x86_64/256MiB/120s, outside VPC, concurrency 0 | Historical stage matches; Release1 not deployed | Review code/runtime policy update later |
| Triggers | Controlled activation after schema/runtime approval | All bucket notification configs empty; no event mappings/resource policy/function URL/aliases; async failure points to ingest-failures | Safe inactive state | Do not wire/activate |
| Other functions/API | Scoring/report/alert/API deployment later | Only named ingest function exists; no FinTrust REST/HTTP APIs | Deployment gap | Separate deployment/auth/controller review |
| Monitoring/SES | Release1 alerts/reports/observability | Ingest logs14-days/storedBytes0, PassThrough tracing; no named schedules/alarms/dashboards; SES sandbox200/day1/sec, zero verified identities | Deployment gap | Observability/notification setup later |
| Private preflight | Separately approved single-AZ runner/endpoint | No interface endpoint, no migration stacks, no migration execution/operator roles | Not deployed | Approve scoped operator bootstrap/network/runner plan |
| Schema001/002 | Ordered exact versions/catalog/owners/grants and preserved rows | Not inspected live | Unknown | Approved private read-only preflight first |

Live DB subnet group `fintrust-db-dev` contains database subnets
`subnet-04dc0f576867d7a6c` (af-south-1a) and `subnet-084deb13f49a36064` (af-south-1b).
Application subnets remain `subnet-0c2d87e8a83361e30` and `subnet-0328276227fa30ead`.
DB endpoint `fintrust-ledger-dev.cv84aee6u6up.af-south-1.rds.amazonaws.com:5432`, DB `fintrust`,
resource ID `db-QZ3JN4H22YOMU7VLI22RL2IUYQ` and pinned secret ARN match runner configuration.
Master credential value was never retrieved. `rds.force_ssl=1`, `ssl=1`, parameter group
`fintrust-postgres16-dev` familypostgres16 and instance parameter apply statusin-sync.
Instance metadata/parameter settings do not substitute for future TLS-session verification.

IAM comparison: 14 of15 mapped Stage1-5 local policy documents match the current live
policy documents. The one expected prepared-release difference is ingest runtime:
live lacks proposed `ReadBatchAudit`/`ListBatchMarkers` and quarantine batch-read KMS context.
Do not apply candidate code without its separately reviewed policy update. No automatic
IAM correction was made. The deployer user's additional `FinTrustWellArchitectedReview`
inline policy grants Well-Architected metadata writes with Resource*. This means the user
is not literally assume-role-only across all AWS services; infrastructure deployment still
uses the MFA-controlled role. Flag for owner review, not unsolicited removal. Inventory
has ReadOnlyAccess plus SignInLocalDevelopmentAccess (OAuth login token actions); no
infrastructure write grant was found in its user/group policy scope. Both users have
zero access keys and one configured MFA device. Validation of all eight inventory files found no unexpected failed reads and no secret
values/environment value fields. See02-iam/release1-inventory-verification.json.
Account SCP/session-policy constraints
and actual MFA context were not independently evaluated. No formal CloudFormation drift
detection operation was run; these are read-only resource/policy comparisons.

## Private database access: implemented locally, not deployed

Authoritative design: `PRIVATE_RDS_RUNNER.md`, `infrastructure/migration.py`,
`migration_runner/`, four phase manifests in existing RDS evidence folder
`docs/EVIDENCE/05-rds/migration-runner-ci/37931518056/`.
That CI verifies PG16/Python3.12 Linux x86_64 packages and migration **001 only**.
No live endpoint, runner, bootstrap identity or migration state is claimed here.

Live-verified target: VPC `vpc-0aba008bb360f5147`, single application subnet
`subnet-0c2d87e8a83361e30` in af-south-1a. Runner uses app SG
`sg-0850bd798bb9505e2` to DB SG `sg-01644a4c9f2c44162` TCP5432.
Temporary client SG permits HTTPS to temporary endpoint SG; endpoint ingress443 only
from that client SG. Four proposed network resources: EndpointSecurityGroup,
ClientSecurityGroup, EndpointIngress, SecretsEndpoint (private DNS, Secrets Manager,
one AZ). Three runner resources: RunnerLogs (14-day retention, Retain), RunnerLambda,
RunnerVersion. Execution role/boundary and artifact authorization are separate bootstrap.
Existing app SG also allows S3/Dynamo gateway traffic: this is not DB-only isolation.
Fresh inventory confirms DNS support/hostnames true, the pinned routes/SGs and no
interface endpoint/private Secrets Manager path in the FinTrust VPC.

Preflight/bootstrap/cleanup phases retrieve only the pinned RDS master secret AWSCURRENT
through the actual private endpoint. IAM phase explicitly denies master-secret retrieval,
uses local SigV4 token generation and `rds-db:connect` for `fintrust_migrate_dev`.
Tokens need no AWS API call, but the PostgreSQL role and rds_iam membership must already
exist. TLS verify-full/CA/host validation required. No password in payload/env/log/Git.
Preflight is read-only; bootstrap, IAM migrate and cleanup are separate mutation approvals.
No invocation now. Numeric qualified version, synchronous invocation, no LogType Tail,
no trigger/URL/async configuration; concurrency stays0 until separately approved1.

Fresh AWS Pricing GetProducts quote (SKU8ZMGRUS7QT5EM7NR, published2026-09-17,
effective2026-09-01): one-AZ endpoint $0.01309/hour, four hours $0.05236,
24 hours $0.31416,730 hours $9.55570 plus processing (first PB $0.01/GB), Lambda/log/S3
usage. Quote confirmed on2026-10-10; credits/tax excluded. Endpoint hours
continue while idle and partial hours round up; see https://aws.amazon.com/privatelink/pricing/.
Existing RDS/CMK/secret storage costs continue independently; this task adds none.
Cleanup after approved DB work: revoke qualified invocation/drain runner; remove DB
login/helper privileges through reviewed cleanup; remove runner versions/function,
temporary IAM, endpoint and SGs after DB cleanup. Retained logs/artifact versions need
explicit retention/cost ownership; no automatic data/snapshot/key deletion.

## Exact later read-only SQL plan

1. Existing `sql/preflight/001_transaction_identity_catalog.sql`: server/database/user/TLS,
schemas, types/nullability/constraints/indexes/owners/ACLs/RLS/triggers/role memberships.
Existing runner sanitizes definitions before evidence; do not export raw definitions.
2. New `sql/preflight/002_release1_catalog.sql`: absence-safe catalog supplement for base,
tracking, ten operational tables/two views; owner/ACL/type/nullability/index validity,
trigger owner/definer and definition hashes only. MD5 here is a metadata comparison
fingerprint, not a credential or release-artifact security checksum. This SQL is proposed
only; the verified 001 package does NOT include it. Extending the private read-only runner
requires a focused implementation/package verification gate before live invocation.
3. Only after catalog approves six base tables/types, no unexpected RLS/triggers and
bounded row count: existing `001_transaction_identity_data.sql` returns counts only,
trusted-source duplicate groups and invalid/null identity/backfill metadata. Legacy rows
need no invented upstream reference; tx_id values/row payloads never leave the DB.
4. Only if schema_migrations exists with exact four columns, ordinary table kind and
SELECT privilege, execute the following under the same read-only/timeout transaction:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='15s';
SET LOCAL search_path=pg_catalog;
SELECT version, source_sha256, catalog_sha256, applied_at
FROM public.schema_migrations ORDER BY version;
ROLLBACK;
```

If absent, report TRACKING_ABSENT; do not create it or infer migration absence from names
alone. Compare LF-normalized source SHA256:
001 `0ff06ca8c43596ac9b8651f4bd851bfb0487343f4c9eccb198849e3e59772bd6`;
002 `5b2c04440eea244bfce150347dfa1953dd2a7e7ddb6af7e3a66e187d1c912f02`.
Catalog SHA uses the canonical comparison algorithm, not the metadata MD5 fields alone.
5. Supplement returns exact conditional `SELECT count(*) FROM public.<approved table>`
query strings for existing SELECT-authorized ordinary tables. They are NOT executed by
the supplement. Review RLS/size/owners first, then execute approved strings individually
inside a bounded READ ONLY transaction, returning table/count only. Includes alerts,
batches/records/reviews/quarantine/outboxes/operations; no notes/raw payloads/account IDs.
Count reconciliation views only after definition compatibility has been established.
Any timeout, missing required grant, wrong owner, partial identity or unexplained object
stops the preflight; do not change schema to make a check pass.

## Migration002 live preconditions and unresolved gate

- Inventory and read-only SQL establish actual schema first. No live schema assumptions.
- Canonical base transactions(tx_id), risk_events(risk_event_id), processed_transactions(tx_id)
and other six base tables must match; no unexpected triggers/RLS/extensions/type changes.
- Verified001 exact seven identity columns, constraint and two indexes precedes002.
Tracking/source/catalog agreement required; untracked001 needs explicitly reviewed adoption,
not blind replay. `fintrust.migrations.apply_local` rejects live DSNs and is not a live runner.
- No conflicts with ten tables, two views, nine functions, triggers, three explicit indexes
or automatically generated PK/unique indexes. Names alone never prove compatibility.
- Dedicated reviewed NOLOGIN owner(s) and temporary login SET grants; exact schema
CREATE/USAGE, base table REFERENCES and view/function SELECT privileges. The001 owner
of transactions alone cannot create002 schema objects. No broad runtime DDL grants.
- Own new tables/indexes/views/functions consistently; pinned SECURITY DEFINER owner,
search path and EXECUTE grants, no PUBLIC runtime expansion. PG16 built-in UUID function
and plpgsql availability verified; snapshot approved separately before changes.
- 002 is transactional, non-idempotent CREATE SQL. Never rerun raw SQL against applied
or partial objects. Exact tracker+catalog yields no-op; conflict refuses. A future verified
live runner must provide serialization, source/catalog tracking, ownership/grant orchestration
and same-transaction postchecks. Existing001 helper creates only001 indexes; do not repurpose it.
- Regular CREATE INDEX, no CONCURRENTLY; lock/statement budgets reviewed against actual
size/activity. New FK validation references old rows; expected financial tables/rows stay
unchanged. Before/after counts and identities compare inside approved verification.
- On error rollback whole transaction, inspect catalog/tracker read-only and stop. Do not
DROP/CASCADE existing history or try ad-hoc partial repairs. Snapshot recovery requires
separate approval and preserves source DB/evidence. Revoke disposable role memberships,
helpers/schema CREATE afterwards; refuse cleanup with sessions/owned surprises.
- Runtime service roles get only tested service table/column/sequence/function privileges,
never ownership, CREATE, migration role membership or master secret. No claims these
local role grants are already live. The002 live runner is still NOT IMPLEMENTED/VERIFIED.

## Operational identity and permission matrix (proposed, not attached)

| Operation | Identity/path | Minimum approved scope |
| --- | --- | --- |
| Inventory | fintrust-inventory | Scoped read-only describe/get/list; no secret values |
| Temporary IAM bootstrap | controlled fintrust-admin | FinTrustMigrationBootstrap: exact migration role/boundary/policies, mandatory boundary; content reviewed |
| Endpoint/runner deployment | separate scoped migration operator | FinTrustMigrationDeployment: exact two stacks/resource types, owned tempSG/endpoint/service, function/log/PassRole; artifact-version S3/KMS code fetch |
| Preflight invocation | existing MFA-backed fintrust-deployer-role with a separately approved temporary invoke-only addition | lambda:InvokeFunction exact approved numeric RunnerVersion; no deploy/secret privilege |
| Runner execution | fintrust-migration-dev + FinTrustMigrationBoundary | Phase-specific FinTrustMigrationRuntime; exact secret via actual vpce/AWSCURRENT or exact DB IAM user; exact logs/ENI controls |
| Snapshot later | separately reviewed snapshot operator | rds:CreateDBSnapshot exact source DB and approved snapshot name/tag scope; describe only, no DB deletion |
| Migration001 later | qualified invoker + IAM-phase runner | Approved fixed001 operation and temporary PostgreSQL role, no master secret |
| Migration002 later | NOT READY | Separate verified live capability/privilege design required first |
| Workload Lambda deployment later | existing fintrust-deployer-role where safe | Reviewed named function/stack/PassRole/artifact version; no IAM bootstrap |
| Trigger/concurrency activation later | separately scoped activation operator | Exact functions/mappings/notifications/rules, bounded concurrency; each activation approved |
| Cleanup later | controlled scoped recovery identity | Exact temporary stacks/endpoint/SG/function/role; reviewed DB cleanup; no financial DROP OWNED/CASCADE |
| Runtime DLQ operations | separate future operations controller | Existing release1-operations-controller-policy queue pair only; not an endpoint deployer; cloud auth/network remains a separate gate |

Critical: current deployer carries an explicit Stage1 deny for interface-endpoint subnet/SG
attachment. Additional Allow cannot override it. Do not weaken it; use a separately reviewed
migration operator. Placeholder endpoint IDs in rendered policy must be replaced with verified
actual ID before attachment. All proposed permissions require Access Analyzer and approved
AWS setup later. No broad admin deployment or controller shortcut is approved here.

## Console screenshot checklist (not yet captured)

Use existing folders. Exclude secret values/environment values/private email addresses.

| Console page | Fields/state | Existing folder / suggested filename | Rubric purpose |
| --- | --- | --- | --- |
| IAM role/account identity | Account, role trust, boundary and policy names; separate MFA evidence | 02-iam / release1-inventory-identity.png | Least privilege and identity traceability |
| VPC resource map + subnet/routes | Four subnets/two AZs, gateway endpoints, routes/no NAT/IGW default path | 04-network / release1-private-network.png | Private network boundary |
| VPC SG inbound/outbound | App source SG to DB5432; endpoint absent/present metadata | 04-network / release1-db-security-path.png | Narrow connectivity |
| RDS configuration/connectivity | PG/class/storage/private/IAM-auth/SG/subnets/state | 05-rds / release1-rds-live-config.png | Database security/cost posture |
| RDS parameter group | rds.force_ssl value and apply status | 05-rds / release1-rds-tls-parameter.png | Encryption in transit |
| Secrets Manager metadata | RDS owning service/DB relationship/rotation, hide value | 05-rds / release1-rds-secret-metadata.png | Secure bootstrap credential management |
| Each S3 bucket properties/permissions | SSE-KMS/versioning/all public blocks/policy | 06-s3-kms / release1-<raw-quarantine-reports>-controls.png | Storage governance |
| KMS key details/policy | Enabled, alias, key administration scope/rotation | 06-s3-kms / release1-kms-controls.png | Encryption governance |
| Dynamo table details/stream | fintrust-risk-dev keys/on-demand/stream/encryption/state | 07-sqs-dynamodb / release1-risk-table.png | Risk projection architecture |
| SQS source+DLQ configuration | FIFO/redrive/timeout/retention/encryption/counts | 07-sqs-dynamodb / release1-fifo-dlq-controls.png | Resilience/idempotency |
| Each Lambda configuration/concurrency/triggers | Runtime/handler/role/VPC/concurrency, unwired vs wired | 08-lambda / release1-<function>-state.png | Truthful runtime/activation boundary |
| API selected routes/stage/auth/integrations | Deployment and auth targets; absence only if authorized discovery succeeds | 09-api / release1-api-auth-routes.png | Real backend/access control |
| EventBridge rules/targets | Exact targets/state | 10-monitoring / release1-event-rules.png | Controlled automation |
| Logs/alarms/dashboard | Retention/health/alarm targets/dashboard existence | 10-monitoring / release1-observability.png | Monitoring/evidence |
| SES account + redacted identity status | af-south-1 sandbox/production and verified state | 10-monitoring / release1-ses-readiness.png | Notification readiness |

For future live SQL, save sanitized catalog/count JSON in05-rds; no fabricated screenshots
or PostgreSQL payloads. CLI evidence must distinguish confirmed absence from AccessDenied.

## Focused local validation

The new catalog supplement and existing001 read-only checks passed **10 tests, zero
failed/skipped** on the existing disposable loopback PostgreSQL database. Checks cover
missing objects, a fully001/002-migrated isolated schema, metadata hashes and unchanged
200-row synthetic ledger. This is local SQL validation, not live RDS or Linux runner
package validation. No full application suite or artifact build was repeated.
Evidence: `docs/EVIDENCE/05-rds/release1-preflight-local-tests.xml` and
`docs/EVIDENCE/05-rds/release1-preflight-local-test-output.txt`.

Additional exact null/backfill query, only after base catalog approval, inside the same
bounded READ ONLY transaction:

```sql
WITH records AS (SELECT to_jsonb(t) AS j FROM public.transactions t)
SELECT count(*) AS total,
 count(*) FILTER (WHERE j->>'source_transaction_id' IS NULL) AS missing_source_reference,
 count(*) FILTER (WHERE j->>'transaction_fingerprint' IS NULL) AS missing_fingerprint,
 count(*) FILTER (WHERE j->>'batch_id' IS NULL) AS missing_batch,
 count(*) FILTER (WHERE j->>'file_sha256' IS NULL) AS missing_file_hash,
 count(*) FILTER (WHERE j->>'source_row' IS NULL) AS missing_row_number
FROM records;
```

These are counts, not automatic rejection/backfill instructions: legacy rows can validly
have null provenance. Compare with canonical001 nullability and approved legacy handling.

## Next gate

Fresh inventory confirms the exact migration operator role does not exist. First
proposed AWS mutation is controlled administrator `iam:CreateRole` for
`fintrust-migration-operator-dev`, after review of this temporary trust:

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::966467878406:root"},"Action":"sts:AssumeRole","Condition":{"ArnEquals":{"aws:PrincipalArn":"arn:aws:iam::966467878406:user/fintrust_deployer"},"Bool":{"aws:MultiFactorAuthPresent":"true"}}}]}
```

Operator receives only generated FinTrustMigrationDeployment and exact preflight
artifact/version authorization, no managed administrator policy, IAM management, secret
read, snapshot or invocation grant. Direct human assumption requires a separately approved
temporary `sts:AssumeRole` allow on only
`arn:aws:iam::966467878406:role/fintrust-migration-operator-dev`, with MFA condition,
added to the named human identity and removed on cleanup. Do not chain from the existing
deployer role or weaken its interface-endpoint deny. Require a short MFA role session (proposed maximum3600seconds); Project=FinTrust,
Environment=dev and Purpose=temporary-migration tags on the role.
The existing FinTrustMigrationBootstrap proposal covers the bounded Lambda execution
role/boundary, not creation of this human operator; administrator performs that separate
reviewed bootstrap. It is never attached to the deployer/operator.

Then review exact network change set/cost before any execution; obtain actual endpoint ID
before creating endpoint-bound execution boundary/role; upload only verified phase archive
under separate artifact-upload approval; deploy immutable preflight version with concurrency 0.
Separately approve qualified invoke/concurrency 1 for the fixed READ ONLY operation, then
return to0 and stop to compare actual SQL. No mutation command was run or authorized by
this report. Exact artifact version, operator bootstrap/deployment JSON and endpoint-bound
policies remain a separate concrete approval checkpoint; do not attach placeholder policies.

Remaining later gates: live schema001/002 state unknown;002 catalog supplement not in
verified runner;002 live executor not implemented; candidate ingest/runtime policy not
live; scoring/report/alert/API/auth/controller/SES/monitoring not ready for activation.
These do not prevent review of controlled read-only preflight infrastructure. They do
prevent migration or full Release1 activation. Existing source, artifact and historical
uploaded VersionId remain untouched. Ten focused local SQL tests remain passed; no
application suite, ZIP build or CI run was repeated for metadata/documentation changes.

**FINTRUST READ-ONLY AWS PREFLIGHT COMPLETE — READY FOR CONTROLLED RDS PREFLIGHT INFRASTRUCTURE**

## Current controlled preflight gate — 2026-10-10

The latest authoritative plan is [RELEASE1_CONTROLLED_PREFLIGHT_PLAN.md](RELEASE1_CONTROLLED_PREFLIGHT_PLAN.md). It supersedes earlier statements that the002 supplement/executor are missing and that a single combined deployment policy should be attached. Historical evidence remains unchanged. Runner source 20775e4, CI 38088022104:626 passed,zero failed/errors/skipped; seven Linux/Lambda3.12 archives verified, PG16 fixed-helper rehearsal passed. No AWS mutation or live SQL occurred. First pending approval is only empty migration-operator role creation. The frozen application ZIP remains unchanged.

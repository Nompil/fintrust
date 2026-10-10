# Release 1 AWS inventory and private RDS preflight checkpoint

Status: **BLOCKED pending fintrust-inventory login**. No live identity, resource state,
AWS drift, migration state or MFA assertion has been established in this checkpoint.
Historical resource IDs below are targets for fresh verification, not live evidence.
No AWS mutation, secret retrieval, live SQL, application change, artifact rebuild or push.

Continues source `12b0c94844b6ff1a6389beb99e1f87a51fedb598`, evidence `8fb2c6e`,
CI `38066413745`: 590 passed, zero failed/skipped. The verified Release 1 artifact
remains SHA256 `0ad342f40447751bf105e88d2ac1d473f6423394c1e01b3b4b921287a5d84b45`.
These historical test results do not prove any live AWS state.

## Identity and inventory execution boundary

The approved inventory profile exists but its browser login has expired. The elevated
read-only STS retry returned: `Your session has expired. Please reauthenticate using aws login`.
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

Every actual field is currently UNVERIFIED because authentication failed. Missing
future Release 1 components are deployment gaps, not evidence of drift in earlier stages.

| Component | Expected Release 1 state | Actual AWS state | Match | Action required |
| --- | --- | --- | --- | --- |
| Identity | Approved read-only profile/account966467878406/af-south-1 | Session expired | Unknown | Login then STS/account guard |
| Network | Stage1 four private subnets/two AZs; app-to-DB5432; S3/Dynamo gateway endpoints; no NAT/public route | Unverified | Unknown | Scoped network inventory |
| S3/KMS | Stage2 three private/versioned CMK-encrypted buckets | Unverified | Unknown | Verify policies/public blocks/key administration |
| RDS | PG16.15 t4g.micro Single-AZ20GiB gp3/private/IAM auth/force_ssl/aws-rds encryption/managed secret/one-day backups/deletion protection | Unverified | Unknown | Inspect DB and secret metadata; no secret values |
| DynamoDB | Stage4 fintrust-risk-dev, on-demand, exact keys, intended stream and encryption | Unverified | Unknown | Compare Stage4 template |
| SQS | Five named queues; transaction FIFO and FIFO DLQ with scoped redrive | Unverified | Unknown | Inspect attributes/counts; never receive/redrive |
| Ingest | Version-pinned verified release; bounded activation separately approved; S3 trigger separately approved | Unverified; historical Stage5 ingest differs from candidate | Unknown | Hash/concurrency/trigger inventory, no replacement |
| Scoring | FIFO mapping, private DB TLS/IAM privileges, projections | Unverified | Unknown | Identify deployed vs prepared resources |
| Reports/alerts | Intended EventBridge/stream triggers and destinations; idempotent alerts | Unverified | Unknown | Verify runtime/trigger/SES readiness |
| API/frontend/auth | Real backend; reviewed cloud identity; least-privilege operations path | Unverified; local identity is not AWS provisioning | Unknown | Inventory and separate auth/controller approval |
| Schema001/002 | Exact ordered versions, catalog/ownership/grants and preserved financial rows | Not inspected live | Unknown | Approved private read-only runner first |

## Private database access: implemented locally, not deployed

Authoritative design: `PRIVATE_RDS_RUNNER.md`, `infrastructure/migration.py`,
`migration_runner/`, four phase manifests in existing RDS evidence folder
`docs/EVIDENCE/05-rds/migration-runner-ci/37931518056/`.
That CI verifies PG16/Python3.12 Linux x86_64 packages and migration **001 only**.
No live endpoint, runner, bootstrap identity or migration state is claimed here.

Historical target: VPC `vpc-0aba008bb360f5147`, single application subnet
`subnet-0c2d87e8a83361e30` in af-south-1a. Runner uses app SG
`sg-0850bd798bb9505e2` to DB SG `sg-01644a4c9f2c44162` TCP5432.
Temporary client SG permits HTTPS to temporary endpoint SG; endpoint ingress443 only
from that client SG. Four proposed network resources: EndpointSecurityGroup,
ClientSecurityGroup, EndpointIngress, SecretsEndpoint (private DNS, Secrets Manager,
one AZ). Three runner resources: RunnerLogs (14-day retention, Retain), RunnerLambda,
RunnerVersion. Execution role/boundary and artifact authorization are separate bootstrap.
Existing app SG also allows S3/Dynamo gateway traffic: this is not DB-only isolation.
Fresh inventory must confirm DNS/routes/SGs and no existing private Secrets Manager path.

Preflight/bootstrap/cleanup phases retrieve only the pinned RDS master secret AWSCURRENT
through the actual private endpoint. IAM phase explicitly denies master-secret retrieval,
uses local SigV4 token generation and `rds-db:connect` for `fintrust_migrate_dev`.
Tokens need no AWS API call, but the PostgreSQL role and rds_iam membership must already
exist. TLS verify-full/CA/host validation required. No password in payload/env/log/Git.
Preflight is read-only; bootstrap, IAM migrate and cleanup are separate mutation approvals.
No invocation now. Numeric qualified version, synchronous invocation, no LogType Tail,
no trigger/URL/async configuration; concurrency stays0 until separately approved1.

Historical regional quote: one-AZ endpoint $0.01309/hour, four hours $0.05236,
24hours $0.31416,730hours $9.55570 plus processing (first PB $0.01/GB), Lambda/log/S3
usage. Regional hourly quote needs fresh verification before approval. Endpoint hours
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
| Preflight invocation | separate MFA-backed qualified invoker | lambda:InvokeFunction exact approved numeric RunnerVersion; no deploy/secret privilege |
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

First possible AWS mutation is administrator bootstrap of the exact bounded migration
operator/execution role if absent; only then the reviewed single-AZ Secrets Manager
network change set and runner deployment. Which resource is first depends on fresh
inventory. None is authorized now. Approve cost and exact policies/templates separately.

Current blockers: expired inventory login; live resource/schema state unknown; proposed
002 supplement not in verified runner;002 live executor not implemented. No drift detected
means no drift assessment was possible, not that the account is compliant.

**FINTRUST AWS PREFLIGHT BLOCKED — fintrust-inventory session expired; live inventory pending**

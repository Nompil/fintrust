# Controlled Release 1 private RDS preflight approval plan

Prepared 2026-10-10 from the existing checkpoint. This plan authorizes no AWS mutation, secret retrieval or live SQL. AWS Integration remains In Progress. Existing stages1–4 and inactive historical ingest are CREATE_COMPLETE; the frozen Release1 application is not deployed.

## Verification and release bindings

- Frozen application source: `3234ba5139ed354943098ecbb81080802baad9f3`; ZIP `build/release1-candidate/3234ba5/fintrust-release1-linux-py312.zip`,21,414,325 bytes; SHA256 `788f786f4947c186a639427fd21f209a6a3cdcf0f0a284a94c0be4237177eb10`. Rechecked unchanged. No application build/upload occurred.
- Migration-tool source: `20775e4d42be3081aab457811290e1f7befb6bea`; [CI 38088022104](https://github.com/Nompil/fintrust/actions/runs/38088022104): **626 passed,0 failed,0 errors,0 skipped**. Seven exact archives imported under Linux CPython3.12.15 x86_64, including official Lambda runtime with networking disabled; psycopg2-binary2.9.13/native libpq loaded. Downloaded hashes and source bindings match. PostgreSQL16 disposable rehearsal passed; it does not prove live RDS IAM/TLS.
- Preflight archive: `build/migration-runner/ci-38088022104/fintrust-migration-preflight.zip`;20,673,631 bytes; SHA256 `3d550f4493069dd797878d8125e59cb9c50ed17fbfe53d0561d556f02f423624`; base64 `PVUPRJMGndeXh42BJeWcucUO0X+/5T0FYdVW8C9CNiQ=`. No S3 VersionId exists for these newly verified runner archives yet; upload requires separate approval.
- Focused tooling local91 passed; corrected IAM focused 38 passed including final renderer recheck. Access Analyzer: all three split operator policies and bootstrap policy **zero findings**. Network/preflight CloudFormation templates validated read-only successfully. One initial direct Windows pytest invocation failed on the protected shared temp directory and skipped the local-DB fixture; the project isolated test runner rerun passed all 38 with zero skips. Initial environment-error evidence and successful replacement are both retained.
- Evidence files are flat additions within existing `docs/EVIDENCE/02-iam` and `05-rds`; authoritative receipt `05-rds/release1-preflight-38088022104-receipt.json` includes all seven manifests, flags and source bindings. Earlier CI38087744387 failure is preserved: unexpected workflow-trigger overlap in the 001-only postcheck was corrected without weakening original financial-table trigger refusal.

## Current-state evidence and missing screenshots

Fresh metadata evidence in each existing folder: `release1-controlled-preflight-metadata.json`. The KMS/queue/monitoring supplement records prior capture time; only those added reads are newer. Existing screenshots are historical deployment proof, not automatically proof of current settings. They were inventoried, not visually re-certified. Missing visual evidence does not block narrowly controlled private preflight when sanitized CLI proves the same state.

|Folder|Console page|Capture fields|Suggested filename|Rubric reason|Evidence status|
|---|---|---|---|---|---|
|01-budget|Billing > Budgets > FinTrust-Monthly-Budget|USD10 monthly, all-service scope; actual50/80/100 + forecast100|release1-budget-controls.png|Cost governance|Historical overview exists; fresh CLI verifies controls. Optional refresh only if rubric needs thresholds visibly.|
|02-iam|IAM > Users > fintrust_deployer / fintrust-inventory > Security credentials|MFA enabled; access keys0|release1-inventory-identity.png|MFA and no persistent credentials|Historical screenshots exist; fresh CLI proves both. No duplicate capture needed.|
|02-iam|IAM > Roles > fintrust-deployer-role > Trust / Permissions|Exact human/MFA trust; scoped staged policies; endpoint deny retained|release1-deployer-controls.png|Least privilege|Historical staged screenshots exist. Capture one current policy/trust view only if visual proof required; operator is absent.|
|04-network|VPC > Your VPCs > FinTrust VPC > Resource map / Subnets / Route tables|Four private subnets, no public IP; S3/DynamoDB gateways; no NAT or interface endpoint|release1-private-network.png|Private architecture and cost|Missing console control view; fresh CLI supports it. Existing06/07 prove historical stack completion.|
|04-network|EC2 > Security groups > sg-01644a4c9f2c44162 > Inbound rules|TCP5432 only from sg-0850bd798bb9505e2|release1-db-security-path.png|Network least privilege|Missing control screenshot; fresh CLI verifies rule.|
|05-rds|RDS > Databases > fintrust-ledger-dev > Configuration / Connectivity & security|PostgreSQL16.15, t4g.micro,20 GiB gp3,SingleAZ,private,encrypted,IAMauth,backup 1 day,deletion protection|release1-rds-live-config.png|Private encrypted relational data|Missing live configuration view; existing09/10 are stack evidence, fresh CLI verifies settings. Use two frames if needed.|
|05-rds|RDS > Parameter groups > fintrust-postgres16-dev > Parameters|rds.force_ssl=1; postgres16 family|release1-rds-tls-parameter.png|TLS enforcement|Missing console proof; fresh CLI verifies rds.force_ssl.|
|05-rds|Secrets Manager > RDS-managed master secret > Overview|RDS owning service, secret ARN, rotation enabled; never Retrieve secret value|release1-rds-secret-metadata.png|Secure credential governance|Missing optional screenshot; fresh metadata CLI suffices. Do not expose any secret value.|
|06-s3-kms|S3 > each fintrust-{raw,quarantine,reports}-966467878406-af-south-1-dev > Properties / Permissions|Versioning enabled; SSE-KMS; all public blocks; bucket policy not public|release1-{raw,quarantine,reports}-controls.png|Storage governance|Three live-control views missing; historical08/09/10 remain deployment proof; fresh CLI verifies all three.|
|06-s3-kms|KMS > Customer managed keys > alias/fintrust-dev|Enabled symmetric encrypt/decrypt AWS_KMS single-region; rotation|release1-kms-controls.png|Encryption governance|Missing optional control view; fresh key/rotation metadata verifies it.|
|07-sqs-dynamodb|DynamoDB > Tables > fintrust-risk-dev > Overview / Additional settings|ACTIVE, on-demand, intended keys, encryption/stream setting as deployed|release1-risk-table.png|Scalable risk projection|Missing control view; fresh CLI verifies actual state; existing02/03 prove completion.|
|07-sqs-dynamodb|SQS > fintrust-transactions-dev.fifo > Details / DLQ; then companion DLQ|FIFO, SSE-SQS, maxReceiveCount 5; DLQ14-days; source queue only redrive|release1-fifo-dlq-controls.png|Resilience and recovery|Missing control view; fresh CLI verifies all five queues without receiving messages.|
|08-lambda|Lambda > fintrust-ingest-dev > Configuration / Concurrency / Triggers|Python3.12 x86_64, outside VPC, reserved0, no event mappings; historical package|release1-ingest-state.png|Safe inactive staging|Missing live-state screenshot; fresh CLI confirms. Frozen new application ZIP has NOT been deployed.|
|09-api|API Gateway > APIs in af-south-1|No FinTrust REST/HTTP API exists|release1-api-current-absence.png|Honest deployment status|No screenshot exists; fresh CLI absence evidence sufficient. Do not manufacture auth/route proof; future release gate.|
|10-monitoring|CloudWatch > Log groups > /aws/lambda/fintrust-ingest-dev|14-day retention, current storedBytes0|release1-observability.png|Bounded logs/audit|Missing optional console proof; fresh CLI sufficient. No FinTrust alarms/dashboard currently exist.|
|10-monitoring|EventBridge > Rules; SES > Account dashboard / Identities|No FinTrust rules; SES sandbox,0 verified identities|release1-event-rules.png / release1-ses-readiness.png|Honest activation/readiness status|No screenshot exists; fresh CLI absence/sandbox evidence sufficient. Do not configure SES or schedules.|

### Capture only these missing console control views

Use account966467878406 and regionCapeTown/af-south-1 for every service. Capture the selected resource name and relevant fields. Save in the existing folder from the table; do not reorganize historical screenshots.

1. VPC resource map/private routes and DB security-group inbound rules: two screenshots in04-network.
2. RDS configuration/connectivity and force_ssl parameter: two or three screenshots in05-rds.
3. Each S3 bucket Properties/Permissions showing versioning/encryption/public blocks: three resources in06-s3-kms; use additional frame only when fields do not fit.
4. DynamoDB table and FIFO/DLQ controls: two resources/views in07-sqs-dynamodb.
5. Ingest concurrency 0 and empty triggers: one or two frames in08-lambda.

Budget, credential, secret metadata, KMS and monitoring visual refreshes are optional where CLI already provides equivalent proof. API/events/SES remain future deployment gaps; absence proof is enough now. Hide emails and account recovery information. Never open Retrieve secret value, show environment-variable values, display records/messages or paste credentials. No screenshots were fabricated or automatically captured by this task.

## Exact IAM proposal and separation

Reviewable JSON is generated locally in `infrastructure/iam/`; no policy has been attached. Proposed managed policy names and files:

|Name / principal|Exact JSON|Scope|
|---|---|---|
|FinTrustMigrationCloudFormation / temporary operator|migration-operator-cloudformation-policy.json|Only fintrust-migration-network-dev and fintrust-migration-runner-dev; named fintrust-migration-* sets; exact 3 resource-type lists per stack; required FinTrust/dev/temporary-migration tags; no service role or imports; no IAM resources/capabilities.|
|FinTrustMigrationNetwork / temporary operator|migration-operator-network-policy.json|Regional metadata reads; CF-mediated temporary tagged SGs, owned rules/cleanup, Secrets Manager endpoint only; exact existing VPC and one subnet; endpoint attachment only owned temporary SGs.|
|FinTrustMigrationRunner / temporary operator|migration-operator-runner-policy.json|Only fintrust-migration-dev function/versions and exact log group; CF-mediated creation/configuration/deletion; PassRole only arn:aws:iam::966467878406:role/fintrust-migration-dev to lambda.amazonaws.com.|
|FinTrustMigrationBootstrap / controlled admin only|migration-execution-bootstrap-policy.json|Only FinTrustMigrationBoundary and exact execution role; role requires this boundary. Inline policy/trust contents are reviewed by admin; IAM cannot constrain their JSON content. Never attach this policy to operator/deployer.|

Three operator JSONs contain the exact same reviewed action set partitioned by service: compact sizes2993/3770/3521bytes, each below6,144. Combined10243byte policy is superseded and must not be attached. Access Analyzer rejected `ec2:VpcEndpointType`; it was removed while keeping exact `ec2:VpceServiceName=com.amazonaws.af-south-1.secretsmanager`, VPC/subnet/ownership/CF controls. The template fixes Interface, one subnet, PrivateDNS; no caller-selectable endpoint type/service. Unsupported condition is not claimed as an IAM guard.

CloudWatch legacy `logs:TagLogGroup` is narrowly allowed on the exact runner log-group ARN with region only, reflecting the verified Stage5 provider behavior. CreateLogGroup and modern TagResource retain request-tag/CF controls. No unrelated log group access or blanket log deletion added.

Regional wildcard resource is used only for APIs without resource-level authorization (metadata, Lambda service ENI operations). Mutation wildcard suffixes are within account/region resource types and require ownership/request tags plus CloudFormation mediation. Lambda ENI permissions are denied when called from function code using lambda:SourceFunctionArn; retained for Lambda service lifecycle. Existing deployer interface-endpoint Deny remains untouched. Operator receives no secrets read, database administration, IAM management or crypto permissions by these base policies.

Separate later grants, never attached now:

- `artifact_policy(verifiedSHA,actualVersionId,phase)` grants s3:GetObjectVersion only exact content-addressed migration ZIP + s3:VersionId and KMS Decrypt only exact existing key via S3, caller account and exact bucket/object encryption context. With S3 Bucket Key, bucket encryption context is required; S3 permission still restricts the exact object/version. Upload identity/authorization is a separate admin checkpoint.
- `invoke_policy(actualNumericVersion)` grants only lambda:InvokeFunction on the exact qualified fintrust-migration-dev:<version>, af-south-1. No $LATEST or wildcard invoke. Attach only after package/config/version verification and separate invocation approval.
- `snapshot_policy(exactReviewedName)` is prepared only for later separate approval: rds:CreateDBSnapshot on exact fintrust-ledger-dev and exact fintrust-release1-before002-YYYYMMDDtHHMMSSz snapshot; tagged snapshot AddTags; regional DescribeDBSnapshots wildcard required for read. No snapshot delete or instance modification.
- Execution runtime: bounded logs/ENI service lifecycle. Preflight/admin bootstrap/cleanup phases GetSecretValue only exact RDS secret, AWSCURRENT and actual aws:SourceVpce. IAM001/002 phases explicitly deny that secret and allow only rds-db:connect on db-QZ3JN4H22YOMU7VLI22RL2IUYQ/fintrust_migrate_dev. Endpoint-bound boundary must be rendered using the actual verified endpoint ID; placeholders must never be attached.

## Exact private architecture

|Component|Proposed setting|
|---|---|
|VPC/subnet|vpc-0aba008bb360f5147; ONLY subnet-0c2d87e8a83361e30, af-south-1a|
|Network stack|fintrust-migration-network-dev: EndpointSecurityGroup, ClientSecurityGroup, EndpointIngress, SecretsEndpoint (4 resources)|
|Private endpoint|com.amazonaws.af-south-1.secretsmanager, Interface, IPv4, PrivateDNS, one AZ; policy only execution role and exact RDS-managed secret|
|Lambda groups|Existing application SG sg-0850bd798bb9505e2 plus temporary client SG; client HTTPS443 only endpoint SG; endpoint ingress443 only client SG|
|DB path|Existing DB SG sg-01644a4c9f2c44162 accepts5432 only app SG; no existing SG edits|
|Runner stack|fintrust-migration-runner-dev: RunnerLogs, Runner, RunnerVersion (3 resources)|
|Lambda|fintrust-migration-dev, Python3.12 x86_64,512MiB,300seconds; reserved concurrency 0; exact numeric immutable version|
|Execution role|arn:aws:iam::966467878406:role/fintrust-migration-dev; Lambda-only trust, FinTrustMigrationBoundary, one phase policy at a time|
|RDS|fintrust-ledger-dev.cv84aee6u6up.af-south-1.rds.amazonaws.com:5432 / database fintrust; PG16.15, private|
|TLS|psycopg2 verify-full, pinned hostname, packaged RDS global CA; live session must report TLS and PostgreSQL16|

Secret metadata relationship is verified without GetSecretValue: `arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn` is the instance managed master secret. Private preflight retrieves AWSCURRENT over the temporary endpoint into memory, uses fintrust_admin and discards references after the connection. No Git/environment/payload/log persistence and no claim Python guarantees memory zeroization. Secrets Manager performs managed-key decryption server-side; no KMS endpoint required. IAM token generation is local SigV4 signing, but IAM login still requires administrator-created PostgreSQL user with rds_iam membership; it cannot bypass initial bootstrap.

No NAT, public DB, public subnet, RDS Proxy, second endpoint AZ, new permanent KMS key or workload-resource edits. Existing app SG egress is unchanged; this is a scoped extension for temporary HTTPS, not a claim that combining SGs restricts all existing egress.

Human assumes operator directly with fresh MFA, max3600seconds, no long-lived keys. Exact-user trust is in migration-operator-trust.json; user needs a later separately approved sts:AssumeRole allow for only this operator. Do not chain through the deployer. CloudTrail event history records role/policy/CF/EC2/secret API management actions; do not assume Lambda Invoke data events are already enabled. Save sanitized request_id, qualified version, CloudFormation events and runner static success/failure categories; no credentials, SQL payloads or row contents.

## Cost and bounded lifetime

Prepared estimate retained, not a new regional quote: Secrets Manager interface endpoint **$0.01309 per AZ-hour**; one AZ ×4 hours=$0.05236,24 hours=$0.31416,730 hours=$9.55570. Plus approximately$0.01/GB endpoint processing, Lambda duration/requests, Secrets Manager requests, S3 artifact storage/requests and CloudWatch logs; taxes/credits separate. AWS bills endpoint partial hours as full hours ([PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/)). Budget a four-hour approved window and delete the endpoint immediately after controlled work, not overnight. IAM empty-role creation has no standing charge. Existing RDS/storage/secret/KMS costs continue independently. No snapshot cost approved now.

## Exact bounded read-only SQL scope

The qualified preflight handler accepts exactly `{operation:preflight,request_id:<UUID>}` (JSON strings); it accepts no SQL, DSN, credentials, endpoint or user override. Invoke only synchronously RequestResponse after separately approving numeric-version invoke and concurrency 1; restore0 immediately, retain sanitized response in05-rds, then stop for schema review.

Exact fixed SQL: `sql/preflight/001_transaction_identity_catalog.sql`, `sql/preflight/001_transaction_identity_data.sql`, `sql/preflight/002_release1_catalog.sql`; orchestrator `migration_runner/common.py` and `release1_preflight.py`. Catalog wrappers are stripped and run within a single REPEATABLE READ READ ONLY transaction, lock timeout2seconds, statement timeout15seconds; the connection also bounds idle transaction time. Finish ROLLBACK. No schema/role grants or application writes happen in preflight.

|Inspection|Exact source / safe result|
|---|---|
|PG identity/TLS/database/schema|001catalog: current_database/current_user/session_user/server_version/pg_stat_ssl/public owner+ACL|
|Tables/columns/constraints/indexes/owners/grants|001catalog all public relations, column ACLs/default ACLs/roles/memberships; safe_report sanitizes definitions into hashes;002catalog expected workflow definitions/owners/RLS/trigger hashes|
|Row counts and duplicates|001data: bounded aggregate transaction counts/duplicate source identity groups; no duplicate identities or transaction row values returned|
|History and provenance|Supplement counts fixed existing readable tables, schema_migrations version/source_sha256/catalog_sha256 max10; null source reference/fingerprint/batch/file hash/row-number counts|
|001 state|assess contract on exact current catalog/data; absent/complete/conflicting state stops at review|
|002 preconditions|Existing 001 columns/indexes, exact source marker when present, expected workflow objects/owners/grants and fixed catalog fingerprints; no automatic adoption of unknown schema/history|
|Workflow/quarantine/reconciliation/alerts|Expected ingestion_batches/attempts/records,risk_reviews/history,quarantine_cases/corrections,correction_outbox,projection_outbox,operations_requests plus batch_reconciliation/quarantine_workflow views; alerts/risk_events/processed_transactions legacy tables|

Counts execute only the hardcoded allowlist of readable ordinary tables with psycopg2.sql.Identifier; the runner never executes SQL strings returned from catalog. Supplement includes absent/present and hashes for views. Null legacy provenance is reported for review, not blindly backfilled. No secret values, pg_authid, customer payloads, messages or full data rows are read for evidence.

## Migration002 readiness (prepared, not live)

Seven phase archives: preflight,bootstrap,iam,cleanup,bootstrap002,iam002,cleanup002. Existing001 behavior retained.002canonical SHA256 `5b2c04440eea244bfce150347dfa1953dd2a7e7ddb6af7e3a66e187d1c912f02`; app and canonical migrations unchanged.

After separate live review/snapshot/migration approvals only: complete 001 baseline before bootstrap002; administrator creates a persistent narrowly privileged NOLOGIN fintrust_workflow_owner and checksum-bound zero-argument SECURITY DEFINER helper. IAM fintrust_migrate_dev gets helper EXECUTE plus schema_migrations SELECT/INSERT, never workflow-owner membership, schema CREATE, arbitrary SQL or financial DML. Owner gets only required schema/object privileges and REFERENCES/SELECT for the reviewed workflow definitions. Pinned search_path excludes temp substitution.

IAM002 executes the fixed helper in one transaction with advisory lock; verifies source/catalog/owners/ACLs and preserves financial row counts; creates exact002 history marker only after verification. Helper self-removes on success. Forced postcheck failure rolls back DDL/history/helper removal; rerun with exact marker/catalog is no-op. Partial objects or mismatched history are refused, not repaired/imported automatically. CI preserved200 synthetic financial rows; actual002 rehearsal and cleanup passed. Host/source phase consistency is verified from downloaded manifests; no external runtime source is substituted.

Cleanup002 administrator phase refuses active migration sessions, removes leftover helper, revokes temporary login tracker access and owner schema CREATE/admin SET. Retain NOLOGIN workflow owner and schema_migrations history because live workflow objects depend on them. Then original001 cleanup revokes/drops temporary login/index builder after separate approval; retain permanent NOLOGIN transaction owner. No DROP OWNED CASCADE. Existing complete 001 with a preexisting unreviewed history table requires a new review, not guessed adoption.

## One first AWS mutation — approval pending

Create ONLY the empty temporary human operator role. This is the first prerequisite for the private path, not permission to deploy that path. It grants no operational permissions until later reviewed attachments. No endpoint, execution role, upload, snapshot, Lambda, invoke or database operation is bundled.

Run only after explicit approval, from the repository root with controlled administrator session:

```bash
aws iam create-role \
  --role-name fintrust-migration-operator-dev \
  --assume-role-policy-document file://infrastructure/iam/migration-operator-trust.json \
  --max-session-duration 3600 \
  --tags Key=Project,Value=FinTrust Key=Environment,Value=dev Key=Purpose,Value=temporary-migration \
  --profile fintrust-admin --no-cli-pager
```

Then read-only verify GetRole/trust/tags/session duration; list attached and inline policies must be empty. Capture `docs/EVIDENCE/02-iam/release1-migration-operator-created.json`. Read-only commands after approved creation:

```bash
aws iam get-role --role-name fintrust-migration-operator-dev --profile fintrust-inventory --no-cli-pager
aws iam list-attached-role-policies --role-name fintrust-migration-operator-dev --profile fintrust-inventory --no-cli-pager
aws iam list-role-policies --role-name fintrust-migration-operator-dev --profile fintrust-inventory --no-cli-pager
```

Stop again. Inventory already proves role absent. Do not use automatic replacement if it appears before approval.

Later separate approvals: exact user assume allow/operator policy attachment; network change-set review/execution; actual endpoint-bound execution role/boundary; verified preflight ZIP upload and exact VersionId; preflight runner change-set review/execution at concurrency 0; qualified invoke/concurrency 1. Read-only result then must be reviewed against001/002 assumptions before any snapshot/bootstrap/migration. Each reviewed change set must show exactly4 network or3 runner resources and no existing-stack mutation.

## Rollback, cleanup and remaining gates

No AWS cleanup needed from this task: no resources created. If first empty-role creation is reversed, controlled admin deletes only that empty role after read-only confirming no attachments/inline policies or active intended session; deletion itself needs approval.

For later approved infrastructure failure, preserve stack events/resources first. ROLLBACK_COMPLETE requires deleting only that temporary stack before fresh CREATE. Log group Retain may survive: verify physical name/tags/retention/data before separately approved delete/import choice; do not blindly retry named creation. If Lambda VPC ENIs still release, keep execution role long enough for Lambda-managed cleanup; do not delete existing app SG/subnet/DB SG.

After approved preflight, restore concurrency 0 and revoke qualified invoke, remove runner function/versions via temporary stack, verify Lambda ENI release, delete temporary network stack (endpoint+twoSGs+ingress), verify endpoint absent so billing stops. Retain 14-day sanitized logs/evidence for audit; deleting retained logs is a separate admin approval (base operator policy lacks blanket logs deletion). Remove phase inline policies, execution role/boundary, temporary operator attachments/policies and exact human assume allow, then operator role. Verify no resource/tag remnants, no queued event work or outstanding migration session. Never delete permanent001/002 owner/history or existing workload stacks.

Unknown live schema/user/grants/history are the deliberate next read-only gate. Current operator absent, no Secrets Manager private endpoint, no uploaded new runner VersionId or qualified runner version; these are setup prerequisites, not design failures. Live RDS IAM/TLS is not proven by CI. API/auth/events/SES/alarms remain later release gates; do not claim full AWS Integration complete. No current plan blocker remains before requesting only empty-role creation.

**FINTRUST CONTROLLED RDS PREFLIGHT PLAN VERIFIED — AWAITING FIRST AWS MUTATION APPROVAL**

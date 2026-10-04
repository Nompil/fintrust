# Budget-first preparation

## Dependency review before code changes

R = required, L = legacy compatibility only, O = optional, D = removed from the proposed deployed path. CloudWatch refers to Lambda-managed stdout delivery, not a runtime SDK call.

| Lambda | RDS | S3 | SQS | DynamoDB | SES | SSM | CloudWatch | Can stay outside VPC? |
|---|---|---|---|---|---|---|---|---|
| Ingest | D: move account existence check to score; L: local CSV loader | R: read CSV/write malformed rows | R: publish validated messages | No | No | No | R: processing logs | Yes after moving account validation |
| Score | R: account check, ledger, frozen score, idempotency | R: quarantine unknown accounts | Managed polling, no SDK calls | R: immutable score projection/event source | No | D: deployment resolves nonsecret DB settings | R | No |
| Alert | D: delivery claims move to conditional DynamoDB writes; L: old direct SQL helper | No | No | R: verify score and maintain delivery state; stream trigger | R: send email | No | R | Yes with conditional delivery claims |
| Query | R: ledger/accounts | No | No | R: risk lookup | No | D: deployment-resolved DB settings | R | No |
| Report | R: SQL analysis | R: monthly exports | Managed failure destination | No | No | D: deployment-resolved DB settings | R | No |

Current ingest checks account existence in SQL before publishing. This business check will move to scoring: unknown accounts go to sanitized S3 quarantine and are acknowledged only after that write succeeds. Database/service failures remain retryable technical failures. Malformed CSV rows remain ingest quarantine. Existing local direct-loading helpers remain for teaching tools.

Current alert locks SQL delivery state. The deployed alert handler will instead consume immutable transaction projections from DynamoDB Streams and claim a separate `ALERT#<transaction UUID>` item using conditional writes. Claims commit before SES. SENT is never resent; SENDING/UNKNOWN require reconciliation; definitive rejections remain retryable. SQL remains the authoritative ledger; delivery status becomes an operational DynamoDB record. The old direct SQL alert helper is retained only for existing local tests/tools, never wired to a deployed function.

Scoring will stop synchronously invoking alert. A successful SQL write followed by a failed DynamoDB write remains a queue retry. Successful projection publication delegates email retries to the stream consumer. The alert filter accepts transaction items and ignores delivery-state items, preventing recursion. Stream processing needs its own failure capture and monitoring because email no longer controls scoring acknowledgement.

These changes remove runtime SSM, SQS, Lambda API and SES calls from private functions. Private functions use only PostgreSQL plus S3/DynamoDB gateway endpoints. Ingest and alert use AWS public service endpoints from outside the customer VPC. No NAT or interface endpoints are selected. IAM database token generation is local signing; standard Lambda polling/log delivery is service-managed.

## Implementation boundaries

Prepare and test locally only. No AWS access. Preserve original routes and SQL ledger behavior. No frontend styling, identity platform, PDF changes or deployment. Paid KMS is an intentional requirement; use one regional key. The final readiness report will distinguish built artifacts, Linux execution checks and unverified cloud behavior.

## Final readiness report

### A-B. Final dependencies and placement

The matrix above is the pre-change review. Its proposed changes are now implemented in the deployed handler path:

| Function | Runtime dependencies | Placement and reason |
|---|---|---|
| Ingest | S3 raw reads, S3 quarantine writes, SQS publishing | Outside customer VPC; no database access |
| Scoring | PostgreSQL, DynamoDB conditional projection, S3 account quarantine | Private subnets; authoritative ledger and account validation |
| Alert | DynamoDB score verification and conditional delivery claims, SES | Outside customer VPC; no database access |
| Query/API | PostgreSQL and DynamoDB point lookup | Private subnets; ledger access |
| Report | PostgreSQL and S3 report writes | Private subnets; SQL aggregation |

Lambda manages queue/stream polling, stdout log delivery and asynchronous failure destinations. Execution-role permissions for those operations remain necessary. Private handlers do not call the SSM, SES, SQS or Lambda APIs. IAM database tokens are signed locally. SSM String parameters are resolved during deployment into environment settings; missing settings fail rather than silently calling SSM.

### C-D. Connectivity and endpoint selection

| Private function | Destination | Connectivity | Cost impact |
|---|---|---|---|
| Scoring | PostgreSQL | Private address, TCP 5432, Lambda security group to DB security group | Existing RDS charges |
| Scoring | DynamoDB | Gateway endpoint, HTTPS 443 | Table requests/storage; no endpoint hourly charge |
| Scoring | S3 quarantine | Gateway endpoint, HTTPS 443 | Object requests/storage and KMS requests |
| Query/API | PostgreSQL | Same private DB rule | Existing RDS charges |
| Query/API | DynamoDB | Gateway endpoint | Table requests/storage |
| Report | PostgreSQL | Same private DB rule | Existing RDS charges |
| Report | S3 reports | Gateway endpoint | Object requests/storage and KMS requests |

Required: S3 and DynamoDB gateway endpoints. Required interface endpoints: none. SSM, SES, SQS, Lambda, CloudWatch Logs and KMS interface endpoints are avoided in this design. S3 performs KMS operations for encrypted objects; applications do not call KMS directly. No NAT gateway, internet gateway or custom NACL is introduced. Gateway policies, IAM permissions and security-group egress must all agree. Prefix-list IDs, region, route associations and existing network compatibility remain deployment-time checks. See [gateway endpoint documentation](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html).

### E. Cost decisions

- NAT: none. Interface endpoints: none, avoiding their hourly/AZ charges.
- KMS: one regional customer-managed key shared by the three data buckets. This is intentionally paid encryption; the published base key charge is USD 1/month, plus request charges and eligible rotation charges. S3 Bucket Keys reduce request volume. Verify regional pricing before approval; this is not an account bill estimate. See [KMS pricing](https://aws.amazon.com/kms/pricing/).
- RDS: existing instance, storage, backups and retained snapshots are likely the largest standing costs. No new instance is provisioned by the foundation. Stopping a database is not permanent cost elimination; agree a teardown/snapshot plan separately.
- CloudWatch: function logs retain 14 days; ingestion, storage, metrics and alarms can still incur charges. Alarm resources and delivery channels remain to be configured.
- S3: versioning and retained buckets protect evidence but grow storage. Requests, Glacier transitions/retrieval and retained noncurrent versions cost money. No automatic deletion policy was invented.
- DynamoDB uses on-demand billing and AWS-owned encryption; delivery state has no TTL. SQS, SES, Lambda and API Gateway incur usage charges. Consumers and the report schedule default to disabled to prevent accidental processing. Regional budgets, concurrency limits and alert thresholds need owner approval before enabling traffic.

### F. Packaging evidence

One shared archive supports ingest, scoring, alert, API and report. Dependencies are pinned for Python 3.12 / Linux x86_64; the build uses binary wheels and includes the SQL query, frontend files and official RDS CA bundle. A supplied wheelhouse supports offline builds. ZIP entry ordering and timestamps are fixed; identical-input reproducibility across different build hosts is not yet proven.

The local build succeeded: compressed 21,896,702 bytes; uncompressed 37,314,453 bytes. SHA-256: `462315d4c4c03282d20a63e43ac14fb0df8d9dcf1a61026e974be88e24d6c5a3`. Handler/assets presence, Linux CPython driver signature, CRC and Lambda archive size checks passed. Files are in `build/fintrust.zip` and `build/fintrust.manifest.json`, excluded from Git.

Linux handler execution is not yet verified. The manual build-only workflow runs `tools/verify_lambda_linux.py` on Linux Python 3.12, imports the archived handlers in isolation with network calls blocked, and marks the matching manifest only after success. That workflow has not been run remotely. No package has been uploaded to AWS.

### G. Security preparation

Prepared locally: scoped IAM policies and trust; private subnet/route definitions; DB ingress only from the Lambda security group; RDS TLS parameter group; database service grants; nonsecret SSM parameter rendering; API IAM authorization; public-access-blocked, versioned, retained S3 buckets; and one rotating CMK with service/context restrictions in execution-role grants.

Bucket policies reject HTTP, explicit non-KMS encryption, another KMS key, explicit KMS encryption without a key ID, and customer-provided encryption keys. Omitting encryption headers uses the configured bucket CMK. The key-policy account-root statement delegates administration through IAM; it is not an execution-role wildcard grant. Existing policies, database logins and resources still require live validation after approval. Ingest and alert have no RDS or ENI permissions in the new policies.

### H. Lifecycle and recovery

Business plan: keep the operational ledger in RDS for 12 months; export eligible closed periods to S3 Standard for three years; then retain in Glacier Flexible Retrieval for seven years. The template transitions `archive/` objects after 1,095 days in S3. This is a fixed-day approximation to three years, not a calendar-anniversary calculation. Monthly reports use `monthly/` and are not a substitute for the full ledger archive.

The RDS archival/export job is not implemented. Before deleting any ledger records it needs checksums, row counts, reconciliation, a restore test and reviewed handling of idempotency keys and foreign keys. No automatic cold-tier expiration is configured because the seven-year retention boundary and deletion authorization are not yet settled. Quarantine is separate: retained, encrypted, versioned, restricted access, no arbitrary expiry. Owners must approve investigation and disposal rules.

Alert recovery: SENT must not be replayed. SENDING or UNKNOWN requires operator reconciliation with provider evidence; a missing response does not prove an email was not sent. Record the transaction, attempt ID and evidence. Only a confirmed non-send can be conditionally changed to FAILED, matching the current attempt/state, before replay. If uncertain, leave it held. Definitive rejection is retryable. Exhausted stream deliveries go to the failure queue; stream records are not permanent history, so delayed recovery must use the immutable table projection. Monitoring, a reviewed reconciliation command and a recovery exercise are required before production.

### I. Dashboard authentication

Keep data methods protected by AWS_IAM. The existing browser fetch calls do not sign SigV4 requests and therefore cannot directly use that deployed API. For an assessment, the smallest secure extension is a loopback-only local proxy using short-lived operator SSO credentials to sign requests server-side, with explicit origin checks and no credentials exposed to JavaScript. This proxy is a recommendation, not implemented functionality. For broader stakeholder access, select a managed login approach in a separate task. An API key controls usage and does not replace authentication.

### J. Validation

Full disposable-database run: **149 passed, 0 failed, 1 skipped** using `tools/local.py test --database`. The skipped service-role execution check requires a disposable database administrator. The original baseline was 129 passed, 0 failed, 1 skipped. Added coverage includes conditional delivery races, uncertain sends, frozen projections, quarantine retries, placement, encryption policy gaps, offline parameter generation and incompatible package rejection. Foundation and processing JSON rendered successfully; `git diff --check` passed. These are local/mocked checks, not AWS integration evidence.

### K. Deployment gates

**P0 — before deployment approval:** run Linux archive verification; review actual resource inventory/import plan, RDS engine/subnets/IAM logins and CA connectivity; validate IAM and CloudFormation against the target account; provide actual parameter and ARN values; verify SES identities/region/sandbox constraints; choose the authenticated demonstration path. No deployment is approved.

**P1 — before consumers or schedules are enabled:** configure failure/backlog/held-delivery alarms and recipients; approve concurrency/spend limits; exercise queue replay and uncertain email reconciliation; test service-role DB grants and end-to-end cloud behavior; reconcile existing S3 notifications without removing unrelated bindings. Archive automation and restore evidence are required before any age-based ledger deletion.

**P2 — follow-up:** automate archival retention after owner decisions; add broader stakeholder identity if needed; align older presentation artifacts and legacy helper documentation with verified deployment evidence. Existing standalone provisioners remain superseded, not part of this rollout.

### L-M. Proposed deployment sequence — not executed

1. Obtain separate approval for account access, region, cost ceiling and deployment scope.
2. Inventory existing resources, review import/change sets and rollback/backup requirements.
3. Verify the Linux package and record its checksum and dependency evidence.
4. Apply reviewed foundation changes and validate private routes, gateway policies and encryption.
5. Reconcile the existing private RDS instance, enforce TLS/IAM authentication, apply reviewed schema/grants and provision only scoring/api/report logins.
6. Store the three services' nonsecret parameters; create scoped roles and pre-created log groups; verify SES identities and failure destinations.
7. Deploy processing functions with consumers/schedule disabled; supply the package hash for the API version. Deploy the restricted API against its alias.
8. Test authenticated requests, DB TLS, object encryption and service permissions; merge only the intended raw CSV notification binding.
9. Enable controlled synthetic processing, verify retries/reconciliation/report outputs and alarm delivery, then approve normal consumer/schedule settings.
10. Capture evidence and enforce the agreed cost/cleanup plan.

Stop here. No AWS account access, provisioning, deployment or push was performed.

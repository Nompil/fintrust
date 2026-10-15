# FinTrust deployment readiness

Status: repository audit complete; Phase 2 implementation is pending the network/cost decision below. No AWS account inventory, connectivity check, deployment or resource modification was performed. Repository definitions are not evidence of deployed configuration.

The last verified application baseline is 129 passed, 0 failed, 1 skipped. This audit changes no runtime code and does not repeat that test run.

## Deployment matrix

Costs below classify exposure, not Free Tier eligibility. Account plan, remaining credits, region, usage and resource inventory must be checked before any deployment.

| Component | Current state | AWS requirement | IAM role | Network requirement | Cost risk | Blocker / Action |
|---|---|---|---|---|---|---|
| S3 raw | Bucket script enables versioning, public access block and raw lifecycle | Customer-managed encryption, TLS-only policy, access logging | Ingest read; uploader separately scoped | S3 gateway endpoint for private ingest | LOW RISK; versions/archive WATCH | Script lacks KMS, TLS policy and logging; inventory existing bucket first |
| S3 quarantine | `quarantine/` prefix in raw bucket; not a separate bucket | Restricted access, sanitized provenance, retention and review | Ingest write; explicit reviewer role later | Same S3 gateway endpoint | LOW RISK | No quarantine lifecycle; choose prefix isolation or separate bucket explicitly |
| S3 reports | Existing bucket assumed by template | Public access block, encryption, TLS, version/retention decision | Report write `monthly/*`; reviewer read | S3 gateway endpoint | LOW RISK | No reconciled bucket definition |
| KMS | Customer-managed key required by project requirements; not defined | One regional symmetric key initially, scoped use and administration | Ingest decrypt raw/generate quarantine data keys; report generate data keys; storage service grants as needed | S3/RDS service-mediated encryption does not imply direct Lambda KMS API calls | WATCH | Approve recurring key cost; key policy and IAM currently absent |
| Ingest Lambda | Account existence checked in PostgreSQL; FIFO publishing implemented | Linux package, IAM auth, raw notification | `fintrust-ingest-<stage>` | RDS, S3, SQS and SSM | LOW RISK | Needs VPC with current account validation; cannot simply detach |
| SQS FIFO | Explicit dedup hash, group=account UUID, visibility 720s, batch 5 | Matching IAM, mapping and queue policies | Ingest send; scoring receive/delete/attributes | Ingest SDK needs SQS route; Lambda-managed polling is separate | LOW RISK | Mapping currently enabled by default; disable during initial provisioning |
| SQS DLQ | FIFO technical-work DLQ after 5 receives; standard ingest/report failure queues | Restricted replay process, alarms, retention | Operator replay; service-specific destination send | SDK replay tool needs SQS access | LOW RISK | Legacy ingest DLQ names differ; reconcile one resource owner |
| Scoring Lambda | SQL transaction, DynamoDB projection, synchronous alert invocation | Package, bounded concurrency and correct runtime | `fintrust-scoring-<stage>` | RDS, DynamoDB, Lambda API, SSM | LOW RISK | No route supplied for Lambda API or SSM |
| RDS PostgreSQL | Schema, grants and TLS client code; no instance definition | Private, encrypted, IAM auth, approved small instance/storage, backups | All five service DB users | TCP 5432 from Lambda DB SG only | WATCH | Actual instance configuration unknown; administrator setup required |
| DynamoDB | On-demand table script and TTL enabled | Explicit billing/encryption choice, correct account/score key | Scoring put; query get/query | DynamoDB gateway endpoint | LOW RISK; capacity WATCH | Script name env differs from runtime; TTL enabling alone does not expire items without TTL values |
| Alert Lambda | SQL delivery claim/state and SES API send | Preserve uncertain-delivery reconciliation | `fintrust-alert-<stage>` | RDS, SES API, SSM | LOW RISK | Requires VPC today; SES API endpoint availability in target region must be verified |
| SES | Sender/recipient environment contract, scoped send policy | Verified regional identities; sandbox sufficient for small assessment | Alert only | API HTTPS 443; SMTP endpoint is not a replacement for current API client | LOW RISK | Verification/quota state unknown; no production-access request needed yet |
| Query Lambda | Existing routes; separate API workflow | Alias, Linux dependencies, CA, VPC and service identity | `fintrust-api-<stage>` | RDS, DynamoDB, SSM | LOW RISK | Python 3.11 workflow versus processing 3.12; query not created by processing template |
| API Gateway | REST template, IAM auth on data routes, public health, throttles 10/s burst 20 | Approved caller identity, access logs, alias and stage | Caller execute-api; gateway resource invocation permissions | Public API; managed invocation into private Lambda | LOW RISK; detailed metrics WATCH | Browser uses unsigned fetch; IAM-protected cloud routes cannot work unchanged. Template lacks OPTIONS preflight routes |
| Report Lambda | Reuses monthly SQL; deterministic S3 keys | SQL and CA in Linux archive | `fintrust-report-<stage>` | RDS, S3, SSM | LOW RISK | No complete build artifact; CSV/JSON pair not atomic |
| EventBridge | Monthly rule and invoke/failure permissions defined | Initially disabled schedule; explicitly enable after verification | Events service scoped to report/failed delivery | Managed invocation; no Lambda endpoint needed just to receive schedule | LOW RISK | Rule currently ENABLED by default |
| CloudWatch | Structured application logs; separate ingest alarm script; API logs 30 days | Processing retention, consistent names, error/DLQ alarms, queries | Each function writes own log group | Standard Lambda stdout delivery is managed; direct SDK calls need their own route | WATCH | Processing log groups lack retention; old monitor names differ; custom metric cost |
| X-Ray | No tracing configuration in processing template | Confirm requirement, sampling and scoped write actions | Functions if tracing selected | Distinguish managed tracing from direct SDK delivery | WATCH | Not implemented; do not claim traces |
| SSM | Canonical per-service DB host/name/user String paths | Provision exact paths; deployment values or private runtime access | Each function reads its own three paths | SSM interface endpoint if runtime lookup retained | LOW RISK; endpoint WATCH | Runtime fallback currently needs paid connectivity without egress |
| Secrets Manager | Not used | No application DB password secret with IAM auth | None | No endpoint needed | AVOID unnecessary resource | Administrator credential handling remains operator responsibility |
| IAM roles | Five scoped offline policy outputs | Create/import matching stage names and trust; KMS policy additions | Five functions, deployment and operators separated | ENI permissions only for attached functions | LOW RISK | Logical Score/Query names map to code scoring/api; do not create duplicate roles |
| VPC | Existing VPC assumed | One VPC, DNS resolution/hostnames enabled | Deployment role | Private internal routes; no NAT | LOW RISK | No network template or evidence |
| Private subnets | Supplied as parameters | Two AZs for RDS subnet group; DB/application separation | Deployment role | Proposed application A/B and isolated DB A/B | LOW RISK | CIDRs/AZs must be chosen against inventory |
| Route tables | Not defined | DB local routes; application local + gateway endpoint routes | Deployment role | No IPv4 default internet/NAT route | LOW RISK | Interface endpoints or validated alternative still needed |
| Security groups | Arbitrary supplied IDs | Lambda DB SG, RDS SG, endpoint SG if selected | Deployment role | RDS inbound 5432 from Lambda SG; endpoints inbound 443 from Lambda SG | LOW RISK | Explicit outbound rules required; no public PostgreSQL CIDR |
| RDS subnet group | Not defined | DB subnet A + B, publicly accessible=false | Deployment role | Private placement across two AZs | LOW RISK | Two-AZ subnet coverage does not require paid Multi-AZ DB deployment |
| GitHub Actions / packaging | Manual API deploy workflow; pinned direct dependencies | Build-only Linux artifacts, SQL, CA, smoke imports, size/checksum manifest | Build no AWS role; deployment OIDC separately | Dependency/CA downloads on build runner | LOW RISK; runner minutes WATCH | Current workflow deploys when dispatched; must not run for readiness; missing CA/report SQL |

## Network decision before infrastructure changes

All five services currently need RDS. Ingest reads accounts before accepting jobs; alert locks the processing record and updates delivery state. Preserve these guarantees unless an explicit redesign is selected.

Proposed private layout: one VPC, two application subnets and two isolated DB subnets across two AZs. RDS is not publicly accessible. RDS SG accepts 5432 only from the Lambda DB SG; application egress permits 5432 to RDS and HTTPS to approved endpoint destinations. Default NACLs are adequate initially; custom stateless filtering would add complexity without an identified requirement.

| Function | Placement with current code | Required outbound calls | Without NAT |
|---|---|---|---|
| Ingest | Application A/B, Lambda DB SG | RDS, S3, SQS, SSM | S3 gateway; SQS/SSM interfaces or approved alternative |
| Scoring | Application A/B, Lambda DB SG | RDS, DynamoDB, Lambda invoke, SSM | DynamoDB gateway; Lambda/SSM interfaces or approved alternative |
| Alert | Application A/B, Lambda DB SG | RDS, SES API, SSM | SES API/SSM interfaces or approved alternative |
| Query | Application A/B, Lambda DB SG | RDS, DynamoDB, SSM | DynamoDB gateway; SSM interface or deployment-resolved settings |
| Report | Application A/B, Lambda DB SG | RDS, S3, SSM | S3 gateway; SSM interface or deployment-resolved settings |

IAM DB tokens are signed locally, so token generation itself does not require an RDS control-plane endpoint. SQS polling, event delivery and standard Lambda log transport must not be confused with calls made by function code. No Secrets Manager endpoint is required. No direct KMS endpoint is needed solely for S3/RDS encryption performed by those services.

S3 and DynamoDB gateway endpoints have no endpoint charge. Interface endpoints have per-AZ hourly and data-processing charges. Four interfaces (SSM, SQS, Lambda, SES API) across two AZs mean eight billed endpoint/AZ instances, even while idle. Resolving the three nonsecret DB settings into Lambda environment variables at deployment could eliminate runtime SSM access and reduce this to six. This is a proposal, not an implemented configuration change.

Cost illustration only: at $0.01 per endpoint/AZ-hour, eight instances for 730 hours cost $58.40; six cost $43.80, before processing/tax. This is not a verified Cape Town quote. Verify af-south-1 service availability and regional prices before approval. Current AWS SES documentation supports API endpoints selected by `email`; do not assume an SMTP endpoint supports boto3 `ses.send_email`.

Cheaper alternatives to evaluate before committing to interface endpoints: deployment-resolved nonsecret configuration; dual-stack application egress where every required regional service and SDK supports it; or moving selected duties outside the VPC. Dual-stack is not yet proven here. Moving ingest/alert outside requires replacing their SQL validation/delivery-state access, with new consistency and failure tests. Do not drop these guarantees to save an endpoint. No NAT gateway, NAT instance, public RDS or paid proxy is selected.

## Configuration and security reconciliation still required

- Canonical service IDs: ingest, scoring, alert, api, report; stages dev/staging/prod. IAM roles `fintrust-<service>-<stage>`; DB logins `fintrust_<service>_<stage>`.
- SSM `/fintrust/<stage>/<service>/db_host`, `/db_name`, `/db_user` are nonsecret Strings. `DB_PORT` defaults to 5432. AWS uses IAM auth and `DB_SSLROOTCERT=/var/task/certs/global-bundle.pem`; local password auth remains local only. Decide deployment resolution versus runtime lookup once.
- Environment configuration: `FINTRUST_SERVICE`, `FINTRUST_STAGE`, AWS region, DB auth/port/CA; ingest `TRANSACTION_QUEUE_URL`; scoring `DYNAMODB_TABLE`, `ALERT_FUNCTION_ARN`, all `RISK_*` settings; alert `SES_SENDER`, `SES_RECIPIENT`; report `S3_REPORT_BUCKET`; query `DYNAMODB_TABLE`, approved `CORS_ALLOWED_ORIGINS`. Resolve legacy `FINTRUST_INGEST_BUCKET`/`FINTRUST_DDB_TABLE` defaults against template inputs rather than silently selecting different resources.
- The project explicitly requires customer-managed KMS for S3. Propose one regional symmetric key with separate administrator and service-use statements, service/account conditions and appropriate encryption context. Reusing it for RDS needs reviewed service grants; DynamoDB can retain service-owned encryption unless the rubric requires otherwise. No keys created. A new customer-managed key starts at $1/month plus applicable requests; rotation can increase storage charges.
- Raw lifecycle currently transitions after 90 days and expires after 2,555 days. This is code, not a verified bank retention policy. Quarantine has no expiry, reports/logs need explicit retention, and versioned deletion needs noncurrent-version handling. Access-log destination is also missing. Do not automatically overwrite existing lifecycle/notification policies.
- Notification script removes other bindings targeting the same function; the processing metadata uses another notification ID. Reconcile ownership and preserve unrelated bindings before activation.
- RDS administrator: apply schema, apply scoped role grants, create each restricted stage LOGIN, grant its service role and `rds_iam`, provision matching configuration, then run role-isolation checks from an approved private execution path. The skipped test checks `rolsuper`; an RDS administrator is not a true PostgreSQL superuser, so the test harness needs a capability-based adaptation before it can serve as RDS evidence. Do not grant superuser to application accounts.
- Current DB connections open per operation and close afterwards. Bound Lambda concurrency against the selected DB connection limit before choosing a paid RDS Proxy. Verify server-side TLS enforcement as well as the existing client `verify-full` setting.
- API routes remain intact. IAM auth requires a signed caller; the existing unsigned dashboard needs an approved authentication/integration plan before a cloud browser demo. Never embed long-lived AWS keys in the browser. Review gateway logging account role, OPTIONS handling and stage redeployment when methods change.
- Package processing Python 3.12 and API Python 3.11 separately, or explicitly migrate both with tests. Include `fintrust/`, `src/`, runtime dependencies, report SQL and CA; frontend assets remain required by the current API package. Verify wheel ABI/architecture, imports in the matching Lambda Linux runtime, zipped/unzipped size, dependency resolution and checksum manifest. Direct dependency pins exist; transitive hash locking is not yet present.
- SES sandbox can be sufficient: verify sender and recipient identities in the sending region, obey quotas and retain the existing SENT/FAILED/UNKNOWN reconciliation behavior. No production request proposed.

## Cost gates and next sequence

| Classification | Resources / controls |
|---|---|
| FREE for the control itself | Gateway endpoints; no claim that the S3/DynamoDB workload is free |
| LOW RISK at assessment volume | Lambda, SQS, S3 requests, API requests, SES, EventBridge; all remain usage/eligibility dependent |
| WATCH | RDS uptime/storage/backups; customer KMS key and requests; DynamoDB on-demand usage; log storage/queries; metrics/alarms/traces; S3 versions/archive minimums; transfer; interface endpoint hours; CI minutes |
| AVOID | NAT Gateway; unnecessary Secrets Manager, RDS Proxy, Multi-AZ instance, interface endpoints and duplicate infrastructure |

Approval requested: choose a budget-first connectivity investigation without implementing paid endpoints, or authorize drafting a private-endpoint design with an explicit recurring-cost ceiling. Neither choice authorizes deployment. The customer-managed KMS cost also needs acceptance before its implementation under the Phase 2 cost gate.

After that decision: reconcile network/configuration and resource ownership; implement offline templates and Linux packaging; add targeted security/configuration tests; run the full local regression suite once; deliver the final Phase 2 report. Deployment remains a separate approval. Proposed later deployment order: billing safeguards, network, KMS/storage, RDS/grants/configuration, DynamoDB, queues, functions with triggers disabled, API/SES verification, monitoring, controlled trigger activation, then end-to-end verification. Keep the monthly schedule disabled until explicitly required.

## Sources

- [Lambda VPC networking](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html): a public subnet does not give Lambda a public IP or internet access.
- [Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html): S3/DynamoDB gateway connectivity and endpoint charging.
- [PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/): endpoint/AZ hours and data processing; illustration is not a regional quote.
- [SES VPC endpoints](https://docs.aws.amazon.com/ses/latest/dg/send-email-set-up-vpc-endpoints.html): API versus SMTP connectivity.
- [SES sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html): identity restrictions and sending limits.
- [KMS pricing](https://aws.amazon.com/kms/pricing/): customer-managed key storage and request charges.

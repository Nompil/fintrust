# Deployment bootstrap and cost gate

Status: **STAGE 0 CONFIGURATION VERIFIED; STAGE 1 READY FOR REVIEW ONLY.**

Continues the completed inventory at commit
`65614ba14c22aed251a8498e34b60ef18cef68be`. The verified Linux CI result remains
178 passed, zero failed, zero skipped, with the matching package marked
`linux_execution_verified: true`. CI, inventory, GitHub setup and earlier phases
were not repeated. The current review used read-only STS, RDS orderability and Free Tier plan calls,
plus the public regional pricing catalogue, Access Analyzer policy validation and
CloudFormation template validation. Saved Stage 0 evidence was reused. No AWS resources were changed.

Account `966467878406`, region `af-south-1`, one `dev` assessment environment.
The local inventory and reconciliation evidence remains in ignored
`build/aws-inventory/REPORT.md`. It found no RDS or FinTrust application resources;
the default public network and unrelated DataSync buckets must remain untouched.

## A. Deployment identity recommendation

Use `fintrust_deployer` with MFA and browser/CLI temporary credentials to assume
`fintrust-deployer-role`. Keep `fintrust-inventory` read-only. No access keys,
AdministratorAccess, PowerUserAccess, GitHub AWS credentials or OIDC are needed.

[Deployment identity design](iam/DEPLOYER_DESIGN.md) supplies the trust policy,
user policy, stage-specific role permission specification and acceptance checks.
Only an authorized administrator bootstraps these identities. The deployer cannot
expand its own permissions. The billing administrator creates the safeguards.
Stage 1 requires no IAM PassRole or persistent CloudFormation execution role.

Saved read-only evidence confirms the MFA-constrained trust, zero deployer keys,
only the exact-role assume grant, and no role permissions attached. The owner
reports successful role assumption; this review did not repeat it. The CloudFormation and DB-subnet policies and preceding network revision passed
Access Analyzer with no findings; final narrowed network-policy revalidation is
pending because the login expired. The split network template passed CloudFormation validation. See the identity design for
exact JSON, action rationale, mismatches and limits of those checks.

## B. RDS recommendation

| Setting | Proposed value and reason |
|---|---|
| Identifier / database | `fintrust-ledger-dev` / `fintrust`; one instance |
| Engine | PostgreSQL 16, parameter family `postgres16`; pin a supported, orderable 16.x minor version at the Stage 3 review. Do not silently use an AWS default or substitute another region |
| Instance | **`db.t4g.micro`**, 2 vCPU, 1 GiB RAM; the smallest Free Plan-supported Graviton option, for a bounded sequential demo. Capacity acceptance is still required |
| Alternatives | `db.t3.micro` has the same 1 GiB memory and costs more here. `db.t4g.small` remains a memory fallback requiring separate paid-plan/cost review; it is not the default |
| Availability | Single-AZ, `MultiAZ=false`; no replica, proxy or Aurora. Two-AZ subnet group provides placement options, not high availability |
| Storage | **5 GiB gp2**, confirmed regional minimum; no storage autoscaling or provisioned IOPS. Small synthetic data only; stop loading below 2 GiB free space. Review growth before increasing capacity. A 20 GiB gp3 alternative costs USD 2.265/month more |
| Encryption | `StorageEncrypted=true`, prefer the regional AWS-managed `aws/rds` key. No separate customer-managed key is required for this single-account demo. This changes the RDS proposal only; existing S3 CMK policies must be reviewed separately before Stage 2 |
| Network | `PubliclyAccessible=false`, IPv4 private endpoint, `fintrust-db-dev` subnet group across `af-south-1a` and `af-south-1b`; DB security group accepts TCP 5432 only from the application SG and a separately reviewed temporary bootstrap SG |
| Authentication / TLS | IAM DB authentication enabled, `rds.force_ssl=1`, clients use `verify-full` and the bundled RDS CA. Distinct `fintrust_scoring_dev`, `fintrust_api_dev`, `fintrust_report_dev` logins get `rds_iam` plus their corresponding least-privilege SQL group |
| Administrator secret | Recommend RDS-managed master secret in Secrets Manager, with its separate storage/API cost disclosed. No master password in Git, parameters, outputs, shell history or application environment. Retrieval only by the later bootstrap process |
| Backups | One-day automated retention for synthetic assessment data, copy tags to snapshots. Final snapshot on approved teardown; retain it only for the explicitly agreed evidence/restore period |
| Protection | Deletion protection on; CloudFormation deletion/replacement snapshot policies. Teardown requires separate approval to disable protection, export/reconcile and verify restore evidence |
| Maintenance | Automatic minor upgrades on within PostgreSQL 16; major upgrades off. Standard support only; no automatic paid Extended Support enrollment |
| Monitoring | Standard metrics plus 14-day application logs initially; no paid enhanced monitoring/advanced database insights selected. Essential DB/memory/storage/connection alarms before workload |

AWS documents [instance memory sizes](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.Summary.html)
and [300–1000 MiB additional memory for IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html).
Micro is a cost-first candidate, not a measured capacity result. IAM support is
confirmed by the regional orderability API; sufficient memory is not. If the
bounded workload cannot retain memory headroom, stop and review configuration
and budget rather than disable IAM authentication or silently resize.
RDS's Arm processor does not require changing the x86_64 Lambda package: the
application communicates with PostgreSQL over its network protocol.

Keep the engine's default `max_connections`; record the actual value before
enabling consumers. Do not assume a fixed connection count from instance memory
or raise it to hide overload. For the micro trial, propose reserved concurrency 1 per DB-using function and
exercise scoring, API and report sequentially; do not enable background schedules.
These are deployment requirements, not changes already applied to processing.py. Current SQL helpers close
connections and scoring processes records sequentially. Confirm all deployed paths
before setting a measured concurrent-connection limit, and leave room
for bootstrap/admin connections and engine overhead. Account concurrency quotas
can prevent reservations; stop rather than deploy without the reviewed limits.
Record memory, DB connections and burst-credit balance during the small demo.

### Private database bootstrap is a real dependency

The laptop cannot directly reach this database through gateway endpoints. Do not
add public access, an IGW, NAT or paid interface endpoints merely to run SQL.
Recommend a separately reviewed, temporary VPC-attached migration Lambda with
concurrency 1 and no triggers. An authorized local operator retrieves the master
secret and supplies it through an in-memory invocation payload, never CLI literals,
logs or artifacts; the runner must redact events/errors and close the connection.
It applies the reviewed schema and service grants, then its temporary role,
function and DB ingress are removed. This is a proposal, not implemented or invoked.
It adds a temporary bootstrap Lambda in Stage 3, distinct from the five runtime
functions, and requires explicit approval and a credential-handling review.

Review the untracked `infrastructure/rds/schema.sql` separately before use; it
has not been staged or adopted. Verify the canonical schema, account seed data,
least-privilege role tests and restore procedure before claiming the DB ready.

## C. Budget and cost controls

### Free Tier-first decision and account evidence

Use AWS Free Tier wherever practical. Paid resources require a demonstrated
project need and separate approval; credits are a reserve, not a spending target.
The read-only `freetier get-account-plan-state` response confirms this account is
`FREE` / `ACTIVE`, with **USD 120 remaining**. Remaining credit and duration change;
recheck them immediately before Stage 3. No account-plan upgrade is authorized.

[AWS RDS Free Tier](https://aws.amazon.com/rds/free/) lists `db.t3.micro` and
`db.t4g.micro` for PostgreSQL on the Free Plan. This account uses the **credit-based
plan**, not the legacy 12-month allowance. RDS usage consumes credits; there is no
independent recurring allocation of 750 RDS hours or 20 GiB storage to assume here.
Under the [Free Plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html),
access ends when credits or plan time run out. Preserve exports/evidence before
that boundary. Do not upgrade automatically to preserve running infrastructure.

For comparison only, the [legacy RDS offer](https://aws.amazon.com/rds/pricing/)
provides eligible accounts 750 Single-AZ micro hours, 20 GB gp2 and 20 GB automated
backup storage per month during its qualifying period. Allowances are shared,
not per instance; gp3 must not be assumed included. That is not this account's offer.

### Regional availability and standing cost

Read-only `DescribeOrderableDBInstanceOptions` in `af-south-1` returned
`db.t3.micro`, `db.t4g.micro` and `db.t4g.small` for PostgreSQL **16.14**, with IAM
authentication and storage encryption supported. The t4g.micro query also returned
other 16.x minors. Recheck the chosen minor's standard-support status and pin it
at Stage 3; do not interpret availability as deployment approval or guaranteed capacity.
No smaller PostgreSQL micro class is proposed; changing engines to obtain another
free offer would not preserve the existing PostgreSQL application.

The [public Cape Town RDS catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/af-south-1/index.json)
was checked again. These are Single-AZ on-demand costs **before credits**:

| Candidate | Compute/hour | 730 hours + 5 GiB gp2 | Free Plan-listed class |
|---|---:|---:|---|
| **db.t4g.micro** | USD 0.021 | **USD 16.085** | Yes; uses credits |
| db.t3.micro | USD 0.024 | USD 18.275 | Yes; uses credits |
| db.t4g.small | USD 0.041 | USD 30.685 | Not listed for the Free Plan; no automatic upgrade |

Both gp2 and gp3 are USD 0.151/GiB-month here. The API and the engine-specific
[storage table](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html)
agree on **5 GiB minimum gp2** and **20 GiB minimum gp3**. gp2's small-volume
baseline is 100 IOPS with burst credits; gp3 provides 3,000 baseline IOPS. Five GiB
is a demo proposal, not a production retention design. The seed contains only
five accounts and 200 transactions; cap further synthetic loading and measure
actual database/WAL/storage usage before the demo. Do not assume all 5 GiB is
available for application rows.

Recommended compute + storage: **USD 16.09/month** rounded at 730 running hours.
With 20 GiB gp3 it would be **USD 18.35/month**. The previous small/20 GiB estimate
of USD 32.95 is superseded. A conservative short-demo estimate is
`24 * 0.021 + 5 * 0.151 = USD 1.259`: 24 running hours plus a full month of storage.
Stopped 5 GiB storage alone is USD 0.755/month while retained. Storage is billed
for provisioned capacity over time, not merely rows inserted.

These subtotals exclude burst CPU charges, extra/retained backups, Secrets Manager,
KMS requests, monitoring, transfer and tax. They are credit consumption estimates,
not a promise of a zero bill or an allowance to exhaust the USD 120 balance.
T3/T4g sustained CPU in Unlimited mode can add charges. Single-AZ only: no replica,
RDS Proxy, Aurora, Multi-AZ, extra IOPS, enhanced monitoring or paid Extended Support.

One-day automated backup retention remains proposed. General backup allowances
are tied to provisioned database storage in the region; retained snapshots or
backups after deletion can continue costing money. Do not assume a permanent
20 GiB free backup allowance on this account. Review the [backup pricing](https://aws.amazon.com/rds/postgresql/pricing/)
and measured backup footprint at Stage 3. The proposed managed master secret
also has a separate charge and must be explicitly included before approval.

**Stage 3 is conditionally acceptable under Free Tier-first guidance** for this
credit-funded micro demo, not as an always-free database. Before creation, agree
at most 24 initial running hours, verify current credit/plan headroom, and approve
the complete estimate including bootstrap/secret/monitoring costs. A later IAM/TLS
smoke test must pass without OOM/restarts, with measured memory, connection,
CPU-credit and storage headroom. If it fails, stop and review; small is not an
automatic fallback. Local PostgreSQL remains the no-AWS-cost development option.

After each approved session, disable consumers/schedules before stopping RDS.
[RDS restarts after seven stopped days](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html);
set an owner reminder before that deadline. Stop is not cleanup: storage persists.
After evidence/export/restore checks, obtain teardown approval, delete the instance
and review final snapshots/retained backups and secrets individually. Keep budget
alerts until residual storage costs are resolved; never delete ledger evidence
just to meet the budget.

### Verified safeguard and remaining billing checks

Saved successful reads confirm the account-wide fixed monthly **USD 10** budget
`FinTrust-Monthly-Budget`, actual-cost thresholds 50/80/100 and forecasted 100,
with an email subscriber for each. This replaces the old proposed budget name.
The existing Zero-Spend Budget is untouched. Notification configuration is not
proof of inbox delivery. The saved response does not establish credit/refund
exclusion, so confirm gross usage remains visible before paid stages. Check the
Free Tier remaining-credit balance as well as budget spend; credits can mask a bill.
USD 10 is an alert threshold, not permission to spend or an exact R200 equivalent.

- For the rubric's billing alarm, separately configure `AWS/Billing`
  `EstimatedCharges`, `Currency=USD`, Maximum over 6 hours, one evaluation period,
  threshold equal to the approved USD budget, missing data treated as missing.
  Enable billing alerts through the billing administrator and use a confirmed
  email subscription on a named billing SNS topic. This alarm/topic is in
  **us-east-1 only**, the documented global billing exception; application resources
  remain in Cape Town. This also needs Stage 0 approval and a small cost allowance.
- At 50%: inspect burn rate and remaining demo hours. At 80%: suspend new paid-stage
  approvals, finish the necessary evidence and plan teardown. At 100%: no further
  workload without explicit review. These are operator actions, not automatic
  deletions. Do not use automatic budget actions that could destroy evidence.
- Check Billing before and after each paid demonstration; agree a named owner,
  maximum running hours and cleanup reminder before creating RDS. No savings plan,
  reserved instance or long-term commitment for this assessment.

[AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
can notify after costs have already accrued: it is not a hard spending cap.
The [CloudWatch billing alarm](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/monitor_estimated_charges_with_cloudwatch.html)
uses global estimated USD charges from us-east-1 and does not forecast spending.
Neither proves the remaining credit allowance or guarantees an R200 final bill.

## D. Stage 1 network resources

The approved planning scope now separates application and database subnets.
[network.py](network.py) renders Stage 1 independently of the combined foundation.

| Resource | Exact proposed shape |
|---|---|
| Stack | `fintrust-network-dev`; `Project=FinTrust`, `Environment=dev` tags |
| VPC | `10.42.0.0/16`, DNS support/hostnames enabled, default tenancy |
| Application subnets | `10.42.0.0/24` and `10.42.1.0/24`, two distinct AZ inputs, no public IP assignment |
| Database subnets | `10.42.2.0/24` and `10.42.3.0/24`, same two AZs, no public IP assignment |
| Route tables | Separate application/database tables; four explicit associations; local routes only except app gateway routes |
| Application SG | No ingress; TCP 5432 to DB SG; TCP 443 to regional S3/DynamoDB prefix lists |
| DB SG | TCP 5432 ingress from application SG only; inert loopback egress suppresses default allow-all |
| DB subnet group | `fintrust-db-dev`, database subnets only; no DB instance or parameter group |
| S3 / DynamoDB endpoints | Gateway only; application route table only; account-scoped policies for deterministic future data-resource ARNs |

Known inventory prefix-list IDs are `pl-a3ac49ca` (S3) and `pl-d6ae4bbf`
(DynamoDB). Keep them deployment parameters and validate their service/region
before execution; do not bake them into portable code. AZ selection also remains
a parameter with the reviewed two distinct AZs supplied for this account.

No Internet Gateway is required. Private functions call RDS and gateway-supported
S3/DynamoDB APIs; ingest and alert run outside the customer VPC. Lambda-managed
polling/log delivery does not require private functions to reach the internet.
No default internet route, NAT, interface endpoint, public IP or bastion is planned.
[Gateway endpoints have no additional endpoint charge](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html);
underlying data-service usage remains billable later.

Gateway policies must use deterministic ARNs for future resources, not `Ref`s to
resources in other stages. Preserve the current allowed actions/account condition:
S3 GetObject/GetObjectVersion/PutObject on the three bucket object ARNs, DynamoDB
GetItem/PutItem/Query on `fintrust-risk-dev`. An ARN in a policy does not create its
target. Do not temporarily use a full-access endpoint policy to break the dependency.

## E. Infrastructure code review and required changes

The Stage 1-only renderer and focused boundary tests are now prepared locally.
The combined foundation, runtime, schema and CI are unchanged.

| Existing code | Finding | Smallest required change before that stage |
|---|---|---|
| `network.py` | New isolated Stage 1 renderer with four subnets, separate route tables, tags, named DB subnet group, Gateway-only endpoints and stable outputs | 19 focused tests and CloudFormation template validation passed; review account/AZ/prefix-list inputs and change set before execution |
| `foundation.py` | Also creates rotating retained CMK, three versioned retained buckets and on-demand DynamoDB; endpoint policies reference those resources directly | Do not deploy the current combined template as Stage 1. Split storage/key into Stage 2, table into Stage 4, DB TLS group into Stage 3. Replace endpoint target Refs with exact deterministic ARNs |
| `foundation.py` | No hardcoded physical VPC/subnet/SG IDs; pseudo-parameters used for account/region; fixed proposed CIDRs; stage supports dev/staging/prod | Deploy dev only. Keep portable references and supply Cape Town/account guards at execution. Confirm CIDRs against any future connected network |
| RDS | Instance definition absent; earlier documents assumed an existing instance | Add private encrypted Single-AZ definition with the settings above, managed master secret, protection/snapshot policies and no paid extras. Review minor version, orderability, cost and bootstrap first |
| `rds/permissions.sql` | Scoped SQL groups exist; cloud LOGIN/rds_iam creation is described in comments | Implement reviewed repeatable setup for the three cloud logins; inspect schema source independently and verify grants before consumers |
| `iam/create_roles.py` | Offline least-privilege application policy renderer, not a deployment identity creator; some bucket defaults use older names without region | Pass exact stage outputs, never rely on old defaults. Bootstrap deployment IAM separately; application roles must not gain deployment rights |
| `processing.py` | One template couples all five functions, five SQS queues, mappings, logs and report schedule; consumer/schedule flag shared | Split or parameterize without changing handler behavior so stages can deploy separately. Keep mappings and schedule independently disabled. Add reviewed concurrency limits before invocation |
| `processing.py` | Requires code bucket/key/hash, existing roles/resources, SES addresses and SSM paths | Define approved artifact storage: use a restricted `deployment/` prefix in the private reports bucket, avoiding a fourth bucket; retain verified artifact/hash pairing and give upload rights only later |
| `ssm/put_parameters.py` | Writes nonsecret DB settings; private runtime uses deployment-resolved environment | Supply exact endpoint/database/service users only after RDS setup. Do not execute this mutating helper now |
| `api/gateway.json` | Regional REST API with AWS_IAM data methods | Approve a separate signed demo caller; current browser UI does not sign requests. Do not expose static AWS credentials or disable IAM to make the demo work |
| Monitoring helper | Mutates resources; default names differ from staged names; alarm recipients absent | Replace with reviewed stage-specific definitions/parameters and confirmed SNS actions. Essential operational alarms accompany workload enablement, not only the final stage |
| Tracing | Active X-Ray is not wired into processing definitions | Review trace configuration/permissions and bounded sampling at Stage 10 if required; no runtime instrumentation changes in this gate |
| Legacy helper scripts | Some create resources directly and use environment/SDK defaults | Use reviewed staged templates with explicit region/profile; do not run teaching helpers during deployment |

The processing queue count is **five**: transaction FIFO, its FIFO DLQ, plus ingest,
alert and report failure queues. Do not omit asynchronous failure destinations
when splitting stages. S3 notification metadata is not applied automatically;
wire only after permissions, monitoring and the consumer enablement review.

No hardcoded live physical IDs were found in the core foundation/processing/API
definitions reviewed. This is a targeted comparison, not a repeated repository
audit. Historical documentation has older status/count assumptions; the checkpoint
above is used for this phase without restarting documentation consolidation.

## F. Deployment sequence and learning evidence

Each row is a separate future review/approval checkpoint. Capture screenshots
without passwords, tokens, authentication URLs or private data.

| Stage | Create / connect / purpose | Console check and evidence | Cost and stop/cleanup |
|---|---|---|---|
| 0: identity + budget | MFA user and temporary deployment role; owner billing budget, email notifications and billing alarm | IAM trust/scoped permissions, MFA status and zero access keys; budget amount/thresholds and confirmed alarm recipient | IAM has no resource-hour fee; allow for alarm/SNS usage. Revoke role access when finished; retain billing alerts until all retained costs are reviewed |
| 1: private foundation | VPC, four private subnets, routes, two SGs, DB subnet group, S3/DynamoDB gateway endpoints | VPC resource map, subnet public-IP false, routes without internet default, DB SG source, endpoint policies/associations | No selected network hourly charge. After dependent resources/ENIs are removed, remove only this stack |
| 2: KMS + S3 | One CMK and raw/quarantine/reports buckets; restrictive TLS/encryption policies and artifact prefix | Encryption/key alias, public-access blocks, versioning and lifecycle | Key base/rotation/requests plus object storage. Retained versions persist; approve export/retention before bucket/key deletion |
| 3: RDS + grants | Private PostgreSQL, TLS group, managed master secret and temporary migration runner; three service logins | Public access false, Single-AZ/class/storage/encryption, IAM auth, SG/subnets; sanitized SQL grant and TLS evidence | Main standing cost. Bootstrap runner removed after use; stop DB between short sessions but schedule final approved teardown and snapshot review |
| 4: DynamoDB + queues | Risk table/stream and all five queues; replay/delivery-state infrastructure | Table keys/NEW_IMAGE, FIFO names, encryption, visibility/redrive/retention, failure destinations | Requests/storage; DLQ messages retained. Preserve uncertain deliveries and evidence before cleanup; no replay yet |
| 5: ingest | Role, log group, verified code and outside-VPC ingest Lambda, S3 read/quarantine/SQS grants | Handler/runtime/hash, IAM scope, log retention and failure destination; notification remains unwired initially | Lambda/log/API usage. No uploads/event wiring until downstream ready; remove trigger before teardown |
| 6: scoring | Private scoring Lambda with IAM DB login, SQS mapping initially disabled, DynamoDB/S3 access | VPC attachment, service DB username (no secrets), mapping disabled, batch failure support/concurrency | RDS already costs while running; bound consumers before enabling. Disable mapping and preserve queue before stop |
| 7: alert + SES | Outside-VPC alert Lambda, scoped sender/recipient, stream mapping initially disabled | Verified SES identities/sandbox, INSERT/high-risk filter, conditional delivery tests, held-send recovery and alarms | SES/Lambda/log usage. Approve any real test email; disable mapping, reconcile SENDING/UNKNOWN before teardown |
| 8: query + API | Private API Lambda and Regional REST endpoint, separate signed demo identity | AWS_IAM data routes, signed request success and unauthorized failure; private DB connectivity | Request/Lambda/log charges. Disable demo access and remove API during approved teardown |
| 9: reporting | Private report Lambda, report queue policy and disabled monthly rule | SQL report in S3, rule DISABLED, limited retries/failure destination; manual synthetic run only when approved | RDS/query/Lambda/S3 charges. Keep schedule disabled outside approved tests; preserve required exports |
| 10: observability + E2E | Complete scoped alarms/log queries/tracing and controlled synthetic flow | Error/DLQ/DB alarms, trace if required, S3-to-report/alert correlation, duplicate/retry evidence and cost view | Logs/metrics/alarms/traces bill by use/retention. Bound volume, stop triggers/schedule, reconcile, export and execute separately approved cleanup |

Stage numbers describe construction order, not permission to enable traffic.
Create basic logs, failure destinations, notifications and essential alarms with
their associated stages. Only after Stages 5–8 are ready and monitoring/recovery
is checked should the owner approve a small end-to-end upload and email. Do not
wait until Stage 10 to discover there was no failure alert during earlier tests.

## G. Standing costs and teardown

| Category | Exposure |
|---|---|
| RDS | Compute while running, provisioned storage even when stopped, surplus CPU credits, excess/retained backup storage |
| Encryption / secret | One CMK base charge (published USD 1/month before requests/eligible rotations); managed master secret storage/API charges |
| Retained data | S3 current/noncurrent versions, DynamoDB data, snapshots and logs can cost money while no demo runs |
| Monitoring | Alarms/custom metrics, log ingestion/retention, SNS and tracing as configured |
| Usage | Lambda, API Gateway, SQS, DynamoDB requests, SES, S3/KMS requests, transfer including possible cross-AZ DB traffic |
| Excluded | NAT, IGW/public IPs, interface endpoints, proxy, replicas/Multi-AZ, extra environments |

See [KMS pricing](https://aws.amazon.com/kms/pricing/),
[RDS pricing](https://aws.amazon.com/rds/postgresql/pricing/) and
[Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/).
Do not describe retained resources as free because the functions are idle.

Stopping RDS is temporary: AWS can [restart it after seven days](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html),
and storage remains billable. Agree a short demo window and reminder; do not build
an automatic stop/start scheduler in this phase. Final cleanup is separately
approved: disable event sources, reconcile queue/delivery state, export and verify
data, take/restore-check the agreed snapshot, remove applications, database and
secret as approved, then networking after Lambda ENIs clear. Review retained
objects/snapshots and CMK decrypt dependencies before any key deletion. Retain
billing safeguards until residual charges are understood.

## H. Next approval and unresolved inputs

**Stage 1 is prepared for review, not attachment or execution approval.**
Finish the final network-policy validation after login renewal; the prior clean
validation predates its last scoping improvement. Review the exact three inline-policy
JSON files linked from [DEPLOYER_DESIGN.md](iam/DEPLOYER_DESIGN.md), their combined
10,233-character quota use, the network template and its limitations. No policy
attachment, change set or infrastructure creation is authorized by this report.

After separate approval, an administrator can install only that reviewed bundle
on the existing role. A subsequent authorized MFA role session must verify account
and ARN before preparing a `fintrust-network-*` CREATE change set for the named
stack, supplying the template's eight resource types, two distinct Cape Town AZs,
regional prefix lists and ownership tags. Do not specify a service role, imports,
CAPABILITY_IAM or auto-execution. Review resource additions/replacements and stop
for execution approval; never use the combined foundation for this stage.

Before paid stages: reconfirm credit/plan headroom, gross-usage budget visibility,
tax/FX, maximum RDS hours, exact supported minor, secret/bootstrap costs and handling,
retention owner, artifact storage, SES identities and authenticated demo access.
Stage 2 CMK use still needs a Free Tier-first justification; this review does not
silently remove encryption requirements from existing bucket policies.

## I. Stop

Only read-only AWS metadata and validation APIs were used. No IAM/budget changes,
policy attachment, infrastructure creation, RDS creation, invocation, email or
Git push occurred. The seven pre-existing untracked files remain untouched.
Linux CI was not repeated; its verified 178-pass result is historical evidence,
not a claim that these new local changes have run in CI.

## Change-set inspection checkpoint

The operator reports that the first change-set ARN correction was installed but
DescribeChangeSet remained denied against `fintrust-network-dev`. Inspection now
has its own named-stack, region-only statement; execute/delete keep their required
`fintrust-network-*` naming guard and documented stack scope. All other conditions
are unchanged. The second correction passed **21 focused tests** and read-only
Access Analyzer validation with **zero findings**. Combined inline policy size is
**10,233 / 10,240 characters**. Live inspection access remains unverified pending
manual replacement of only FinTrustStage1CloudFormation and role re-assumption.
See [the identity design](iam/DEPLOYER_DESIGN.md#change-set-inspection-permission-correction)
for both findings and the manual retry. Reuse the existing change set if its status
and reviewed proposal remain valid. Do not execute it during this check. No AWS
policy update, infrastructure execution or push was performed by this correction.


## Live VPC rollback checkpoint

Read-only AWS events confirm fintrust-network-dev is ROLLBACK_COMPLETE after the
Vpc resource was denied ec2:ModifyVpcAttribute. The action was already present in
the attached and local network policy. Corrected only its case-sensitive
`ec2:Attribute` values to `EnableDnsSupport` and `EnableDnsHostnames`, as shown in
AWS's IAM example. Both DNS properties are enabled in the source and built
Stage 1 template. Region, ownership tags, CalledVia and action/resource scope are
unchanged. Focused tests: **22 passed**; corrected network Access Analyzer result:
**zero findings**. The policy has not been updated in AWS by this correction and
no live retry has been performed.

The initial CREATE was executed by the operator and failed; earlier preparation
checkpoints are historical. Stage 1 is not deployed successfully. Preserve evidence
and inspect cleanup, then seek approval to replace only FinTrustStage1Network and
delete the rolled-back named stack. A fresh CREATE change set needs a deleted
stack name and new review; do not reuse the executed proposal or retry execution
without approval. See [the identity design](iam/DEPLOYER_DESIGN.md#live-stage-1-vpc-rollback-finding)
for the finding, sources and manual recovery sequence. No AWS mutation or push
was performed in this correction.

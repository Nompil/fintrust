# Deployment bootstrap and cost gate

Status: **STAGES 1 AND 2 DEPLOYED AND VERIFIED; STAGE 3 PREPARED FOR REVIEW.**

The current Stage 1 and Stage 2 checkpoints below supersede historical preparation
and rollback statements in this record.

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
| Storage | **20 GiB gp3**, documented PostgreSQL SSD minimum; no storage autoscaling or provisioned IOPS. Small synthetic data only; stop loading below 2 GiB free space. Review growth before increasing capacity. gp2 and gp3 have the same regional storage price; gp3 provides a stronger baseline |
| Encryption | `StorageEncrypted=true`, prefer the regional AWS-managed `aws/rds` key. No separate customer-managed key is required for this single-account demo. This changes the RDS proposal only; existing S3 CMK policies must be reviewed separately before Stage 2 |
| Network | `PubliclyAccessible=false`, IPv4 private endpoint, `fintrust-db-dev` subnet group across `af-south-1a` and `af-south-1b`; DB security group accepts TCP 5432 only from the application SG and a separately reviewed temporary bootstrap SG |
| Authentication / TLS | IAM DB authentication enabled, `rds.force_ssl=1`, clients use `verify-full` and the bundled RDS CA. Distinct `fintrust_scoring_dev`, `fintrust_api_dev`, `fintrust_report_dev` logins get `rds_iam` plus their corresponding least-privilege SQL group |
| Administrator secret | Recommend RDS-managed master secret in Secrets Manager, with its separate storage/API cost disclosed. No master password in Git, parameters, outputs, shell history or application environment. Retrieval only by the later bootstrap process |
| Backups | One-day automated retention for synthetic assessment data, copy tags to snapshots. Final snapshot on approved teardown; retain it only for the explicitly agreed evidence/restore period |
| Protection | Deletion protection on; CloudFormation deletion/replacement snapshot policies. Teardown requires separate approval to disable protection, export/reconcile and verify restore evidence |
| Maintenance | Automatic minor upgrades on within PostgreSQL 16; major upgrades off. Standard support only; no automatic paid Extended Support enrollment |
| Monitoring | Standard metrics plus 14-day application logs initially; no paid enhanced monitoring/advanced database insights selected. Essential DB/memory/storage/connection alarms before workload |

AWS documents [instance memory sizes](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.Summary.html)
and [300â€“1000 MiB additional memory for IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html).
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

| Candidate | Compute/hour | 730 hours + 20 GiB gp3 | Free Plan-listed class |
|---|---:|---:|---|
| **db.t4g.micro** | USD 0.021 | **USD 18.350** | Yes; uses credits |
| db.t3.micro | USD 0.024 | USD 20.540 | Yes; uses credits |
| db.t4g.small | USD 0.041 | USD 32.950 | Not listed for the Free Plan; no automatic upgrade |

Both gp2 and gp3 are USD 0.151/GiB-month here. The
[CreateDBInstance API contract](https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_CreateDBInstance.html)
requires **20 GiB minimum for PostgreSQL gp2 and gp3**. Earlier orderability
metadata reported five GiB for gp2; that response does not override the engine's
creation constraints. Select **20 GiB gp3**: equal storage cost and 3,000 baseline
IOPS rather than gp2's burst-dependent small-volume baseline. No extra IOPS or
throughput is provisioned. The seed is small; cap further loading and measure
actual database/WAL usage rather than treating all capacity as application space.

Recommended compute + storage: **USD 18.35/month** at 730 running hours. The
previous five-GiB estimate is superseded. A conservative short-demo estimate is
`24 * 0.021 + 20 * 0.151 = USD 3.524`: 24 running hours plus a full month of storage.
The Stage 3 table below instead prorates storage/secret for a 24-hour lifespan.
Stopped 20 GiB storage alone is USD 3.02/month while retained. Storage is billed
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
their associated stages. Only after Stages 5â€“8 are ready and monitoring/recovery
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


## Current Stage 1 status

**Stage 1: deployed and verified. AWS Integration: In Progress.**
The operator completed the corrected reviewed retry. The saved
[stack screenshot](../docs/EVIDENCE/04-network/06-stage1-stack-create-complete.png)
shows fintrust-network-dev CREATE_COMPLETE in af-south-1. The
[resource screenshot](../docs/EVIDENCE/04-network/07-stage1-resources-create-complete.png)
records successful resource creation; the operator confirms all resources completed.
Earlier rollback/recovery instructions above are historical and no longer apply
to this successful stack. Preserve it for subsequent stages. This evidence verifies
creation, not application connectivity or end-to-end integration. Stage 2 remains
local preparation only and requires its own IAM/cost/change-set approval.


## Stage 2 storage approval checkpoint

The existing stage plan separates storage from networking and the later database,
processing and API stages. [storage.py](storage.py) extracts only the existing
foundation storage resources, adds FinTrust/dev ownership tags, restricts Stage
to dev, and retains the key, alias, buckets and bucket policies on deletion or
replacement. No runtime code or Stage 1 template changes were made.

| Logical resource | Proposed physical resource / purpose |
|---|---|
| DataKey | One regional symmetric customer-managed KMS key; annual rotation, 30-day deletion window |
| DataKeyAlias | alias/fintrust-dev |
| RawBucket / RawBucketPolicy | fintrust-raw-966467878406-af-south-1-dev; source CSV storage and encryption/TLS controls |
| QuarantineBucket / QuarantineBucketPolicy | fintrust-quarantine-966467878406-af-south-1-dev; rejected-record storage and controls |
| ReportsBucket / ReportsBucketPolicy | fintrust-reports-966467878406-af-south-1-dev; reports and later deployment/ artifacts |

There are exactly eight resources: AWS::KMS::Key, AWS::KMS::Alias,
AWS::S3::Bucket and AWS::S3::BucketPolicy. There are no SSM parameters, IAM roles,
RDS, Lambda, triggers, object uploads, network changes or new endpoints in this
stage. SSM/database configuration and runtime roles remain later-stage work.
All buckets retain Block Public Access, BucketOwnerEnforced, versioning, SSE-KMS
with the exact key and S3 Bucket Keys. Five policy denies enforce TLS and reject
conflicting encryption headers. Default encryption applies when headers are absent.
Incomplete multipart uploads expire after seven days; the existing report archive
transition remains. No automatic object/version deletion is introduced.

### Cost decision before IAM attachment

Expected standing charge for an empty deployment is **USD 1/month for the new
unrotated key**, prorated hourly, plus usage-dependent S3/KMS charges and tax.
[AWS KMS pricing](https://aws.amazon.com/kms/pricing/) charges another USD 1/month
for each of the first two rotations. Its 20,000 monthly eligible request allowance
is shared across regions and does not cover customer-managed key storage.
[S3 pricing](https://aws.amazon.com/s3/pricing/) depends on regional stored bytes,
versions, requests, transfers and archive operations; no object volume has been
approved here. Empty buckets add no fixed bucket rental charge. Credits are not
a zero-cost guarantee or a substitute for the monthly USD 10 budget.

A CMK is retained because the existing design and execution-role renderer scope
S3 permissions to a customer-controlled key and its encryption context. It is
not required merely to encrypt S3 data: AWS-managed aws/s3 or SSE-S3 could remove
the key-storage charge, but would require a separate reviewed change to those
controls. **Choose/approve the CMK charge or request that alternative before any
Stage 2 IAM attachment or resource creation.** No paid-resource approval is inferred.

Retain prevents accidental disposal but also leaves billable storage and the key
after stack deletion. Teardown needs separate export/restore/retention approval,
all object versions handled deliberately, and explicit key lifecycle approval.
Do not delete Stage 1 or schedule key deletion as a routine cleanup step.

### Exact deployment permission requirements for review

The current Stage 1 inline bundle uses 10,233 of the role's 10,240 characters;
**do not append Stage 2 permissions to that bundle**. Prepare a separately reviewed
managed policy, or review a stage-specific replacement that preserves necessary
network reads. Neither attachment nor removal is authorized here. The following
is the required permission scope, not an installed policy or successful live
provider-permission test. The final policy JSON must pass Access Analyzer and
policy-size/scoping tests before the first security mutation.

| Permission area | Required action scope and boundary |
|---|---|
| CloudFormation preparation | ValidateTemplate/GetTemplateSummary with regional wildcard where required; CreateChangeSet only on arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-storage-dev/*, fintrust-storage-* names, both ownership request tags, nonempty exact four resource types above, no RoleArn or imports |
| CloudFormation inspection | DescribeChangeSet in its own named-stack, region-only statement; DescribeStacks/DescribeStackEvents/DescribeStackResources/ListStackResources/GetTemplate on the same named stack |
| CloudFormation writes | ExecuteChangeSet/DeleteChangeSet on the documented supported named-stack resource scope with fintrust-storage-* naming and regional conditions; execution requires separate proposal approval |
| S3 creation/configuration | CreateBucket, PutBucketTagging, PutBucketPublicAccessBlock, PutBucketOwnershipControls, PutBucketVersioning, PutEncryptionConfiguration, PutLifecycleConfiguration, PutBucketPolicy on only the three bucket ARNs above; region/account and CloudFormation-mediated writes. CreateBucket LocationConstraint must be af-south-1. Tags are configured after creation, so existing-resource tag conditions cannot gate initial creation/tagging |
| S3 provider inspection | GetBucketLocation, GetBucketTagging, GetBucketPublicAccessBlock, GetBucketOwnershipControls, GetBucketVersioning, GetEncryptionConfiguration, GetLifecycleConfiguration, GetBucketPolicy, GetBucketPolicyStatus, GetBucketAcl and ListBucket only on those exact bucket ARNs; no object contents access |
| KMS creation | CreateKey necessarily uses Resource * before the key ID exists; constrain region, FinTrust/dev request tags, symmetric encryption use and CloudFormation mediation; TagResource for creation tags. Do not give broad KMS administration |
| KMS configuration/inspection | DescribeKey, GetKeyPolicy, GetKeyRotationStatus, ListResourceTags and EnableKeyRotation on regional account keys with FinTrust/dev ownership; PutKeyPolicy only if required for later template maintenance and explicitly reviewed as a security boundary |
| Alias | CreateAlias on only arn:aws:kms:af-south-1:966467878406:alias/fintrust-dev and its owned target key; alias resources do not carry key ownership tags. Scope read/list permissions to what the provider requires |

No IAM write/PassRole, S3 object write/read/delete, KMS decrypt/data-key use,
key deletion/disable, bucket deletion, RDS, EC2 mutations or Lambda permissions
are part of this proposed creation grant. Runtime data access and artifact upload
will be separately scoped later. Rollback permissions must be reviewed against
Retain before attachment; do not add destructive permissions speculatively.

### Prepared command and change-set sequence

Local renderer:

```powershell
python -m infrastructure.storage --output build/stage2-storage.json
```

The generated template is ignored by Git. Focused local validation: **25 passed**
across Stage 2 storage, Stage 1 network and budget-first tests. Read-only AWS
CloudFormation ValidateTemplate through fintrust-inventory succeeded, with no IAM
Capabilities returned. This confirms template acceptance, not deployment rights,
key-policy safety under every caller, live bucket controls or application access.
Linux CI and the full application suite were not repeated for this isolated renderer.

After cost and final permission approval, verify the MFA-assumed caller account/
role and the af-south-1 target, check exact bucket names/alias and existing stack
ownership read-only, then prepare the following proposal. Replace the profile
placeholder only with the verified assumed-role profile. **Not executed:**

```powershell
& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' cloudformation create-change-set `
  --profile <verified-assumed-role-profile> --region af-south-1 `
  --stack-name fintrust-storage-dev --change-set-name fintrust-storage-stage2-review `
  --change-set-type CREATE --template-body file://build/stage2-storage.json `
  --parameters ParameterKey=Stage,ParameterValue=dev `
  --resource-types AWS::KMS::Key AWS::KMS::Alias AWS::S3::Bucket AWS::S3::BucketPolicy `
  --tags Key=Project,Value=FinTrust Key=Environment,Value=dev --no-cli-pager
```

Do not supply capabilities, a service role or imports. Stop if a named resource
already exists: no automatic adoption, deletion or replacement. Inspect the change
set and require exactly eight Add actions with no unrelated resources before a
separate execution approval. After approved execution, verify stack/resource
status, bucket controls and key/alias metadata read-only before later-stage work.

**Stop boundary:** Stage 2 template preparation is complete; deployment is not
approved. The first next AWS mutation would be the separately reviewed permission
attachment, followed by change-set preparation only after cost approval. No IAM
attachment, change-set creation/execution, resource mutation, upload or push occurred.


### Final Stage 2 permission proposal

The [three Stage 2 managed-policy JSON documents](iam/DEPLOYER_DESIGN.md#stage-2-proposed-managed-policy-bundle)
are now prepared. Their scope, intended attachment principal, wildcard rationale,
policy-content administration powers and retained-resource recovery limits are
explicitly recorded. Each passed read-only Access Analyzer with zero findings.
The role's nearly-full inline quota requires the managed-policy route; no inline
bundle changes were made.

FinTrust retains one customer-managed KMS key for explicit encryption governance,
key policy and lifecycle control. Its base cost is approximately USD 1/month,
prorated hourly, plus usage. This is an intentional project tradeoff, not a claim
that AWS-managed encryption is insufficient. The user requested this final
security review before attachment; no deployment or IAM mutation approval is
inferred from the cost recommendation. The previous permission table is design
rationale; the linked JSON is the concrete proposal for approval.


## Stage 3 private database approval checkpoint

Read-only inventory confirms both fintrust-network-dev and fintrust-storage-dev
are CREATE_COMPLETE. AWS Integration remains In Progress. Earlier Stage 2
preparation statements above are historical; no Stage 1/2 changes are proposed.

[database.py](database.py) renders exactly two CloudFormation resources for
`fintrust-database-dev`: `LedgerDatabase` (AWS::RDS::DBInstance) and `DatabaseTls`
(AWS::RDS::DBParameterGroup). RDS also creates/manages a master-password secret
in Secrets Manager; this is a dependent billable resource, not a third explicitly
managed CloudFormation resource. The missing AWSServiceRoleForRDS must be created
by an authorized administrator as a separately approved prerequisite.

| Setting | Exact Stage 3 proposal |
|---|---|
| Database | fintrust-ledger-dev / fintrust; PostgreSQL **16.15**, parameter family postgres16 |
| Compute/storage | db.t4g.micro; Single-AZ; **20 GiB gp3**; no autoscaling, IOPS, replica or proxy |
| Network | IPv4, PubliclyAccessible=false; reuse fintrust-db-dev and sg-01644a4c9f2c44162; no network mutations |
| Database subnets | subnet-04dc0f576867d7a6c and subnet-084deb13f49a36064 in vpc-0aba008bb360f5147 |
| Ingress | Existing database SG has only TCP 5432 from sg-0850bd798bb9505e2 (application/Lambda SG); no IP-range ingress |
| TLS/IAM | rds.force_ssl=1 in fintrust-postgres16-dev; EnableIAMDatabaseAuthentication=true; application IAM path already uses verify-full and the bundled RDS CA |
| Encryption | StorageEncrypted=true; omit KmsKeyId to select the regional AWS-managed aws/rds key. Do not reuse the Stage 2 S3 CMK; this follows the existing Free Tier-first RDS plan |
| Master credentials | fintrust_admin; ManageMasterUserPassword=true, no password parameter/output; default AWS-managed aws/secretsmanager encryption, no customer key or secret-value read grant |
| Support/monitoring | Standard support only; Extended Support disabled; minor upgrades on, major upgrades off; no enhanced monitoring or Performance Insights |
| Backup/deletion | One-day automated backups, CopyTagsToSnapshot=true; deletion protection on; deletion/replacement Snapshot; parameter group Retain |

The template pins the existing database group as its only accepted SG input and
the existing named subnet group; it does not create an ingress exception. Live
orderability confirms 16.15/gp3/micro, twenty-GiB minimum, encryption and IAM support
in af-south-1. This replaces the older 16.14 candidate without changing major
version. Micro capacity, IAM memory headroom and actual TLS connections remain
unmeasured. Begin with a small sequential synthetic workload, then check free
memory/connections/storage; never silently resize or turn off IAM authentication.

### Proposed permission bundle

All documents are local proposals, not attached policies:

- [FinTrustStage3CloudFormation](iam/stage3-cloudformation-policy.json): only
  fintrust-database-dev and fintrust-database-* proposals; exact DBInstance and
  DBParameterGroup resource types, FinTrust/dev request tags, no service role,
  imports, IAM capabilities or PassRole. Named-stack reads/recovery only.
- [FinTrustStage3Rds](iam/stage3-rds-policy.json): exact new DB/parameter-group
  ARNs and existing subnet-group/default PostgreSQL option-group references;
  CloudFormation-mediated creation with PostgreSQL/micro/twenty-GiB, encrypted,
  private VPC, Single-AZ and managed-password conditions. TLS-group configuration
  and ownership tagging are scoped; no database deletion, resizing, stop/start,
  network mutation or SQL login permissions are granted.
- [FinTrustStage3Secret](iam/stage3-secret-policy.json): CreateSecret/TagResource
  only for account/regional rds!db-* secret names plus DescribeKey for keys with
  aws/rds or aws/secretsmanager aliases. There is no GetSecretValue, crypto-use,
  grant or secret-delete permission. RDS generates the unknown secret identifier;
  the prefix cannot identify only this DB before creation. This grant can create
  other matching RDS-prefix secrets; narrow it after resolving the actual ARN.
  No unverified CalledVia condition is imposed on the RDS/Secrets Manager
  dependency. Confirm the provider path during the later authorized deployment.
- [RDS service-role bootstrap](iam/stage3-service-linked-role-policy.json): a
  **separate administrator prerequisite**, only CreateServiceLinkedRole for
  rds.amazonaws.com and its exact account role ARN. Do not attach this document
  to the deployer by default. It has no general role creation or PassRole.

IAM rds:Vpc is Boolean true (VPC placement), not a VPC ID condition. The named
subnet group, template SG restriction and pre-execution inspection establish the
actual VPC/SG boundary. Class, size and IAM/password settings not supported as
IAM condition keys are also asserted by the template tests and change-set review.
The template's IAM-auth flag is not a substitute for SQL rds_iam grants.
Each JSON fits the managed-policy size limit; check attachment quota before
approval rather than appending to the nearly-full Stage 1 inline bundle.

[Secrets integration permissions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html)
require CreateSecret, TagResource and DescribeKey. No new customer-key grant is
needed for this managed-key proposal. [RDS service-linked roles](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAM.ServiceLinkedRoles.html)
are service-managed prerequisites, not a CloudFormation execution role.

### Cost before credits

Refreshed [public Cape Town RDS catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/af-south-1/index.json):
compute USD **0.021/hour**, gp2/gp3 USD **0.151/GiB-month**. One 20 GiB volume is USD
3.02/month. [Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/)
adds approximately USD **0.40/secret-month**, plus API calls. Using 730 hours for
monthly proration, the database/storage/secret subtotal is:

| Running period | Compute | Prorated storage + secret | Total |
|---|---:|---:|---:|
| One hour | USD 0.021 | USD 0.004685 | **USD 0.025685** |
| 24 hours | USD 0.504 | USD 0.112438 | **USD 0.616438** |
| 730 hours | USD 15.330 | USD 3.420 | **USD 18.750** |

These are estimates, not caps or a Free Tier promise. Excluded: API calls, burst
CPU surplus credits, excess backup/manual/final snapshots, transfer, taxes and
other stages (including the existing S3 key). Credit eligibility/balance must be
reconfirmed before approval. Full-month operation exceeds the USD 10 budget;
prefer an explicitly approved 24-hour test window and a cleanup owner. The older
24-hour estimate included a full month of storage; this table instead prorates
storage and secret for the stated running interval. Retaining them longer adds cost.

### SQL initialization and acceptance dependency

Reviewed canonical sql/schema.sql and infrastructure/rds/permissions.sql, with
sql/views.sql, sql/procedure.sql and reporting SQL. No SQL was executed or modified.
The seven pre-existing untracked files, including infrastructure/rds/schema.sql,
remain untouched. The canonical schema uses pgcrypto and restricted foreign keys.
permissions.sql defines service groups and documents the three required staged
IAM logins; it does not automatically create/grant those cloud logins.

Database creation alone does not initialize tables, service users or seed data.
A later separately reviewed migration runner must execute the canonical SQL,
provision fintrust_scoring_dev / fintrust_api_dev / fintrust_report_dev with rds_iam
and matching service grants, and verify connections using verify-full. The prior
private migration-Lambda proposal remains a dependency; it is not created by this
stage and has not been implemented or invoked. Use the existing application SG
for a reviewed runner without adding public access/NAT/ingress. Credential handling,
secret-value access, runner permissions/artifact and removal need their own review.
Do not claim Stage 3/application readiness until this bootstrap and capacity tests pass.

### Validation, recovery and next boundary

**36 focused tests passed**, including six new Stage 3 boundary tests. All four
proposed policy documents passed Access Analyzer with **zero final findings**.
Its initial rds:Vpc type warning was corrected and revalidated. CloudFormation
ValidateTemplate through fintrust-inventory passed with no IAM capabilities.
These are read-only/static validation results, not live provider permission or
RDS/TLS/SQL execution evidence. No Linux CI/full-suite rerun was needed for the
isolated infrastructure addition.

Deletion protection deliberately blocks normal teardown. The creation bundle
also lacks ModifyDBInstance/DeleteDBInstance and physical cleanup permissions.
Before execution, agree how an authorized administrator will recover a failed
create or disable protection for approved teardown; automatic rollback can be
blocked by protection or missing disposal grants. Preserve events and inspect
actual retained resources; do not force-delete, skip resources or grant broad
RDS access. A ROLLBACK_COMPLETE stack requires approved deletion before a new
CREATE; inspect retained names/snapshots and secret state first.

For approved final teardown: reconcile/export synthetic records, test restore,
choose retained snapshot period, then separately review scoped protection-disable,
DB deletion/final snapshot and stack cleanup permissions. Snapshot policies do
not waive deletion protection. RDS deletes its managed secret when the instance
is deleted; restoring a snapshot requires a fresh credential/bootstrap plan.
The retained parameter group and snapshots can outlive the stack; storage costs
continue. Stopping is not deletion: storage/backup/secret costs remain and RDS
normally restarts after seven days; no stop command is authorized here.

**Exact next manual AWS step after approval:** an authorized administrator creates
only AWSServiceRoleForRDS (if still absent) with `iam create-service-linked-role
--aws-service-name rds.amazonaws.com`, then installs only the three reviewed Stage 3
managed policies on fintrust-deployer-role after checking attachment quota. This
requires explicit identity/cost/recovery approval and is not authorized by this
record. Do not attach the separate bootstrap policy to the role automatically.

After separate preparation approval, render build/stage3-database.json, verify
MFA-assumed identity/account/region, reconfirm named resource absence/orderability
and the live network outputs, then prepare (not execute) the named CREATE proposal:

```powershell
& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' cloudformation create-change-set `
  --profile fintrust-deployer-role --region af-south-1 `
  --stack-name fintrust-database-dev --change-set-name fintrust-database-stage3-review `
  --change-set-type CREATE --template-body file://build/stage3-database.json `
  --parameters ParameterKey=DatabaseSubnetGroup,ParameterValue=fintrust-db-dev `
    ParameterKey=DatabaseSecurityGroup,ParameterValue=sg-01644a4c9f2c44162 `
  --resource-types AWS::RDS::DBInstance AWS::RDS::DBParameterGroup `
  --tags Key=Project,Value=FinTrust Key=Environment,Value=dev --no-cli-pager
```

Require exactly two Add actions and review the dependent managed secret/service
role, settings and recovery plan before separate execution approval. No AWS
mutation, attachment, change set, SQL execution or push occurred in preparation.


### Stage 3 PostgreSQL minimum-storage correction

The initial five-GiB gp2 proposal was invalid under the engine-specific
CreateDBInstance contract, despite the orderability API returning that minimum.
Corrected the template to **20 GiB gp3** and the Stage 3 RDS IAM NumericEquals
constraint to **20**. Public Cape Town prices are equal for gp2/gp3; gp3 therefore
provides the stronger baseline without a storage-price increase. Regression checks
require the documented PostgreSQL SSD minimum and the exact selected size/type.
This supersedes the five-GiB cost/setting claims in earlier preparation summaries.
No live database, policy, service role or change set was changed.

### Stage 3 administrator recovery runbook

The operator reports fintrust-database-stage3-review is CREATE_COMPLETE / AVAILABLE
with exactly two Add actions. This report is not a new account inspection. Save
its screenshot as docs/EVIDENCE/05-rds/01-stage3-change-set-reviewed.png; no image
was supplied with the recovery request, so that evidence has not been saved here.
No execution is authorized by this runbook.

**Execution checkpoint:** NOT READY TO EXECUTE until the operator confirms a
working administrator recovery identity in account 966467878406, accepts the
ongoing cost and test window, and gives separate execution approval. The reviewed
proposal is technically prepared. Its deployer permissions intentionally exclude
physical database cleanup; an administrator must remain available if rollback
cannot dispose of the database. This is not a request to broaden the deployer.

#### Inspect before choosing recovery

In the Console select Cape Town, CloudFormation > fintrust-database-dev > Events
and Resources. Capture the first CREATE_FAILED reason and subsequent rollback
failures; record the stack ID and actual physical IDs. In RDS > Databases inspect
fintrust-ledger-dev, status, deletion protection, pending changes, encryption,
subnet group, security groups and managed-secret ARN. Never capture secret values.
Wait for active create/modify/rollback operations to settle before intervening.
DBInstanceNotFound means there is no instance to disable/delete; AccessDenied
means UNKNOWN. Do not infer absence from an authorization error.

Default execution attempts rollback on provisioning failure. A protected DB
cannot be deleted, and the restricted deployer may also lack deletion/snapshot
permissions. The stack can enter ROLLBACK_FAILED; stack failure does not mean the
DB or secret disappeared. DatabaseTls has Retain and can outlive rollback. If
preserving successful resources is chosen separately at execution, a CREATE_FAILED
stack follows the preserve/retry path instead; do not silently change that option.
ContinueUpdateRollback applies to UPDATE_ROLLBACK_FAILED, not a failed initial
CREATE rollback.

For commands below replace APPROVED_ADMIN_PROFILE with an existing authenticated
administrator profile. Do not configure new credentials or use the inventory
profile for writes. Verify sts get-caller-identity first: account 966467878406,
expected administrator identity. The CLI path is C:\Program Files\Amazon\AWSCLIV2\aws.exe.
These commands are examples for a later approved recovery, not commands to run now.

```powershell
$recoveryAws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$recoveryProfile = 'APPROVED_ADMIN_PROFILE'
& $recoveryAws sts get-caller-identity --profile $recoveryProfile --no-cli-pager
& $recoveryAws cloudformation describe-stack-events --stack-name fintrust-database-dev --profile $recoveryProfile --region af-south-1 --output json --no-cli-pager
& $recoveryAws cloudformation list-stack-resources --stack-name fintrust-database-dev --profile $recoveryProfile --region af-south-1 --output json --no-cli-pager
& $recoveryAws rds describe-db-instances --db-instance-identifier fintrust-ledger-dev --profile $recoveryProfile --region af-south-1 --output json --no-cli-pager
```

#### Approved disposal through CloudFormation

Prefer stack-managed disposal once failure is terminal and removal is approved.
In RDS select the exact instance > Modify > clear Deletion protection. Review
pending modifications before selecting Apply immediately: unrelated pending
changes can also be applied. CLI equivalent:

```powershell
& $recoveryAws rds modify-db-instance --db-instance-identifier fintrust-ledger-dev --no-deletion-protection --apply-immediately --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds describe-db-instances --db-instance-identifier fintrust-ledger-dev --query 'DBInstances[0].{Status:DBInstanceStatus,Protection:DeletionProtection,Pending:PendingModifiedValues}' --profile $recoveryProfile --region af-south-1 --no-cli-pager
```

Proceed only after protection reads false and the instance is in a state allowing
deletion. For a terminal ROLLBACK_FAILED, ROLLBACK_COMPLETE or CREATE_FAILED stack,
use ordinary administrator stack deletion, not force deletion or resource skipping:

```powershell
& $recoveryAws cloudformation delete-stack --stack-name fintrust-database-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws cloudformation wait stack-delete-complete --stack-name fintrust-database-dev --profile $recoveryProfile --region af-south-1
```

The stack has no execution role, so the administrator caller must have all required
RDS/snapshot cleanup permissions. Snapshot deletion policy requests a final DB
snapshot; inspect its actual ARN/status rather than assume creation succeeded.
If deletion fails, capture DELETE_FAILED events and resolve that specific error.
A ROLLBACK_COMPLETE stack cannot be reused for a fresh CREATE until removed.

**Exceptional orphan cleanup:** use direct RDS deletion only after confirming
ownership, stack management state and separate disposal approval. For a DB that
supports snapshots, select Create final snapshot and a unique unused name in
RDS > Actions > Delete. CLI equivalent (replace the snapshot placeholder):

```powershell
& $recoveryAws rds delete-db-instance --db-instance-identifier fintrust-ledger-dev --no-skip-final-snapshot --final-db-snapshot-identifier APPROVED_UNIQUE_SNAPSHOT_NAME --delete-automated-backups --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds wait db-instance-deleted --db-instance-identifier fintrust-ledger-dev --profile $recoveryProfile --region af-south-1
```

The example explicitly deletes automated backups while keeping the final manual
snapshot; approve that retention choice before use. For failed, incompatible-restore
or incompatible-network DB status AWS requires skipping the final snapshot.
STOP in that case: do not silently waive the final-snapshot requirement. Record
whether any recoverable data/backup exists and obtain separate loss/cleanup
approval. Direct deletion of a still stack-managed DB creates drift and is not
the normal recovery path.

#### Retained resources, cost and evidence

Use RDS > Snapshots > Manual and filter by fintrust-ledger-dev. Record the actual
snapshot identifiers and status, including any partially completed snapshots.
Keep the approved final snapshot until export/reconciliation and restore testing
or a documented empty-database exception are accepted; agree an owner and retention
limit. Later snapshot deletion requires separate approval. Identify the retained
parameter group by its exact name and tags; confirm no DB instance references it
before deleting it. Read-only inventory commands:

```powershell
& $recoveryAws rds describe-db-snapshots --db-instance-identifier fintrust-ledger-dev --snapshot-type manual --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds describe-db-instance-automated-backups --db-instance-identifier fintrust-ledger-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds describe-db-parameter-groups --db-parameter-group-name fintrust-postgres16-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds describe-db-instances --query "DBInstances[?DBParameterGroups[?DBParameterGroupName=='fintrust-postgres16-dev']].DBInstanceIdentifier" --profile $recoveryProfile --region af-south-1 --no-cli-pager
```

After separate approval, delete only reviewed unused retained resources:

```powershell
& $recoveryAws rds delete-db-snapshot --db-snapshot-identifier APPROVED_ACTUAL_SNAPSHOT_ID --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds delete-db-parameter-group --db-parameter-group-name fintrust-postgres16-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
```

Reconcile retained automated backups separately; manual snapshot deletion does
not remove them. RDS removes its managed secret when the DB is deleted; verify
its actual metadata using the recorded ARN, never independently delete it while
the DB exists. Do not delete the account-wide service-linked role or Stage 1/2
resources. Before retrying, check DB/parameter-group name collisions and retained
resources; adoption or reuse needs a reviewed template, not an automatic retry.

A surviving DB incurs instance hours, storage, managed-secret and applicable
backup/usage charges. A stopped DB still incurs storage/secret/backup costs and
normally restarts after seven days. Manual/final snapshots and retained automated
backups can remain billable after DB/stack removal. The parameter group and
service-linked role have no separate standing charge. Stage 2 S3/KMS costs continue.

Save evidence under docs/EVIDENCE/05-rds: reviewed change set, first failure,
rollback/deletion failures, physical resource inventory, approved recovery decision,
protection-disabled result, final snapshot status, final stack/DB absence and
retained-resource reconciliation. Include stack/change-set IDs, tested commit and
administrator identity; exclude credentials, MFA codes and secret values. A waiter
failure is a signal to inspect events, never proof of cleanup.

References: [stack failure options](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stack-failure-options.html),
[Snapshot/Retain policies](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html),
[RDS deletion](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DeleteInstance.html),
[failed-state snapshot limitations](https://docs.aws.amazon.com/cli/latest/reference/rds/delete-db-instance.html),
[ModifyDBInstance](https://docs.aws.amazon.com/cli/latest/reference/rds/modify-db-instance.html),
[DeleteStack](https://docs.aws.amazon.com/cli/latest/reference/cloudformation/delete-stack.html).

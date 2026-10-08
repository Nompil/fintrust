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

### Stage 3 first deployment failure and retained-group retry

Operator evidence reports fintrust-database-dev reached ROLLBACK_COMPLETE: no DB
instance was created; DatabaseTls / fintrust-postgres16-dev was DELETE_SKIPPED
and remains in RDS, family postgres16, description FinTrust PostgreSQL 16 requires
TLS. The initial missing permission was rds:DescribeEngineDefaultParameters.
The deployer also could not call cloudformation:DescribeStackResource, while the
inventory identity could. These are operator-supplied live findings, not a new
resource inspection by this correction.

Corrected only the two read gaps: ReadRegionalEngineDefaults permits
rds:DescribeEngineDefaultParameters with Resource * and RequestedRegion
 af-south-1. AWS lists no resource type or engine-family condition for this
metadata action; scoping it to a parameter-group ARN or resource tags would not
work. It reads engine defaults, not database records. ReadDatabase adds the
singular DescribeStackResource to its existing exact fintrust-database-dev stack
ARN and regional condition. It is justified for deployment diagnostics, not an
inventory-only restriction. Creation, mutation, encryption, tags, costs and
retention settings are unchanged. No delete permission is added to the deployer.
See [RDS authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rds.html)
and [CloudFormation authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awscloudformation.html).

**Recommended recovery:** with separate administrator approval, remove the failed
stack and the unused retained parameter group, then prepare a fresh reviewed
CREATE. Do not rename the template resource or silently treat the retained group
as newly created. Import/reuse would require a separate adoption/template and
permission review (the current creation policy forbids imports); it is unnecessary
for this unused group and a failed initial deployment. ROLLBACK_COMPLETE permits
only stack deletion before recreating the same stack name. The executed change
set cannot be reused.

Exact manual sequence, one step at a time:

1. Capture stack ID, first CREATE_FAILED permission error, ROLLBACK_COMPLETE,
   DatabaseTls DELETE_SKIPPED / physical ID and the RDS group family/description.
   Save screenshots under docs/EVIDENCE/05-rds; no screenshot was supplied here.
2. Reconfirm approved administrator identity/account 966467878406. Recheck absence
   of fintrust-ledger-dev, and confirm no DB instance uses the retained parameter
   group. AccessDenied is UNKNOWN, not absence. Check the group's FinTrust/dev
   ownership tags. If a DB exists or any instance uses the group, STOP and follow
   the protected-DB runbook; do not delete it.
3. Administrator updates only the existing FinTrustStage3Rds and
   FinTrustStage3CloudFormation customer-managed policies to these corrected
   JSON documents, making the reviewed versions default. No new attachments or
   secret-policy change are needed. Preserve previous versions for review.
4. After explicit deletion approval, delete only fintrust-database-dev and wait
   for stack-delete-complete. Its Retain policy leaves the parameter group.
5. After confirming again that the group is unused and owned, delete only
   fintrust-postgres16-dev. Verify DBParameterGroupNotFound afterward. No final
   DB snapshot is needed because no DB was created; inspect for unexpected
   instances, secrets or snapshots rather than assuming none exist.
6. Re-assume the MFA-backed deployer role; verify account/region and corrected
   policy versions. Prepare a fresh CREATE change set using the existing
   build/stage3-database.json, exact parameters, resource types and tags. Review
   exactly two additions again. Separate RDS execution/cost approval remains
   required; this correction does not authorize any retry.

Commands for steps 2, 4 and 5 (APPROVED_ADMIN_PROFILE is a placeholder, not a
configured profile; all mutations below require separate approval):

```powershell
$recoveryAws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$recoveryProfile = 'APPROVED_ADMIN_PROFILE'
& $recoveryAws sts get-caller-identity --profile $recoveryProfile --no-cli-pager
& $recoveryAws rds describe-db-instances --db-instance-identifier fintrust-ledger-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds describe-db-instances --query "DBInstances[?DBParameterGroups[?DBParameterGroupName=='fintrust-postgres16-dev']].DBInstanceIdentifier" --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds list-tags-for-resource --resource-name arn:aws:rds:af-south-1:966467878406:pg:fintrust-postgres16-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws cloudformation delete-stack --stack-name fintrust-database-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws cloudformation wait stack-delete-complete --stack-name fintrust-database-dev --profile $recoveryProfile --region af-south-1
& $recoveryAws rds delete-db-parameter-group --db-parameter-group-name fintrust-postgres16-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
& $recoveryAws rds describe-db-parameter-groups --db-parameter-group-name fintrust-postgres16-dev --profile $recoveryProfile --region af-south-1 --no-cli-pager
```

The retained parameter group has no separate standing charge. A surviving DB,
secret, snapshot or retained backup would change that conclusion. Preserve
before/after evidence and do not touch the Stage 1/2 stacks, subnet group or
account-wide RDS service-linked role. READY FOR MANUAL RECOVERY means the plan is
prepared for administrator review/approval, not permission to delete or deploy.

Validation for this correction: 37 focused tests passed; Access Analyzer returned
zero findings for both changed policies using fintrust-inventory. Caller identity
matched account 966467878406 / user/fintrust-inventory. No attached policy, stack,
parameter group, change set or other AWS resource was changed. No push occurred.

## Stage 4 risk table and queues approval checkpoint

Operator reports Stage 3 fintrust-database-dev and both RDS resources reached
CREATE_COMPLETE. Stages 1, 2 and 3 are verified by the operator; AWS Integration
remains In Progress. This preparation did not independently re-inspect those
stacks. Database SQL initialization, service users, verified TLS connections and
capacity testing remain later acceptance dependencies.

The existing staged plan defines Stage 4 as DynamoDB + queues. The isolated
[messaging.py](messaging.py) renderer extracts the existing risk table from
foundation.py and the five existing queues from processing.py. It makes no AWS
calls. It renders build/stage4-messaging.json for fintrust-messaging-dev; Stage
is fixed to dev. Exactly six explicit CloudFormation resources are proposed:

| Logical ID | Type | Physical name | Purpose |
|---|---|---|---|
| RiskTable | AWS::DynamoDB::Table | fintrust-risk-dev | Risk projections and durable alert delivery state |
| Transactions | AWS::SQS::Queue | fintrust-transactions-dev.fifo | Ordered scoring jobs |
| TransactionDLQ | AWS::SQS::Queue | fintrust-transactions-dlq-dev.fifo | Exhausted scoring jobs |
| IngestFailures | AWS::SQS::Queue | fintrust-ingest-failures-dev | Lambda asynchronous ingest failure destination |
| ReportFailures | AWS::SQS::Queue | fintrust-report-failures-dev | Report Lambda / later EventBridge failure destination |
| AlertFailures | AWS::SQS::Queue | fintrust-alert-failures-dev | Later DynamoDB stream consumer failure destination |

RiskTable retains the string account_id HASH / score_date RANGE keys, on-demand
PAY_PER_REQUEST billing and NEW_IMAGE stream. TX# projection and ALERT# delivery
state rows share this table; there is no separate delivery-state table. No TTL
is configured: expiring delivery claims could allow unsafe duplicate sends.
No indexes, replicas, provisioned capacity, PITR, export or backup resources are
introduced. Default AWS-owned encryption remains enabled at rest despite
SSEEnabled=false (that field declines an AWS-managed/customer-managed KMS key).
The queues use SQS-managed encryption, with no new CMK or KMS request charges.

Transactions keeps a 720-second visibility timeout (six times the planned
120-second scoring timeout), four-day retention, explicit deduplication IDs and
maxReceiveCount=5 to its FIFO DLQ. All failure queues retain messages for 14 days.
The transaction DLQ additionally restricts redrive sources to the exact transaction
queue with RedriveAllowPolicy byQueue. Its deterministic source ARN avoids a
circular dependency. This controls which queue can use it as a DLQ; it grants
no replay permission. All six resources are tagged Project=FinTrust / Environment=dev
and Retain on deletion/replacement. Retention is intentional for messages, risk
records and uncertain delivery claims; it is not infinite SQS message retention.

This stage creates no Lambda, role, event-source mapping, producer permission,
queue resource policy, notification, alarm, schedule, VPC endpoint or network
change. The stream is enabled but no consumer is wired. ReportQueuePolicy remains
a later EventBridge integration resource; no Events SendMessage grant is needed
now. Outputs supply table name/ARN/stream ARN and each queue URL/ARN for later
stages. Existing endpoint policy already targets fintrust-risk-dev. Outside-VPC
ingest/alert and private scoring placement are unchanged.

**Later-stage dependency:** the combined processing.py still contains queue
creation and foundation.py still contains table creation. Neither combined
template may be deployed over these named Stage 4 resources. Later Lambda-stage
renderers must reference Stage 4 outputs instead of recreating queues/table. No
unrequested runtime/template migration was made during this preparation.

### Stage 4 permission proposals

Attach only after separate administrator approval to fintrust-deployer-role;
use three customer-managed policies, not the nearly-full Stage 1 inline bundle:

- FinTrustStage4CloudFormation: [stage4-cloudformation-policy.json](iam/stage4-cloudformation-policy.json).
  Only fintrust-messaging-dev stack, fintrust-messaging-* change sets, exact
  DynamoDB::Table and SQS::Queue resource types, nonempty resource-type list,
  FinTrust/dev creation tags, no imports, IAM capabilities, execution service
  role or PassRole. Regional template validation needs Resource *. Stack reads
  include singular DescribeStackResource. Stack delete/rollback recovery does
  not authorize physical deletion of retained resources.
- FinTrustStage4DynamoDB: [stage4-dynamodb-policy.json](iam/stage4-dynamodb-policy.json).
  CreateTable/TagResource on only table/fintrust-risk-dev in this account/region,
  required ownership request tags and CloudFormation mediation. Named-table
  DescribeTable/DescribeContinuousBackups/DescribeTimeToLive/ListTagsOfResource
  support provider inspection. No data reads/writes, stream consumption, table
  update, backups, exports or deletion. Creation supplies billing, keys, stream
  and encryption; no broad UpdateTable grant is proposed.
- FinTrustStage4Sqs: [stage4-sqs-policy.json](iam/stage4-sqs-policy.json).
  CreateQueue/TagQueue only on the five exact regional/account queue ARNs with
  required ownership request tags and CloudFormation mediation. SetQueueAttributes
  requires those exact ARNs, ownership resource tags and mediation. GetQueueUrl,
  GetQueueAttributes and ListQueueTags inspect only those queues. No SendMessage,
  ReceiveMessage, DeleteMessage, purge, message move, delete or arbitrary queue list.

SetQueueAttributes can change queue policy/encryption/redrive configuration;
IAM cannot restrict this action to only one reviewed set of attributes. Exact
ARNs, mediation and ownership tags reduce scope but do not replace template
review. Remove configuration grants when no longer needed. CloudFormation
create permissions cannot enforce a resource count; require exactly six Add
operations at change-set review. These proposals are not permissions boundaries
that override other existing grants. Tags are not immutable ownership proof.
No new service-linked role is required by this single-region/table/queue design.

### Cape Town Stage 4 cost

Public regional catalogs confirm the following rates before credits and any
account-wide Free Tier allocation:

| Meter | Rate |
|---|---:|
| SQS standard requests, first paid tier | USD 0.476 / million |
| SQS FIFO requests, first paid tier | USD 0.595 / million |
| DynamoDB Standard on-demand writes | USD 0.84 / million write request units |
| DynamoDB Standard on-demand reads | USD 0.168 / million read request units |
| DynamoDB Standard storage beyond applicable allowance | USD 0.33677 / GB-month |
| DynamoDB Streams reads beyond applicable allowance | USD 0.2694 / million requests |

Sources: [SQS Cape Town catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSQueueService/current/af-south-1/index.json),
[DynamoDB Cape Town catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/af-south-1/index.json),
[SQS metering/free tier](https://aws.amazon.com/sqs/pricing/),
[DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/).

No fixed queue/table instance hourly charge is introduced; empty idle resources
have no material usage bill. Populated DynamoDB storage remains billable after
traffic stops or the stack is removed, subject to applicable allowance. The
catalog shows first 25 GB-month storage and 2.5 million stream read requests
at zero price; these are shared allowances, not verified remaining account
entitlements. SQS lists one million monthly requests free across regions. Do
not assume on-demand reads/writes are covered by provisioned-capacity Free Tier.

Example before allowances: 10,000 FIFO request units, 1,000 standard request units,
10,000 DynamoDB write units, 10,000 read units and 0.01 GB-month storage total
approximately USD 0.019874; this is a scenario, not a measured demo estimate.
Items are metered by size/consistency and SQS payloads by 64-KB chunks; sends,
receives, deletes, empty polling and retries each contribute requests. Later
Lambda streams polling has its own pricing rules; no polling occurs in this
stage. Backup/restore, transfer, Lambda, logs and existing RDS/S3/KMS costs are
outside this subtotal. Live RDS continues its Stage 3 standing cost while this
stage is prepared. Budget alerts are warnings, not spending caps.

### Recovery, evidence and next manual boundary

Before attachment: check managed-policy quota, verify exact JSON scope and confirm
all six intended physical names are absent or known-owned. If any already exists,
STOP for reconciliation; a CREATE does not adopt existing resources. After
approval, an administrator creates/attaches only the three reviewed policies;
the deployer cannot administer IAM. Inventory checks attachments and policy
versions. Re-assume with MFA and verify account/region before later preparation.

Retain deliberately leaves successfully created resources after failed creation
or stack deletion. A ROLLBACK_COMPLETE stack needs separately approved deletion
before a fresh CREATE. Capture failed events and all physical IDs first; retained
queue/table names can collide. Do not silently rename, recreate or delete them.
Import/reuse requires a separately supported reviewed adoption plan. Physical
DeleteQueue/DeleteTable permissions are deliberately absent from this bundle;
provide a separate administrator recovery owner before execution. Failed
resources not tracked by CloudFormation also need metadata inspection.

Retained queues still expire messages after four/14 days: capture queue counts
and failure evidence promptly; this preparation does not authorize reading,
exporting or replaying their contents. Before later disposal, disable all
producers/consumers, reconcile pending work and SENDING/UNKNOWN alerts, preserve
approved evidence/data, and obtain explicit destructive approval. Never purge
or recreate queues to clear errors. DynamoDB data/claims must be reconciled or
backed up under a separately reviewed export/restore plan before table deletion.
The stream has finite record retention, so enabling consumers later requires an
explicit catch-up/reconciliation plan if existing risk data predates the stream
window. No automatic replay is enabled by Stage 4.

The next manual AWS step is review/approval of the three proposed managed
policies and their attachment quota, then administrator attachment. After separate
change-set preparation approval, from the repository root:

```powershell
& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' cloudformation create-change-set `
  --profile fintrust-deployer-role --region af-south-1 `
  --stack-name fintrust-messaging-dev --change-set-name fintrust-messaging-stage4-review `
  --change-set-type CREATE --template-body file://build/stage4-messaging.json `
  --parameters ParameterKey=Stage,ParameterValue=dev `
  --resource-types AWS::DynamoDB::Table AWS::SQS::Queue `
  --tags Key=Project,Value=FinTrust Key=Environment,Value=dev --no-cli-pager
```

Do not run this command during local preparation. Require CREATE_COMPLETE /
AVAILABLE and exactly six Add actions; retain reviewed JSON and later stack
resource evidence under docs/EVIDENCE/07-sqs-dynamodb. Stop again for execution
approval. No policies, change sets, queues, tables or runtime resources were
created or modified by this preparation.

Validation completed after inventory login renewal. Caller identity matched
account 966467878406 and arn:aws:iam::966467878406:user/fintrust-inventory.
Access Analyzer ValidatePolicy returned zero findings for all three Stage 4
identity policies. CloudFormation ValidateTemplate passed for the matching
build/stage4-messaging.json in af-south-1, with only Stage=dev as a parameter and
no IAM capabilities reported. These checks are read-only/static validation;
they do not prove live provider permissions or successful resource creation.
The existing local baseline remains 90 focused tests passed; no code or policy
changed during validation, so tests were not repeated. Whitespace checks passed.

Stage 4 is prepared for policy/attachment review, not deployed or authorized for
execution. Next: administrator review of the three proposed managed policies and
attachment quota, then separate approval before any attachment or change-set
creation. No AWS mutation, deployment, data access or push occurred.

## Stage 5 — ingest Lambda preparation

Stage 1 network, Stage 2 storage, Stage 3 database and Stage 4 messaging are
reported verified by the operator, with their stacks CREATE_COMPLETE. AWS
Integration remains In Progress. The existing sequence makes Stage 5 ingest
only; scoring, alert delivery/SES, query/API and reporting remain later stages.
This preparation does not independently certify their runtime integration.

### Scope and configuration

Render with `python -m infrastructure.ingest_deployment`. The renderer first
checks the retained Linux CI artifact, then writes ignored
`build/stage5-ingest.json`. Proposed stack: `fintrust-ingest-dev`; proposed
change-set name: `fintrust-ingest-stage5-review`. No change set was created.

Exactly three explicit resources:

| Logical ID | Type | Configuration |
|---|---|---|
| IngestLogs | AWS::Logs::LogGroup | /aws/lambda/fintrust-ingest-dev; 14-day retention; Retain on delete/replacement |
| IngestFunction | AWS::Lambda::Function | fintrust-ingest-dev; Python 3.12; x86_64; fintrust.ingest.lambda_handler; 256 MiB; 120 seconds |
| IngestAsync | AWS::Lambda::EventInvokeConfig | $LATEST; two retries; six-hour maximum age; existing ingest failure queue |

All resources stay in af-south-1. The function runs outside the VPC and has no
subnet/security-group attachment or NAT dependency. Environment variables are
FINTRUST_SERVICE=ingest, FINTRUST_STAGE=dev,
TRANSACTION_QUEUE_URL=https://sqs.af-south-1.amazonaws.com/966467878406/fintrust-transactions-dev.fifo,
and QUARANTINE_BUCKET=fintrust-quarantine-966467878406-af-south-1-dev.
AWS supplies AWS_REGION. There are no database credentials, DB environment
variables, Secrets Manager reads, SSM reads, DynamoDB grants or IAM DB grants
for this stage. The cloud ingest path enqueues transactions; it does not query
PostgreSQL. Existing shared-package native dependencies remain unchanged.

ReservedConcurrentExecutions is **0**, deliberately preventing processing.
Live GetAccountSettings returned ConcurrentExecutions=10 and
UnreservedConcurrentExecutions=10. A positive reservation of one would conflict
with the requirement to leave 100 unreserved executions. Zero is the documented
function stop setting. Do not remove the limit to bypass this boundary. Review
regional quota and an approved bounded activation plan separately before enabling
ingest. No quota request was made. Static validation does not prove the live
CloudFormation provider can complete every operation under these permissions.
See [Lambda concurrency controls](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html).

There is no S3 notification, Lambda resource-policy permission, event-source
mapping, schedule or invocation in this stage. Async failure configuration alone
does not activate a producer. SQS/DynamoDB consumers remain unwired.

### Matching package and upload boundary

Use only `build/ci-evidence/37342810131/fintrust-linux-verified/fintrust.zip`,
with its matching manifest, CI evidence and verifier log. The older
`build/fintrust.zip` is not approved for this deployment.

SHA-256: d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62.
Compressed size: 21,646,562 bytes; uncompressed size: 37,097,109 bytes.
The retained manifest has linux_execution_verified=true: all five archived
handlers imported on Linux CPython 3.12/x86_64; native psycopg and CA checks passed,
with no forbidden network attempts. Local verification rechecked archive CRC,
native binary structure, sizes/digest, matching green CI evidence and current
runtime/UI/SQL source, allowing Windows text line-ending conversion. It did not
execute Linux native imports on Windows or rebuild the package.

The existing reports bucket is reused for the package, under an isolated
`deployment/lambda/<SHA-256>/fintrust.zip` key. Exact bucket:
fintrust-reports-966467878406-af-south-1-dev. No new artifact bucket is proposed.
The required CodeObjectVersion parameter has no default and rejects null; its
actual value is unresolved because no package upload occurred. Separately
approve an administrator upload of the exact verified bytes under existing KMS
protection, then verify the uploaded version/checksum before preparing a change
set. S3 ETag is not a SHA-256 proof. Retain object version, digest, CI evidence and
reviewed template together. Every rebuild requires matching Linux evidence again.

### IAM review and bootstrap

Proposed deployer attachment: **FinTrustStage5Deployment**, from
`infrastructure/iam/stage5-deployment-policy.json`. It combines exact-stack
CloudFormation permissions, tagged/CloudFormation-mediated Lambda/log creation
and configuration, exact-role PassRole to Lambda, exact package-version S3 read,
and existing-key decrypt via S3. No InvokeFunction, AddPermission, event-source
mapping creation, package upload or execution-role administration is granted.
Only ValidateTemplate/GetTemplateSummary and regional log-group enumeration use
Resource="*", where the APIs need that scope. Named change sets are restricted
to fintrust-ingest-*; creation requires the three exact resource types, FinTrust/dev
tags, no service role and no imports. No IAM capabilities are needed.

The live deployer has nine managed-policy attachments; this single policy fits
the default tenth slot and the 6,144-character policy-size limit. Confirm the
actual attachment quota before approval. Later stages need a separate policy
lifecycle review rather than silently removing earlier grants.

An administrator must separately create execution role **fintrust-ingest-dev**
using `stage5-ingest-trust.json` (Lambda service only), and attach only
**FinTrustStage5IngestRuntime**, from `stage5-ingest-runtime-policy.json`.
Live GetRole found this role absent. The template references its exact ARN and
does not create IAM resources. Existing KMS key:
arn:aws:kms:af-south-1:966467878406:key/598a4158-2cc6-4946-af24-512784a276c8.
Runtime grants are log streams/events in the exact group, raw/raw/* object reads,
quarantine/quarantine/* writes, and SendMessage to the existing transactions FIFO
and ingest failure queues. KMS decrypt/data-key grants require S3 mediation,
caller account and the respective bucket/object encryption context. Bucket-level
context supports S3 Bucket Keys; S3 object permissions still bound the prefixes.
The runtime role cannot read the deployment package or administer resources.

### Validation, cost and recovery

Focused tests: **95 passed** across Stage 5, Stage 4, processing, ingest and
package checks. No full database suite or CI rerun was needed for this scoped
preparation. Access Analyzer returned zero findings for the final deployer and
runtime identity policies and Lambda trust resource policy. CloudFormation
ValidateTemplate passed for the final disabled template; CodeObjectVersion is
the only parameter, with no IAM capabilities reported. Identity matched the
fintrust-inventory user in account 966467878406. Validation is static/read-only,
not proof of deployment, uploaded-code loading or end-to-end processing.

No provisioned concurrency or additional fixed-price resource is introduced.
IAM roles have no resource standing charge; Lambda usage, CloudWatch logs,
S3 package/version storage and KMS requests are usage-based. Zero concurrency and
unwired sources prevent normal function execution, but stored package versions
and retained logs can still cost money. Existing RDS, Secrets Manager, S3 and
customer-managed KMS costs continue independently. No account-specific Free Tier
coverage or zero total bill is promised; estimate invocation volume before
activation. See [Lambda pricing](https://aws.amazon.com/lambda/pricing/).

The execution role and package are administrator-created prerequisites outside
this stack. Log retention intentionally leaves the log group behind during
rollback/deletion; its physical name can collide on retry. Capture stack events,
physical IDs and retained resources before any cleanup. Function deletion is
CloudFormation's default, but this policy intentionally omits physical Lambda
DeleteFunction/DeleteFunctionEventInvokeConfig and log deletion grants. A failed
creation may therefore need separately approved administrator cleanup and can
reach ROLLBACK_FAILED. Do not blindly retry or widen the role to resolve it.
Reconcile any function/config/log/role/package objects, preserving required
evidence. ROLLBACK_COMPLETE needs separately approved stack deletion before a
fresh CREATE. Destructive cleanup or import/reuse remains a separate decision.

Next manual AWS step: review and explicitly approve the exact execution-role
bootstrap, single deployer policy attachment and verified-package upload plan.
Only afterward resolve CodeObjectVersion and separately approve change-set
preparation. Require exactly three Add actions and stop again before execution.
No IAM attachment, upload, change-set creation, invocation, deployment, quota
change or push occurred during this preparation. Stage 5 is prepared for review;
activation remains blocked pending the concurrency quota decision.

### Stage 5 batch-send permission review

A pre-deployment review raised a suspected missing batch-send permission because
fintrust/ingest.py calls sqs.send_message_batch. The AWS SQS API permissions
reference explicitly maps both SendMessage and SendMessageBatch to the IAM action
sqs:SendMessage. There is no separate sqs:SendMessageBatch IAM action to add.
The existing runtime policy already grants the required permission on exactly
fintrust-transactions-dev.fifo and fintrust-ingest-failures-dev; the latter
supports Lambda's async failure destination. No policy or application change
was required, and no queue scope was broadened.

Source: [AWS SQS API permission mapping](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-api-permissions-reference.html).
A focused regression check now locks the SQS action and both exact queue ARNs.
The full Stage 5 focused selection passed: 96 passed, zero failed/skipped.
Access Analyzer revalidated the unchanged runtime policy with zero findings.
Offline package/source consistency passed again for SHA-256
 d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62
and matching linux_execution_verified=true evidence. No new package or Linux
CI run is required because application/package sources did not change.

Stage 5 is READY FOR MANUAL AWS SETUP after explicit approval of the previously
reviewed bootstrap, attachment and upload actions. This is not deployment or
activation readiness: verify the exact uploaded VersionId/checksum before the
change set, keep concurrency zero and triggers unwired, and confirm the controlled
administrator recovery session before execution. The operator reports
fintrust-admin is available; it was not authenticated or used during this review.
No AWS mutation, role creation, policy attachment, package upload, change set,
Lambda deployment, activation, trigger wiring or push occurred.

### Stage 5 tagged log-group failure and recovery

Live read-only inventory confirmed fintrust-ingest-dev is ROLLBACK_COMPLETE.
The first CREATE_FAILED event is IngestLogs (AWS::Logs::LogGroup), reporting
that CreateLogGroup with tags requires the additional logs:TagResource permission.
The unchanged template requests FinTrust/dev tags and 14-day log retention.
This is a provider authorization requirement that static template validation
alone did not establish.

The only policy correction is a separate TagIngestLogGroup statement granting
logs:TagResource on exactly
arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev.
The tagging ARN omits the :* suffix used by other log operations. Conditions
require aws:RequestedRegion=af-south-1, aws:RequestTag/Project=FinTrust,
aws:RequestTag/Environment=dev and aws:CalledVia containing
cloudformation.amazonaws.com. Existing statements remain unchanged; no delete,
untag or unrelated Logs actions were added. Resource ownership tags are not
required before creation because the resource does not yet exist.
Sources: [CreateLogGroup tagged-creation permissions](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html),
[TagResource ARN format](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_TagResource.html).

CloudFormation records IngestLogs physical ID /aws/lambda/fintrust-ingest-dev
as DELETE_SKIPPED. However, DescribeLogGroups returned no matching groups;
ListTagsForResource and DescribeLogStreams both returned ResourceNotFoundException.
The physical group therefore does not currently exist. Its retention, tags and
streams are not applicable, rather than evidence that a retained group has the
intended settings. No log events were read. The stack resource list contains only
IngestLogs, with no Lambda or async configuration recorded. DELETE_SKIPPED is a
retention record and does not itself prove successful physical creation.
Administrator log-group deletion is neither needed nor justified at this checkpoint.
Recheck existence immediately before retry; if it appears, stop and reconcile
ownership, retention, tags, streams and data preservation before any deletion.

The exact uploaded package version was inspected read-only:
- bucket: fintrust-reports-966467878406-af-south-1-dev
- key: deployment/lambda/d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62/fintrust.zip
- VersionId: 8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.
- ContentLength: 21,646,562 bytes; ServerSideEncryption: aws:kms
- key ARN: arn:aws:kms:af-south-1:966467878406:key/598a4158-2cc6-4946-af24-512784a276c8
- BucketKeyEnabled: true.

HeadObject with checksum mode returned no checksum field. A version-specific
GetObject attempt was denied because fintrust-inventory lacks kms:Decrypt.
No read permission was broadened and no administrator identity was used.
Remote byte-level checksum verification is therefore based on the operator's
previous verified upload evidence, not a new independent hash claim. Local
matching package/source/manifest checks passed again, with retained Linux
verification true and SHA-256
d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62.
The ZIP, function sources and template did not change. Reuse the exact uploaded
VersionId; no rebuild or re-upload is needed. If prior checksum evidence cannot
be produced, use the controlled administrator to download that exact existing
version and compare SHA-256 before retry, without uploading another object.

Validation: 97 focused tests passed, zero failures/skips, across Stage 5,
Stage 4, processing, ingest and package tests. Access Analyzer ValidatePolicy
returned zero findings for the corrected Stage 5 deployer policy. The regression
checks the new exact tagging ARN, required request tags, Cape Town restriction,
CloudFormation mediation and absence of unrelated Logs actions. IAM policy size
remains within the existing tested 6,144-character managed-policy limit.

Manual recovery sequence, only after explicit approval:
1. Preserve failed stack events, stack ARN, resource list, absent-log-group output
   and original artifact/version verification evidence under docs/EVIDENCE/08-lambda.
2. Using the controlled administrator, create a new version of the existing
   FinTrustStage5Deployment managed policy from stage5-deployment-policy.json,
   set it as default, and leave all other policies/attachments unchanged. Inspect
   existing versions first; do not create a duplicate policy or delete versions
   blindly. Inventory verifies the new default JSON and existing attachment.
3. Recheck the failed stack's resources and absent physical group. With separate
   deletion approval, remove only the ROLLBACK_COMPLETE fintrust-ingest-dev stack.
   A fresh CREATE using the same stack name requires that failed stack to be
   deleted first. Do not use ContinueUpdateRollback for a failed CREATE.
4. Wait for stack deletion, confirm the log group is still absent, and preserve
   the execution role and exact S3 artifact version. No log-group deletion is
   presently required. Stop if any unexpected live resource appears.
5. Re-assume the deployer role with MFA and confirm account/region. With separate
   preparation approval, create fintrust-ingest-stage5-review for
   fintrust-ingest-dev from unchanged build/stage5-ingest.json, using
   CodeObjectVersion=8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx., the three approved resource
   types and FinTrust/dev tags. Wait and inspect exactly three Add actions.
6. Stop before execution approval. Keep concurrency zero and triggers unwired.

The administrator stack-deletion commands, NOT executed here, are:

```powershell
& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' cloudformation delete-stack `
  --stack-name fintrust-ingest-dev --profile fintrust-admin `
  --region af-south-1 --no-cli-pager
& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' cloudformation wait stack-delete-complete `
  --stack-name fintrust-ingest-dev --profile fintrust-admin --region af-south-1
```

Confirm the administrator identity before using those commands. Static validation
still does not prove all future provider permissions. READY FOR MANUAL RECOVERY:
the known authorization defect is corrected and no physical log-group deletion
is required. Recovery actions require explicit approval; deployment retry and
activation are separate gates. No AWS IAM update, deletion, upload, change set,
Lambda deployment, concurrency change, trigger wiring or push occurred here.

### Stage 5 repeated tagging denial: effective-authorization investigation

This finding supersedes the earlier READY FOR MANUAL RECOVERY recommendation.
The second deployment also reached ROLLBACK_COMPLETE. Inventory independently
confirmed FinTrustStage5Deployment v2 is default, attached to fintrust-deployer-role,
and includes the exact TagIngestLogGroup statement. The role has no permissions
boundary; the stack has no CloudFormation service-role ARN. No AWS policy was
changed during this investigation.

AWS documents TagResource resource-level log-group scope with an ARN that has
no trailing :*. The Service Authorization Reference lists aws:RequestTag,
aws:ResourceTag and aws:TagKeys for TagResource/log-group. Request-tag conditions
are valid for this action; there is no basis to claim they are unsupported.
AWS also describes CalledVia as conditional on supported forward access sessions,
not as a key guaranteed for every provider-side dependent permission evaluation.
Supporting a key does not prove that the failed dependent check supplied it.
Sources:
- [CloudWatch Logs authorization actions and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html)
- [LogGroup IAM ARN distinction](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_LogGroup.html)
- [IAM CalledVia availability](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-calledvia)

CloudTrail returned two CreateLogGroup failures, including the retry at
2026-10-08T13:07:08Z. Both identify an assumed fintrust-deployer-role principal
and invokedBy=cloudformation.amazonaws.com. The retry has request ID
4405018a-9e3c-4599-bd04-4f10a38f16cb. RequestParameters, resources and additional
event data are absent. TagResource lookup returned zero events for the inspected
window. This points to the additional permission check within CreateLogGroup;
it does not prove there was a separate TagResource API request. CloudTrail's
invokedBy field is not a dump of the IAM CalledVia context.

Read-only IAM simulations of the isolated live-v2 tagging statement returned:

| Supplied hypothetical request context | Decision |
|---|---|
| Exact no-suffix ARN; region, Project, Environment and CalledVia present | allowed |
| Same ARN/tags/region, CalledVia absent | implicitDeny; missing aws:CalledVia |
| Same ARN/region/CalledVia, request tags absent | implicitDeny; missing both request-tag keys |
| ARN ending :*, all condition values present | implicitDeny; resource mismatch |

A structured SimulatePrincipalPolicy request for the full live role with the
correct no-suffix ARN and all four context values also returned allowed.
These simulations are hypothetical policy evaluation, not an observation of
CloudWatch Logs' actual dependent-authorization resource/context. Initial CLI
list-form simulations had argument parsing failures or unsuitable aggregate
output; only the successful structured requests above are diagnostic evidence.
No simulated deny was misrepresented as the real provider failure.

The exact failed condition or internal authorization ARN remains UNKNOWN.
The evidence does not justify changing the documented tagging ARN, removing
request-tag conditions, removing CalledVia, or claiming a working correction.
Fresh STS credentials were reported by the operator. No stale-session contribution
was established; identical CloudTrail session names do not independently prove
credential lifetime. Full request authorization can also involve session or
organization controls outside the isolated statement. Neither static validation
nor simulation proves all such live controls or internal authorization checks.

No IAM correction was made. The before/after TagIngestLogGroup statement is
identical to v2. Existing focused scope/condition regression tests remain intact;
no test fabricates unknown provider-call context. The full Stage 5 focused
selection still passed: 97 passed, zero failures/skips. Access Analyzer
revalidated the unchanged deployer policy with zero findings. These results do
not close the live permission blocker.

Live logs inventory again returned no log group. CloudFormation lists only
IngestLogs /aws/lambda/fintrust-ingest-dev as DELETE_SKIPPED; no physical log
cleanup is currently required. The earlier uploaded ZIP VersionId remains the
specified deployment artifact: 8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.
No runtime, template or package source changed and no rebuild/re-upload is needed.
This turn did not independently rehash the encrypted remote artifact; retain
previous exact-version checksum evidence.

DO NOT APPLY YET / NOT READY FOR MANUAL RECOVERY. Next diagnostic evidence needed:
obtain the effective resource ARN and condition context used by the failed
CreateLogGroup dependent tagging authorization, using the recorded request ID,
account, region, time and principal in an administrator-reviewed AWS support
investigation, or separately approve a tightly controlled diagnostic experiment.
No support message or diagnostic AWS mutation was sent/performed here.
Do not silently broaden the tagging resource or weaken conditions as a guess.

Once that evidence identifies the specific mismatch: prepare the minimal local
correction, test supported context cases, simulate it, validate with Access
Analyzer, and obtain approval before replacing the live default policy version.
Then preserve failure evidence, reconcile resources, obtain separate deletion
approval for the ROLLBACK_COMPLETE stack, verify the physical group remains absent,
and prepare a fresh reviewed CREATE using the same exact package version.
Keep concurrency zero and triggers unwired. Stop again before execution.
No AWS IAM update, stack/log deletion, package upload, change set, deployment,
concurrency change, trigger wiring or push occurred during this investigation.

### Stage 5 controlled diagnostic proposal

[STAGE5_DIAGNOSTIC.md](STAGE5_DIAGNOSTIC.md) prepares the temporary CalledVia-only
experiment, validated with 99 focused tests, seven IAM simulations and zero
Access Analyzer findings. Canonical policy remains unchanged. The plan is ready
for review; no experiment or AWS mutation is approved or executed.


### Local transaction-identity hardening checkpoint

[Identity, batch audit and duplicate-charge handling](../docs/IDEMPOTENCY.md)
records the new local implementation, additive migration and review/release gates.
Duplicate data is prevented/audited; distinct suspicious charges remain in the
ledger. No AWS migration or permission update was performed. New runtime source
requires a new Linux-verified artifact; the earlier uploaded ZIP remains evidence
for its previous source only. Stage 5 tagging recovery and deployment remain
separate, unexecuted approval checkpoints. Do not run older Stage 5 commands as a
release procedure for the new source.

Local hardening validation: 252 passed, 0 failed, 1 existing administrator-only
skip. New proposed runtime policy Access Analyzer validation: zero findings.
Current source/package consistency: BLOCKED until a new reviewed Linux build;
the retained historical artifact is unchanged. Review the hardening before any
RDS migration, role update, package release or Stage 5 recovery execution.


### Stage 5 second controlled tagging-context diagnostic

Experiment one (temporary v3, CalledVia removed only) still failed with the same
logs:TagResource dependent-creation denial, request ID
`e9ed29b3-f2dc-48d0-befb-801908dce534`. Read-only inventory confirms canonical v2
is default again, the failed stack is ROLLBACK_COMPLETE and the group is absent.

[STAGE5_DIAGNOSTIC2.md](STAGE5_DIAGNOSTIC2.md) prepares a separate temporary policy
removing only the request-tag pair relative to v3, retaining exact ARN/region.
106 focused tests passed with zero failures/skips; seven actual read-only IAM
simulation cases matched expectations; Access Analyzer returned zero findings.
The plan includes one approved attempt, capture and mandatory v2 restoration.
Success would strongly implicate request-tag context, not prove the exact missing
key; the same denial means stop broadening IAM and inspect other authorization
mechanisms. Canonical policy remains unchanged. No AWS mutation or push occurred.

The existing object/version and historical Linux evidence are unchanged. No
rebuild/upload is required for this historical policy diagnostic. The already
committed identity-hardening source still needs its own new Linux-verified package
before a current-source deployment. Do not confuse those separate approval gates.


## Complete tagged-create authorization investigation (2026-10-08)

The second live diagnostic also failed (request ID
`21ae5b40-b1d9-421a-a113-87728de892de`); v2 restoration is verified.
[Complete authorization review](STAGE5_AUTHORIZATION_REVIEW.md) examines both
CreateLogGroup and TagResource, all current role policies, boundaries, session
evidence, Organizations and the regional provider schema. No boundary, applicable
SCP or Logs-relevant explicit deny was found. CloudTrail omits failed-call request
parameters and actual IAM context. Do not claim all tagging hypotheses eliminated.

Fifteen read-only simulations show that v4 may allow tagging while the unchanged
CreateLogGroup gate denies without CalledVia or tags. A separate local candidate
changes only primary CreateLogGroup CalledVia relative to v4, preserving both
creation ownership tags and all other grants. This is a proposed discriminating
test, not a proven fix; canonical and previous diagnostic policies are unchanged.
117 focused tests passed with no failures/skips; Access Analyzer returned zero
findings for canonical and candidate. No AWS mutation or push occurred.
Stop for review before any policy version, cleanup, change set or deployment.

### Stage 5 direct failure and targeted legacy tagging preparation

The third controlled CloudFormation experiment (v5) failed before Lambda
creation, followed by one separately approved direct SDK tagged-create attempt
that failed with the same additional TagResource error. Direct request:
9aa1ba5a-1a43-4238-bd8d-a62f4b038348. Both experiments restored canonical v2;
the exact log group remains absent, the failed stack is not deleted again,
and AWS Integration remains In Progress. Runtime code/package and Stages 1-4
are unaffected. Full local evidence: docs/EVIDENCE/08-lambda/45-stage5-diagnostic3-result.md
and 51-stage5-direct-logs-result.md.

A final targeted alternative-path diagnostic is prepared only:
[TagLogGroup plan](STAGE5_TAGLOGGROUP_DIAGNOSTIC.md). Relative to v5, it adds
only logs:TagLogGroup for the exact ingest log-group ARN with :* and region.
No existing grant is relaxed. Full v2/v3/v5 archival evidence and candidate-bound
read-only validation are committed under iam/evidence/. Proposed future version
cleanup deletes only archived, nondefault v3 after separate approval, preserving
canonical v2 and v5 control; no deletion or policy-version creation occurred.
No direct creation/CloudFormation retry is authorized by this preparation.

### Stage 5 permanent legacy tagging correction — approval checkpoint

The approved one-shot direct v6 test succeeded: HTTP 200, zero retries, request
e641540c-a094-42b4-9411-b06bfeda7e8b. Exact FinTrust/dev tags were verified and
the empty diagnostic group deleted. Canonical v2 was restored; v6 remains
nondefault. Earlier TagResource relaxations, primary CreateLogGroup CalledVia
relaxation and the v5 direct test failed.

Local stage5-deployment-policy.json now equals archived canonical v2 PLUS ONLY
the proven logs:TagLogGroup grant on the exact suffixed ingest group in af-south-1.
Primary creation/modern TagResource retain all canonical tags and CalledVia. The
new one-group legacy grant permits direct retagging and has only the proven
region condition; review this tradeoff before installation. No diagnostic-wide
relaxations are promoted. This is a prepared permanent fix, not a live deployment.

[Permanent policy review and exact recovery commands](STAGE5_PERMANENT_FIX.md)
supersedes the older diagnostic retry plans for future work. Proposed version-slot
cleanup is archived nondefault v4 only; preserve v2/v5/v6. Current AWS v2 remains
default. Read-only preparation completed 18 simulations and zero Access Analyzer
findings; regression results are recorded in the permanent-fix document.

After separate approvals: install one new permanent version; delete the failed
ROLLBACK_COMPLETE stack only after preserving evidence; confirm physical group
and Lambda absence; prepare fintrust-ingest-stage5-permanent-review with unchanged
build/stage5-ingest.json and CodeObjectVersion=8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.;
review exactly three Adds; stop before the one execution. Reserved concurrency
remains 0, no triggers, no historical package rebuild/upload or SQL changes.
The newer duplicate/idempotency release remains a separate later build/migration
and deployment. Do not rerender the frozen template or mix the two releases.


## Current checkpoint: async qualified ARN and CREATE rollback failure

The permanent logs fix created IngestLogs and IngestFunction. IngestAsync failed
on PutFunctionEventInvokeConfig for the exact $LATEST ARN; rollback failed on
missing DeleteFunctionEventInvokeConfig. The stack is ROLLBACK_FAILED and v2
is restored as default. See [STAGE5_ASYNC_FIX.md](STAGE5_ASYNC_FIX.md) for the
size-constrained supplemental policy, read-only evidence and administrator cleanup
plan. Earlier ROLLBACK_COMPLETE retry instructions are historical and must not
be executed for this state. No AWS mutations or runtime/SQL changes in this review.

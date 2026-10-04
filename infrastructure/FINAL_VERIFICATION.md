> Retained engineering evidence and procedure snapshot. Current navigation: [operations](../docs/OPERATIONS.md) and [evidence register](../docs/EVIDENCE/README.md). Preparation does not establish execution.

# Final Phase 2 verification

Follow-up: [LINUX_CI_GATE.md](LINUX_CI_GATE.md) records the completed pre-push
review and prepared Ubuntu/Python 3.12 workflow. Linux execution remains
unverified until that workflow succeeds; the recommendation below is unchanged.

Decision: **NOT READY** to close the requested offline gate. Linux execution
evidence is missing. Inventory is prepared but not authorized or executed.
Public documentation was consulted without AWS account access.

## A. Linux package verification

The Windows host has no Docker or installed WSL distribution. The repository has
no Git remote, so its manual GitHub workflow cannot be dispatched here. Installing
WSL, configuring a remote or pushing was outside this workspace-only task.

The verifier now checks Linux x86_64 / CPython 3.12, manifest runtime/architecture,
handlers, digest, encoded digest and sizes before execution. An isolated subprocess
imports all five archived handlers and native psycopg, checks their locations,
reads bundled SQL, loads CA certificates and rejects socket/DNS operations.
The CA checksum must match. Success records the actual platform and probe results.
These checks are implemented and regression-tested; they have not run on Linux.

Rebuilt archive: `build/fintrust.zip`, compressed **21,896,842 bytes**, uncompressed
**37,314,792 bytes**. Structural/CRC/size checks passed.
SHA-256: `ed0bc4826040b717086b7025ffb24e4e15ab54ccabfeaf205d408f924601cbba`.
CA SHA-256: `fe45bbebf92ad3e27a583bbb2ddd1553c521ed4d49af5514dc0a40372ea5395c`.
The matching manifest correctly retains `linux_execution_verified: false`.
Build outputs are ignored by Git. No upload occurred.

On an authorized Linux x86_64 Python 3.12 runner, from this checkout:

```sh
python3.12 tools/verify_lambda_linux.py build/fintrust.zip
```

Keep the ZIP and resulting manifest together. Every rebuild requires verification
again. The existing workflow uses Ubuntu: success proves Linux imports, not the
exact Lambda Amazon Linux 2023 OS. For that stronger evidence, also execute this
verifier inside the official Lambda Python 3.12 image on an authorized Docker
runner with networking disabled. Neither replaces cloud integration testing.

## B. af-south-1 compatibility

No required regional feature was found unsupported. Availability is distinct
from account opt-in, quotas, correct configuration and deployment evidence.
Keep Cape Town; never substitute another region automatically.

| Service / feature | Supported? | Limitation | Required action |
|---|---|---|---|
| Lambda Python 3.12 / VPC | Yes | Private attachment grants no internet access | Verify package and subnet/ENI permissions. [Region](https://docs.aws.amazon.com/general/latest/gr/lambda-service.html), [runtime](https://aws.amazon.com/about-aws/whats-new/2023/12/aws-lambda-support-python-3-12/), [VPC](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html) |
| S3 / gateway endpoint | Yes | Routes/prefix lists are regional; IAM and endpoint policy both apply | Keep buckets and endpoint in Cape Town; review associations. [Region](https://docs.aws.amazon.com/general/latest/gr/s3.html), [gateway](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) |
| SQS FIFO / FIFO DLQ / redrive | Yes | Redrive requires matching FIFO destination and permissions; ordering versus new traffic needs review | Preserve messages; authorize replay separately. [Region](https://docs.aws.amazon.com/general/latest/gr/sqs-service.html), [feature](https://aws.amazon.com/about-aws/whats-new/2023/11/amazon-sqs-fifo-dead-letter-queue-redrive/) |
| DynamoDB / Streams / gateway | Yes | Gateway handles table calls; Lambda service manages stream polling | Confirm keys, stream view, ARN and failure queue. [Region](https://docs.aws.amazon.com/general/latest/gr/ddb.html), [gateway](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) |
| RDS PostgreSQL / IAM authentication | Yes | PostgreSQL 16 IAM authentication available in all regions; actual instance configuration unknown | Verify engine, TLS, private endpoint and three IAM DB users. [Feature support](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RDS_Fea_Regions_DB-eng.Feature.IamDatabaseAuthentication.html) |
| API Gateway REST | Yes | AWS_IAM methods require signed requests; browser currently does not sign | Confirm Regional API; choose authenticated demo path. [Endpoints](https://docs.aws.amazon.com/general/latest/gr/apigateway.html) |
| SES API / sandbox | Yes, API | No Cape Town SMTP endpoint. Regional sandbox requires verified senders/recipients; 200 messages/day and 1/second | Keep boto3 SES API; verify identities and actual limits. [Region](https://docs.aws.amazon.com/general/latest/gr/ses.html), [sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html) |
| EventBridge scheduled rules | Yes | Legacy scheduled rules use default bus and UTC | Keep report schedule disabled until approved. [Region](https://docs.aws.amazon.com/general/latest/gr/ev.html), [rules](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html) |
| CloudWatch Logs / alarms | Yes | Availability does not prove configured alarm recipients | Inspect retention; configure approved thresholds before traffic. [Logs](https://docs.aws.amazon.com/general/latest/gr/cwl_region.html), [CloudWatch](https://docs.aws.amazon.com/general/latest/gr/cw_region.html) |
| X-Ray | Yes | Active tracing/grants not configured in templates | Track as outstanding observability work. [Region](https://docs.aws.amazon.com/general/latest/gr/xray.html) |
| KMS customer-managed keys | Yes | Regional keys; ciphertext depends on retained decrypt access | Inspect existing key/alias first; creation separately approved. [Region](https://docs.aws.amazon.com/general/latest/gr/kms.html) |

## C. Region consistency

Fixed mixed resolution: S3, SQS, SES, Lambda and alert DynamoDB clients now use
the same `AWS_REGION` as database clients. A subprocess regression with a
conflicting SDK default confirms all runtime clients remain in Cape Town.

Foundation/processing/API definitions use regional pseudo-parameters; SSM/IAM
rendering defaults and preflight target Cape Town. Portable renderers cannot
prevent an operator selecting a different deployment region: future identity,
command-region and ARN checks must enforce this boundary.

The older `infrastructure/iam/audit.py --rest-api-id` helper still uses the SDK
default region. Use the new explicit-region inventory procedure instead. No
helper was executed against AWS. Historical training references remain intact.
Billing inventory's `us-east-1` is a global-service endpoint exception, not
application placement.

## D. Read-only inventory procedure

[READ_ONLY_INVENTORY.md](READ_ONLY_INVENTORY.md) supplies exact PowerShell commands,
identity/region checks, metadata-only reads and pagination/error guidance for all
requested resources. No SSM values, queue messages, objects, rows or log events
are requested. AccessDenied means UNKNOWN. Cost Explorer query charges need
approval even though the query is read-only. Commands remain unexecuted.

## E. Resource reconciliation

The inventory document includes per-resource REUSE, IMPORT, UPDATE, CREATE,
LEAVE UNTOUCHED and CONFLICT REVIEW decisions. All are provisional until ownership
and compatibility are established. Preserve data, notifications, roles and route
associations. Existing physical names cannot simply be supplied to CREATE-only
templates: adapt references or use a separately reviewed supported import.

## F. Required parameters

[OPERATOR_PARAMETERS.md](OPERATOR_PARAMETERS.md) is a blank nonsecret worksheet
covering account, region, network, database, buckets, queues, key, roles, SSM,
email, API, frontend origin, package, monitoring and budget. Missing values remain
unresolved. The current foundation shares two private subnets between application
and database resources; a separate database subnet tier is not implemented.

## G. Cape Town cost risks

| Category | Exposure | Decision |
|---|---|---|
| Standing costs | Existing RDS hours, storage and retained backups/snapshots; one CMK | Inventory first. Foundation creates no new DB instance. |
| KMS base | Expected **USD 1/key/month** in af-south-1, prorated hourly; first two rotations each add USD 1/month; requests extra | One new unrotated key starts at USD 1/month before requests/tax. Not a total bill or free-tier promise. [Published key-storage price](https://aws.amazon.com/kms/pricing/) |
| Usage / retained capacity | S3 versions/storage/archive retrieval, DynamoDB on-demand/storage, SQS, SES, Lambda, REST API, logs/metrics/alarms, X-Ray if enabled, transfer | Estimate with Cape Town rates and approved volume. Idle retained storage still costs money. |
| No endpoint fixed charge | S3 and DynamoDB gateway endpoints | No endpoint hourly charge; underlying usage remains billable. [Gateway documentation](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) |
| Prohibited / unapproved | NAT gateway creation prohibited; interface endpoints unapproved | Neither required by proposed placement. Preserve unrelated existing resources. |
| Account-specific | Plan, credits, expiry, payer allocation, currency and tax | Unknown. Owner must confirm; budget alerts are not a hard spending cap. |

No zero-cost claim is made. Retention, alarms and cleanup/backup decisions precede
normal traffic. One CMK is approved in principle only, not for creation.

## H. Tests

Full local run: **158 passed, 0 failed, 1 skipped** using
`tools/local.py test --database` against `fintrust_local_test`.
The service-role execution check requires a disposable database administrator.
Nine added cases cover manifest mismatches, blocked DNS/socket calls and region
defaults. No existing tests were weakened. Local checks do not prove Linux
execution or AWS integration.

## I. Remaining P0 blockers

1. Execute the matching archive on authorized Linux x86_64 Python 3.12; retain
   successful evidence. Exact Lambda OS testing is a separate stronger check.
2. Obtain separate inventory authorization; confirm account opt-in, ownership,
   RDS configuration, policies and quotas.
3. Resolve real parameters, resource reconciliation, budget and CMK cost approval.
4. Before deployment: validate target IAM/CloudFormation, DB IAM grants/TLS, SES
   identities and authenticated dashboard access.

Before consumers/schedules: complete alarms, replay/uncertain-send recovery,
service-role DB tests and cloud integration evidence. Active X-Ray is outstanding.
Ledger deletion remains blocked pending verified export, reconciliation,
retention approval and restore testing.

## J. Recommendation

**NOT READY.** Regional documentation supports the architecture and local tests
pass, but the required Linux execution gate has not passed. Complete that gate,
then seek separate read-only inventory authorization. This does not authorize
provisioning or enablement.

## K. Stop

No AWS account calls, uploads, deployments, resource changes, email sends,
trigger enablement or Git pushes occurred. Wait for separate authorization.

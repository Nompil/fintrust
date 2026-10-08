# Stage 5 permanent Logs authorization correction and recovery

Status: **PERMANENT STAGE5 IAM FIX READY FOR DEPLOYMENT** means locally prepared,
regression tested and read-only validated. Installation, failed-stack deletion,
change-set preparation and execution each remain approval checkpoints. This
preparation performs no AWS mutation.

## Permanent change: canonical v2 plus one grant

Before: v2 has no logs:TagLogGroup statement. It grants CreateLogGroup on the
exact suffixed group with region, FinTrust/dev request tags and CloudFormation
CalledVia; its modern TagResource grant uses the exact unsuffixed group with
those same conditions.

After: all v2 statements remain identical, in order, plus:

```json
{
  "Sid": "LegacyTagIngestLogGroup",
  "Effect": "Allow",
  "Action": ["logs:TagLogGroup"],
  "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev:*",
  "Condition": {
    "StringEquals": {"aws:RequestedRegion": "af-south-1"}
  }
}
```

The canonical file is iam/stage5-deployment-policy.json. It is built from the
archived live v2 document, not from v5/v6. No other grant, resource, tagging,
PassRole, package, KMS or CloudFormation restriction changes. No wildcard Logs
action or wildcard group name is added. Existing DescribeLogGroups retains its
required Resource="*"; that discovery permission is not new.

AWS documents the :* ARN for most log-group actions; modern TagResource,
UntagResource and ListTagsForResource use the unsuffixed form. The successful
legacy-path diagnostic used the exact suffix and only the region condition.
The authorization table lists request-tag conditions, but listing a key does
not establish its propagation during the dependent creation check. TagLogGroup
also has documented tag-enforcement limitations and is on the path to deprecation.
We therefore preserve the proven region restriction on the new grant, without
adding unproven request tags, resource tags, TagKeys or CalledVia to that grant.
All original canonical conditions remain on primary creation and modern tagging.

Security tradeoff for approval: the new grant can directly add/update arbitrary
tags on this ONE log group in af-south-1; it is not restricted to CloudFormation.
It does not grant direct log-group creation, deletion, untagging, log writes,
invocation or trigger creation. IAM cannot distinguish this grant's dependent
creation check from its standalone legacy tagging use without extra context
conditions. Do not claim creation's tag conditions constrain standalone retagging.

Sources: [Logs authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html),
[LogGroup ARN](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_LogGroup.html),
[TagLogGroup API](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_TagLogGroup.html),
[CreateLogGroup API](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html).

## Live troubleshooting evidence and limits

| Control / experiment | Result / request ID |
| --- | --- |
| Canonical v2 CloudFormation | Tagged creation denied; 4405018a-9e3c-4599-bd04-4f10a38f16cb |
| v3: remove CalledVia only from TagResource | Same denial; e9ed29b3-f2dc-48d0-befb-801908dce534 |
| v4: also remove request-tag conditions from TagResource | Same denial; 21ae5b40-b1d9-421a-a113-87728de892de |
| v5: also remove CalledVia from primary CreateLogGroup | Same denial; 0d0c4c54-315a-4bf6-80e3-02e70f34ec93 |
| v5: direct SDK tagged creation, outside CloudFormation | Same denial; 9aa1ba5a-1a43-4238-bd8d-a62f4b038348 |
| v6: v5 plus only scoped TagLogGroup | Direct success, HTTP 200, RetryAttempts=0; e641540c-a094-42b4-9411-b06bfeda7e8b |

Common denial: `CreateLogGroup with Tags. An additional permission "logs:TagResource" is required.`
V6's live inspection verified Project=FinTrust, Environment=dev, no streams/data.
Only the diagnostic group was deleted; v2 was restored and v6 retained nondefault.
Cleanup initially paused due to a local/server clock discrepancy; preflight
absence, HTTP 200, exact tags and server-time match resolved attribution. Both
the initial summary and completed cleanup evidence remain preserved.

This strongly isolates missing effective legacy tagging permission for the
tested direct path. It does not prove a global requirement for both tagging
actions, interpret the x-amzn-log-group-authz header, or guarantee canonical
conditions in a future CloudFormation provider request. The permanent fix is
prepared for a single reviewed retry, not already proven live.

## Validation and version capacity

Focused regressions: **157 passed, 0 failed, 0 skipped** in 7.14 seconds.
Coverage: Stage 5 ingest/authorization/legacy/permanent policies, Stage 4 messaging,
processing, ingest and package verification tests. Historical diagnostic tests
use the archived v2 baseline, preserving their original experiment semantics.
All six PowerShell command blocks were syntax parsed without executing them.
Frozen template and historical ZIP hashes match the recorded approvals.

Focused result and real simulation evidence: iam/evidence/stage5-permanent-validation.json.
The 18 independent custom-policy simulations cover all three action/resource
pairs, wrong group/account/region, missing CalledVia/tags, no deletion/untagging,
and the standalone retagging tradeoff. Expected results include primary create
and modern tagging denied without CalledVia or request tags; legacy tagging
allowed for only the exact suffixed group in-region. Access Analyzer target is
findings=[]. These checks do not simulate the complete service backend or prove
session/SCP context. [Simulator limits](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulateCustomPolicy.html).

Read-only snapshot: iam/evidence/stage5-permanent-version-baseline.json.
Versions are v1/v2/v4/v5/v6, v2 default. All five slots are occupied.
Propose deleting **only nondefault v4**, the oldest remaining condition diagnostic,
AFTER fresh verification that its live document equals both the archived v4 and
stage5-deployment-diagnostic2-policy.json. Preserve v2 as rollback, v5 as failing
direct control, v6 as successful direct evidence, and v1 unchanged. The archive
must be committed before deletion. No deletion occurred in this preparation.

## Exact future manual recovery commands — NOT executed here

Use PowerShell in C:\Users\Nompilo\Desktop\fintrust. These are a staged plan;
do not paste/run the whole document without the approvals indicated. No more
than one execution attempt is authorized by the proposed retry. Stop on any
mismatch/error. Do not automatically retry or loosen permissions.

### 1. Read-only preflight

```powershell
$stage5Aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$stage5Policy = 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
$stage5Group = '/aws/lambda/fintrust-ingest-dev'
$stage5GroupArn = 'arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev'
$stage5Version = '8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.'
$stage5Bucket = 'fintrust-reports-966467878406-af-south-1-dev'
$stage5Key = 'deployment/lambda/d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62/fintrust.zip'
$stage5ChangeSet = 'fintrust-ingest-stage5-permanent-review'

function Invoke-Stage5Aws {
    param([string[]]$Arguments, [string]$Profile = 'fintrust-inventory')
    $stage5Output = & $stage5Aws @Arguments --profile $Profile --region af-south-1 --no-cli-pager --output json
    if ($LASTEXITCODE -ne 0) { throw 'AWS command failed; stop and preserve the error.' }
    if ($stage5Output) { $stage5Output | ConvertFrom-Json }
}

Invoke-Stage5Aws -Arguments @('sts','get-caller-identity') -Profile fintrust-admin
Invoke-Stage5Aws -Arguments @('sts','get-caller-identity') -Profile fintrust-deployer-role
Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
Invoke-Stage5Aws -Arguments @('iam','list-attached-role-policies','--role-name','fintrust-deployer-role')
Invoke-Stage5Aws -Arguments @('cloudformation','describe-stacks','--stack-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('cloudformation','describe-stack-resources','--stack-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('cloudformation','describe-stack-events','--stack-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('logs','describe-log-groups','--log-group-name-prefix',$stage5Group)
Invoke-Stage5Aws -Arguments @('lambda','list-functions','--query',"Functions[?FunctionName=='fintrust-ingest-dev']")
Invoke-Stage5Aws -Arguments @('s3api','head-object','--bucket',$stage5Bucket,'--key',$stage5Key,'--version-id',$stage5Version)
Get-FileHash -LiteralPath build/stage5-ingest.json -Algorithm SHA256
Get-FileHash -LiteralPath build/ci-evidence/37342810131/fintrust-linux-verified/fintrust.zip -Algorithm SHA256
```

Require exact account/identities, v2 default and v4 nondefault, existing role
attachment, failed stack ROLLBACK_COMPLETE with expected absent resources,
exact physical log group absent, Lambda absent. Preserve preflight evidence.
Template SHA256 must be 01d8eae2ac57e7c4ae28c0e5c763f3d48f42d840d217a9164cea37c6c2d3720b.
ZIP SHA256 must be d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62.
HeadObject must identify the exact non-null version, ContentLength 21646562,
SSE aws:kms and key 598a4158-2cc6-4946-af24-512784a276c8. HeadObject/ETag is NOT
byte-level checksum proof; retain the prior operator download/hash evidence.
No package rebuild/re-upload or source comparison to the newer hardened release.

### 2. After policy-installation approval: free v4, create one permanent version

```powershell
$stage5Archived = Get-Content infrastructure/iam/evidence/stage5-permanent-version-baseline.json -Raw | ConvertFrom-Json
$stage5LiveV4 = Invoke-Stage5Aws -Arguments @('iam','get-policy-version','--policy-arn',$stage5Policy,'--version-id','v4')
if ($stage5LiveV4.PolicyVersion.IsDefaultVersion) { throw 'v4 is default; do not delete.' }
if (($stage5LiveV4.PolicyVersion.Document | ConvertTo-Json -Depth 100 -Compress) -cne ($stage5Archived.v4.PolicyVersion.Document | ConvertTo-Json -Depth 100 -Compress)) { throw 'v4 archive mismatch; stop.' }
$stage5V4Local = Get-Content infrastructure/iam/stage5-deployment-diagnostic2-policy.json -Raw | ConvertFrom-Json
if (($stage5LiveV4.PolicyVersion.Document | ConvertTo-Json -Depth 100 -Compress) -cne ($stage5V4Local | ConvertTo-Json -Depth 100 -Compress)) { throw 'v4 local document mismatch; stop.' }
Invoke-Stage5Aws -Arguments @('iam','delete-policy-version','--policy-arn',$stage5Policy,'--version-id','v4') -Profile fintrust-admin
Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
$stage5New = Invoke-Stage5Aws -Arguments @('iam','create-policy-version','--policy-arn',$stage5Policy,'--policy-document','file://infrastructure/iam/stage5-deployment-policy.json') -Profile fintrust-admin
$stage5PermanentId = $stage5New.PolicyVersion.VersionId
if (-not $stage5PermanentId -or $stage5New.PolicyVersion.IsDefaultVersion) { throw 'Unexpected new version; stop.' }
$stage5LiveNew = Invoke-Stage5Aws -Arguments @('iam','get-policy-version','--policy-arn',$stage5Policy,'--version-id',$stage5PermanentId)
$stage5Local = Get-Content infrastructure/iam/stage5-deployment-policy.json -Raw | ConvertFrom-Json
if (($stage5LiveNew.PolicyVersion.Document | ConvertTo-Json -Depth 100 -Compress) -cne ($stage5Local | ConvertTo-Json -Depth 100 -Compress)) { throw 'New version content mismatch; do not activate.' }
Invoke-Stage5Aws -Arguments @('iam','set-default-policy-version','--policy-arn',$stage5Policy,'--version-id',$stage5PermanentId) -Profile fintrust-admin
Invoke-Stage5Aws -Arguments @('iam','get-policy','--policy-arn',$stage5Policy)
Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
Invoke-Stage5Aws -Arguments @('iam','get-policy-version','--policy-arn',$stage5Policy,'--version-id',$stage5PermanentId)
```

Record the returned version ID, never assume v7. Verify it is the sole default,
v2/v5/v6 remain preserved nondefault, attachment unchanged, and JSON equals the
local permanent policy. Reconfirm admin identity before mutations. If propagation
is uncertain, stop; do not create additional versions or attempts.

### 3. After separate failed-stack deletion approval

Save stack events/resource list and ARN first. ROLLBACK_COMPLETE from a failed
CREATE cannot be updated into a fresh CREATE under the same name; delete its
stack record. This plan does not delete a retained log group blindly.

```powershell
Invoke-Stage5Aws -Arguments @('cloudformation','delete-stack','--stack-name','fintrust-ingest-dev') -Profile fintrust-admin
Invoke-Stage5Aws -Arguments @('cloudformation','wait','stack-delete-complete','--stack-name','fintrust-ingest-dev') -Profile fintrust-admin
& $stage5Aws cloudformation describe-stacks --stack-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
# Expected: ValidationError stating this exact stack does not exist.
# AccessDenied/session/network failures are UNKNOWN, not absence proof.
Invoke-Stage5Aws -Arguments @('logs','describe-log-groups','--log-group-name-prefix',$stage5Group)
Invoke-Stage5Aws -Arguments @('lambda','list-functions','--query',"Functions[?FunctionName=='fintrust-ingest-dev']")
```

Require exact group/Lambda absent. If a retained group appears, preserve tags,
retention, streams and ownership evidence and seek separate cleanup/import
approval; do not automatically delete it or rename the template. Preserve the
execution role and uploaded artifact. Never use ContinueUpdateRollback for this
failed CREATE. Do not delete any Stage 1-4 resource.

### 4. After change-set preparation approval

Refresh/verify MFA-backed deployer identity. Use the UNCHANGED frozen template,
not a new renderer output, and the historical artifact version.

```powershell
Invoke-Stage5Aws -Arguments @('sts','get-caller-identity') -Profile fintrust-deployer-role
Invoke-Stage5Aws -Arguments @('cloudformation','create-change-set',
    '--stack-name','fintrust-ingest-dev','--change-set-name',$stage5ChangeSet,
    '--change-set-type','CREATE','--template-body','file://build/stage5-ingest.json',
    '--parameters',"ParameterKey=CodeObjectVersion,ParameterValue=$stage5Version",
    '--resource-types','AWS::Lambda::Function','AWS::Lambda::EventInvokeConfig','AWS::Logs::LogGroup',
    '--tags','Key=Project,Value=FinTrust','Key=Environment,Value=dev',
    '--description','Stage 5 canonical v2 plus scoped TagLogGroup; historical package; disabled ingest') -Profile fintrust-deployer-role
Invoke-Stage5Aws -Arguments @('cloudformation','wait','change-set-create-complete','--stack-name','fintrust-ingest-dev','--change-set-name',$stage5ChangeSet) -Profile fintrust-deployer-role
$stage5Review = Invoke-Stage5Aws -Arguments @('cloudformation','describe-change-set','--stack-name','fintrust-ingest-dev','--change-set-name',$stage5ChangeSet) -Profile fintrust-deployer-role
$stage5Review | ConvertTo-Json -Depth 100
```

Require CREATE_COMPLETE / AVAILABLE, exactly three changes, all Add, and exact
logical/type pairs: IngestLogs/AWS::Logs::LogGroup,
IngestFunction/AWS::Lambda::Function, IngestAsync/AWS::Lambda::EventInvokeConfig.
CodeObjectVersion must equal the historical version above. No RoleARN, imports,
IAM capabilities, replacements, extra resources or trigger wiring.
Save the full review and screenshot; STOP for execution approval.

### 5. After execution approval: exactly one attempt, then read-only verification

```powershell
Invoke-Stage5Aws -Arguments @('cloudformation','execute-change-set','--stack-name','fintrust-ingest-dev','--change-set-name',$stage5ChangeSet) -Profile fintrust-deployer-role
Invoke-Stage5Aws -Arguments @('cloudformation','wait','stack-create-complete','--stack-name','fintrust-ingest-dev') -Profile fintrust-deployer-role
Invoke-Stage5Aws -Arguments @('cloudformation','describe-stacks','--stack-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('cloudformation','describe-stack-resources','--stack-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('cloudformation','describe-stack-events','--stack-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('logs','describe-log-groups','--log-group-name-prefix',$stage5Group)
Invoke-Stage5Aws -Arguments @('logs','list-tags-for-resource','--resource-arn',$stage5GroupArn)
Invoke-Stage5Aws -Arguments @('lambda','get-function-configuration','--function-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('lambda','get-function','--function-name','fintrust-ingest-dev','--query','Configuration.CodeSha256')
Invoke-Stage5Aws -Arguments @('lambda','get-function-concurrency','--function-name','fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('lambda','get-function-event-invoke-config','--function-name','fintrust-ingest-dev','--qualifier','$LATEST')
Invoke-Stage5Aws -Arguments @('lambda','list-tags','--resource','arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev')
Invoke-Stage5Aws -Arguments @('lambda','list-event-source-mappings','--function-name','fintrust-ingest-dev')
& $stage5Aws lambda get-policy --function-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
# Expected: ResourceNotFoundException for no function resource policy.
Invoke-Stage5Aws -Arguments @('s3api','get-bucket-notification-configuration','--bucket','fintrust-raw-966467878406-af-south-1-dev')
```

Require stack and all three resources CREATE_COMPLETE. Log group has FinTrust/dev
tags (CloudFormation system tags may additionally appear) and retentionInDays=14.
Lambda must be Active/Successful, python3.12, x86_64,
fintrust.ingest.lambda_handler, role arn:aws:iam::966467878406:role/fintrust-ingest-dev,
256 MB, 120 seconds, no VPC attachments, exact frozen environment variables,
ReservedConcurrentExecutions=0, matching SHA256 in base64, and no provisioned
concurrency. Async config is $LATEST, max retries=2, max age=21600, only failure
destination fintrust-ingest-failures-dev. EventSourceMappings must be empty;
no Lambda invocation policy or raw-bucket Lambda notification may target ingest.
Unknown/denied inspections are not verification. Do not invoke Lambda to test it.

### 6. Failure handling and canonical rollback

If execute/wait fails, do not execute again. Capture describe-stack-events,
describe-stack-resources, first CREATE_FAILED reason/request ID, current physical
state and policy default. Record partial successes; never infer absence from a
failed waiter. Stop for separate recovery approval. Restore v2 using admin on a
failed authorization retry AFTER any in-progress CloudFormation rollback finishes
(or under an explicit administrator recovery decision); changing permissions
mid-operation can interfere with cleanup. V2 restoration does not delete resources.

```powershell
Invoke-Stage5Aws -Arguments @('iam','set-default-policy-version','--policy-arn',$stage5Policy,'--version-id','v2') -Profile fintrust-admin
Invoke-Stage5Aws -Arguments @('iam','get-policy','--policy-arn',$stage5Policy)
Invoke-Stage5Aws -Arguments @('iam','get-policy-version','--policy-arn',$stage5Policy,'--version-id','v2')
Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
```

On complete verified success, leave the approved permanent version default and
retain v2 rollback; do NOT restore the broken v2 automatically. The deployer
policy lacks physical Lambda/EventInvokeConfig delete permissions by design;
partial creation can need controlled admin cleanup. Logs are Retain and can
collide on later CREATE; inspect before requesting deletion, preserve any data.
Keep concurrency 0 and triggers absent through any recovery. Retained logs can
incur storage charges if data exists; retained code versions and prior Stage 1-4
costs continue. This IAM-only preparation adds no usage or standing resource cost.

## Evidence, release separation and next step

Suggested future files under docs/EVIDENCE/02-iam: 37-stage5-v4-archived.json,
38-stage5-permanent-version-created.json, 39-stage5-permanent-default.json.
Under docs/EVIDENCE/08-lambda: 58-stage5-permanent-preflight.json,
59-stage5-failed-stack-deleted.json, 60-stage5-permanent-change-set-reviewed.json,
61-stage5-permanent-change-set-reviewed.png, 62-stage5-permanent-stack-events.json,
63-stage5-permanent-resources.json, 64-stage5-permanent-log-settings.json,
65-stage5-permanent-lambda-configuration.json, 66-stage5-permanent-trigger-checks.json.
Capture failure equivalents if the retry fails. Never overwrite historical files.

The successful direct diagnostic is archived with its cleanup in
`iam/evidence/stage5-permanent-validation.json`; original full evidence remains
under docs/EVIDENCE/08-lambda/52 through 57. The policy-version snapshot archives
v4 before a proposed future deletion. History and canonical conditions are
covered by tests/test_stage5_permanent.py plus the existing Stage 5 suites.

Next manual step: review/approve the exact permanent grant and its one-group
retagging tradeoff, then approve replacing only FinTrustStage5Deployment's default
via the version procedure above. No attachment or execution-role recreation is
needed. Do not install diagnostic v6. Failed-stack deletion, fresh change-set
creation and execution remain separate checkpoints.

Historical ZIP/version/template are frozen. Do not use verify_package's current
source-consistency gate to redefine the historical artifact: newer source has
separate duplicate/idempotency hardening. That later release needs its own Linux
build, checksum, S3 version, migration review, deployment and integration checks
after disabled Stage 5 infrastructure is verified. No SQL or runtime code changed.

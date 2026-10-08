# Stage 5 second temporary tagging-context diagnostic

Status: **SECOND DIAGNOSTIC PLAN READY for review only.** No AWS mutation is
approved or performed by this preparation. This plan is a single attempt using
the historical, pinned package, not a release of the current hardened source.

## Checkpoint and experiment

Operator evidence: experiment one activated temporary v3, removing only
`aws:CalledVia` from `TagIngestLogGroup`. It still failed with:
`CreateLogGroup with Tags. An additional permission "logs:TagResource" is required.`
Request ID: `e9ed29b3-f2dc-48d0-befb-801908dce534`.
This proves removing CalledVia alone was insufficient; it does not identify the
missing provider context conclusively. Canonical v2 has been restored.

Read-only confirmation on 2026-10-08 with `fintrust-inventory`:

- Account 966467878406; ARN `arn:aws:iam::966467878406:user/fintrust-inventory`.
- Live v2 is default and its complete document matches canonical locally.
- Live v3 is nondefault and matches the first diagnostic file locally.
- `fintrust-ingest-dev` is `ROLLBACK_COMPLETE`; only recorded stack resource is
  `IngestLogs`, physical `/aws/lambda/fintrust-ingest-dev`, `DELETE_SKIPPED`.
- Logs discovery returned `logGroups: []`; no physical group requires deletion
  under this observation. Recheck before any approved recovery.
- Existing S3 version exists, is 21,646,562 bytes, uses the existing KMS key
  `598a4158-2cc6-4946-af24-512784a276c8`, and has BucketKeyEnabled=true.

New file: `iam/stage5-deployment-diagnostic2-policy.json`.
The canonical file and experiment-one file are byte-for-byte unchanged.
Compared with v3, only the two equality keys `aws:RequestTag/Project` and
`aws:RequestTag/Environment` are removed. CalledVia remains absent. Treat the
request-tag prerequisite pair as one experimental factor; this cannot distinguish
which individual tag key is missing/wrong. Relative to v2, both CalledVia and
request tags are absent, so a direct v2-versus-experiment-two comparison alone
cannot isolate CalledVia. The observed v3 failure is the necessary control.

Exact diagnostic statement:

```json
{
  "Sid": "TagIngestLogGroup",
  "Effect": "Allow",
  "Action": [
    "logs:TagResource"
  ],
  "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "af-south-1"
    }
  }
}
```

All other grants are identical, including the CreateLogGroup request-tag and
CloudFormation controls. No wildcard Logs scope or extra action is added.
Temporarily, the deployer can directly add/update arbitrary tags on this one
log group in this region. Do not use that permission directly during the test.
Do not substitute resource-tag ownership conditions for request tags during
create-time dependent authorization: the resource may not exist yet.

AWS documents resource-level TagResource/request-tag support and the unsuffixed
ARN for tagging. This does not prove that CreateLogGroup's dependent TagResource
check receives the same context as a standalone TagResource call.
Sources: [Logs authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html),
[LogGroup ARN](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_LogGroup.html),
[condition-key availability](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html).

## Local and read-only validation

106 focused tests passed, zero failures/skips:

```powershell
& 'C:\Users\Nompilo\AppData\Local\Programs\Python\Python314\python.exe' -m pytest -q `
  tests/test_stage5_ingest.py tests/test_stage4_messaging.py tests/test_processing.py `
  tests/test_ingest.py tests/test_lambda_package.py `
  --basetemp "build/pytest-diagnostic2-$([guid]::NewGuid().ToString('N'))" `
  -o cache_dir=build/pytest-diagnostic2-cache
```

Six new cases check the exact complete diff, unchanged canonical control,
unchanged create controls, sole tagging action, size limit, exact ARN and region,
and excluded wrong-group/region/suffixed ARN. Scope predicate tests explicitly
check structure; they do not pretend to implement AWS's full authorization engine.
Actual read-only AWS SimulateCustomPolicy results on the full candidate, with
only the requested region supplied (no tags and no CalledVia):

| Case | Actual result |
| --- | --- |
| Exact group + af-south-1 + TagResource | allowed |
| Unrelated report group + af-south-1 | implicitDeny |
| Exact group + us-east-1 | implicitDeny |
| ARN with :* suffix | implicitDeny |
| Same group in another account | implicitDeny |
| UntagResource on exact group | implicitDeny |
| First diagnostic v3 + exact group/region but no request tags | implicitDeny |

Access Analyzer on the entire candidate: `{"findings": []}` (zero findings).
Simulator results do not prove effective live-role authorization, provider context,
SCPs, boundaries or session-policy behavior. See
[AWS simulator limits](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html).
Ignored local inputs/results:
`build/stage5-diagnostic2-sim-*.json`,
`build/stage5-diagnostic2-validation-results.json`,
`build/stage5-diagnostic2-analyzer-result.json`,
`build/stage5-diagnostic2-package-result.json`,
`build/stage5-diagnostic2-baseline.json`.

Exact read-only validation commands (already performed; optional reproduction):

```powershell
$stage5Aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
& $stage5Aws accessanalyzer validate-policy `
  --policy-document file://infrastructure/iam/stage5-deployment-diagnostic2-policy.json `
  --policy-type IDENTITY_POLICY --profile fintrust-inventory --region af-south-1 --no-cli-pager
foreach ($stage5Case in @('correct','other-group','wrong-region','suffix-arn','other-account','other-action','v3-no-tags')) {
  & $stage5Aws iam simulate-custom-policy `
    --cli-input-json "file://build/stage5-diagnostic2-sim-$stage5Case.json" `
    --profile fintrust-inventory --region af-south-1 --no-cli-pager
}
```

## Artifact and source boundary

ZIP: `build/ci-evidence/37342810131/fintrust-linux-verified/fintrust.zip`.
SHA256: `d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62`.
VersionId: `8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.`.
CRC/digests/size/manifest checks pass; matching historical green CI, five Linux
imports and native PostgreSQL/CA evidence remain valid for the archived source.
HeadObject confirms the exact version and encryption; ETag is not a SHA256 proof.
No remote decrypt/download was needed and no package or upload changed here.

The prior local hardening commit `1a0897b` changed application source: three new
modules and eight changed runtime files differ from the archived source.
**Current-source/package consistency remains BLOCKED** until a separately
reviewed new Linux build. This is a pre-existing release gate, not caused by this
policy experiment. No rebuild/re-upload is required for the controlled historical
IAM diagnostic itself. A release of current hardened code does require a new
verified package. Do not regenerate the Stage 5 template or update the runtime
role for this experiment. No invocation, activation, triggers or SQL migration.

Frozen existing template: `build/stage5-ingest.json`.
SHA256: `01d8eae2ac57e7c4ae28c0e5c763f3d48f42d840d217a9164cea37c6c2d3720b`.

## Manual recovery and experiment commands — NOT EXECUTED

The following blocks are instructions for separately approved manual actions,
not an executable script to run wholesale. Stop at each approval checkpoint.
Use the actual repository at C:\Users\Nompilo\Desktop\fintrust. All workload
operations remain in af-south-1. Never output STS credentials or MFA codes.
If any precondition fails after temporary activation, restore v2 using the final
restoration block before stopping; do not leave the diagnostic default active.

### 1. Recheck before approval

```powershell
Set-Location 'C:\Users\Nompilo\Desktop\fintrust'
$stage5Aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$stage5PolicyArn = 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
$stage5GroupArn = 'arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev'
& $stage5Aws sts get-caller-identity --profile fintrust-admin --region af-south-1 --no-cli-pager
& $stage5Aws iam list-policy-versions --policy-arn $stage5PolicyArn --profile fintrust-inventory --no-cli-pager
& $stage5Aws iam get-policy-version --policy-arn $stage5PolicyArn --version-id v2 --profile fintrust-inventory --no-cli-pager
& $stage5Aws cloudformation describe-stacks --stack-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation list-stack-resources --stack-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
Get-FileHash build/stage5-ingest.json -Algorithm SHA256
& $stage5Aws s3api head-object `
  --bucket fintrust-reports-966467878406-af-south-1-dev `
  --key deployment/lambda/d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62/fintrust.zip `
  --version-id 8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx. --expected-bucket-owner 966467878406 `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Require the approved admin identity in account 966467878406; v2 default and
matching canonical; failed stack with only the expected absent log resource;
unchanged template hash and pinned object. Three versions currently exist; IAM
has a five-version limit. Do not delete any version without separate approval.

### 2. Temporary managed version — approval required

Create nondefault first, inspect, then make default. Do not assume v4: use the
returned version ID. Preserve v2 and v3. No role reattachment is needed.

```powershell
$stage5NewVersionJson = & $stage5Aws iam create-policy-version --policy-arn $stage5PolicyArn `
  --policy-document file://infrastructure/iam/stage5-deployment-diagnostic2-policy.json `
  --no-set-as-default --profile fintrust-admin --no-cli-pager --output json
if ($LASTEXITCODE -ne 0) { throw 'Version creation failed; stop.' }
$stage5DiagnosticVersion = ($stage5NewVersionJson | ConvertFrom-Json).PolicyVersion.VersionId
& $stage5Aws iam get-policy-version --policy-arn $stage5PolicyArn --version-id $stage5DiagnosticVersion `
  --profile fintrust-inventory --no-cli-pager
```

Inspect the full returned JSON against the local candidate. Only after it matches:

```powershell
& $stage5Aws iam set-default-policy-version --policy-arn $stage5PolicyArn --version-id $stage5DiagnosticVersion `
  --profile fintrust-admin --no-cli-pager
& $stage5Aws iam get-policy --policy-arn $stage5PolicyArn --profile fintrust-inventory --no-cli-pager
& $stage5Aws iam list-policy-versions --policy-arn $stage5PolicyArn --profile fintrust-inventory --no-cli-pager
```

Require that returned ID is default, v2/v3 remain retained. Allow propagation and
obtain a fresh MFA-backed session using the existing session procedure;
get-caller-identity checks identity but does not guarantee a session refresh.
Console equivalent: IAM > Policies > FinTrustStage5Deployment > Edit JSON using
the experiment-two file > save new version; verify Policy versions and retain v2.

### 3. Failed-stack deletion — separate destructive-action approval required

Recheck stack state/resources and absence just before deletion. Capture failure
and resource evidence first. A ROLLBACK_COMPLETE failed CREATE cannot be retried
as a fresh CREATE with the same name until the old stack is deleted.

```powershell
& $stage5Aws cloudformation delete-stack --stack-name fintrust-ingest-dev `
  --profile fintrust-admin --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation wait stack-delete-complete --stack-name fintrust-ingest-dev `
  --profile fintrust-admin --region af-south-1
& $stage5Aws cloudformation describe-stacks --stack-name fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fintrust-ingest-dev `
  --query "logGroups[?logGroupName=='/aws/lambda/fintrust-ingest-dev']" `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Waiter must succeed; DescribeStacks should then return the explicit
stack-does-not-exist ValidationError (not AccessDenied or expired credentials).
Logs query must be `[]`. No log deletion is proposed because it is absent. If it
appears, stop and reconcile ownership, tags, retention and streams; any deletion
requires its own approval. Do not delete a newly discovered retained resource.

### 4. Fresh change set — separate approval required

Keep stack `fintrust-ingest-dev`; use distinct permitted name
`fintrust-ingest-stage5-diagnostic2-review` to identify this experiment's evidence.
Only parameter: CodeObjectVersion with the exact existing value below.
No capabilities, imports or service role.

```powershell
& $stage5Aws sts get-caller-identity --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation create-change-set `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-diagnostic2-review `
  --change-set-type CREATE --template-body file://build/stage5-ingest.json `
  --parameters ParameterKey=CodeObjectVersion,ParameterValue=8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx. `
  --resource-types AWS::Lambda::Function AWS::Lambda::EventInvokeConfig AWS::Logs::LogGroup `
  --tags Key=Project,Value=FinTrust Key=Environment,Value=dev `
  --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation wait change-set-create-complete `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-diagnostic2-review `
  --profile fintrust-deployer-role --region af-south-1
& $stage5Aws cloudformation describe-change-set `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-diagnostic2-review `
  --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation get-template `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-diagnostic2-review `
  --template-stage Original --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
```

Require CREATE_COMPLETE / AVAILABLE, exactly three Add entries, no others:

| Logical ID | Type |
| --- | --- |
| IngestAsync | AWS::Lambda::EventInvokeConfig |
| IngestFunction | AWS::Lambda::Function |
| IngestLogs | AWS::Logs::LogGroup |

Review the template too: Python3.12/x86_64, ingest handler, outside VPC, original
role and environment, pinned version, reserved concurrency 0, no triggers,
retained logs with 14-day retention. Do not run the local renderer against the
new source; source/package consistency would correctly fail. Stop for review
and explicit single-attempt execution approval.

### 5. One execution, outcome capture and mandatory restoration

Run only after all previous reviews and execution approval. The following block
restores v2 in finally, including a failed execution, failed waiter or evidence
capture error. Do not perform a second attempt. A waiter timeout is not a terminal
failure: inspect status with the administrator, stop and record it; never delete
an in-progress stack. Restoring permissions can affect an in-progress operation,
so use the approved administrator recovery route if it remains active.

```powershell
try {
  & $stage5Aws cloudformation execute-change-set `
    --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-diagnostic2-review `
    --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
  if ($LASTEXITCODE -ne 0) { throw 'Execution was rejected; no retry.' }
  & $stage5Aws cloudformation wait stack-create-complete --stack-name fintrust-ingest-dev `
    --profile fintrust-deployer-role --region af-south-1
  $stage5WaitExit = $LASTEXITCODE
  Write-Output "Stack waiter exit: $stage5WaitExit"
  & $stage5Aws cloudformation describe-stacks --stack-name fintrust-ingest-dev `
    --profile fintrust-inventory --region af-south-1 --no-cli-pager
  & $stage5Aws cloudformation describe-stack-events --stack-name fintrust-ingest-dev `
    --profile fintrust-inventory --region af-south-1 --no-cli-pager
  & $stage5Aws cloudformation describe-stack-events --stack-name fintrust-ingest-dev `
    --query "StackEvents[?ResourceStatus=='CREATE_FAILED']" `
    --profile fintrust-inventory --region af-south-1 --no-cli-pager
  & $stage5Aws cloudformation list-stack-resources --stack-name fintrust-ingest-dev `
    --profile fintrust-inventory --region af-south-1 --no-cli-pager
} finally {
  & $stage5Aws iam set-default-policy-version --policy-arn $stage5PolicyArn --version-id v2 `
    --profile fintrust-admin --no-cli-pager
  if ($LASTEXITCODE -ne 0) { throw 'RESTORATION FAILED: use administrator recovery; do not retry.' }
  & $stage5Aws iam get-policy --policy-arn $stage5PolicyArn --profile fintrust-inventory --no-cli-pager
  & $stage5Aws iam list-policy-versions --policy-arn $stage5PolicyArn --profile fintrust-inventory --no-cli-pager
  & $stage5Aws iam get-policy-version --policy-arn $stage5PolicyArn --version-id v2 `
    --profile fintrust-inventory --no-cli-pager
}
```

Confirm DefaultVersionId=v2 and v2 IsDefaultVersion=true. For emergency restoration
at an earlier checkpoint, run the same set-default/get-policy/list-versions/v2
get-policy commands directly. Keep the diagnostic version nondefault as evidence;
do not delete any policy version here. Administrator login should be usable for
the full experiment; never start without a working restoration identity.

After restoration, inspect log-group existence, tags and retention; TagResource
is isolated only if log creation actually succeeded and FinTrust/dev tags are
present. If no physical group remains, use creation events and available provider
evidence, explicitly recording limits rather than claiming current tags.

```powershell
& $stage5Aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
# Only if the exact physical group exists:
& $stage5Aws logs list-tags-for-resource --resource-arn $stage5GroupArn `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
# Only if IngestFunction exists:
& $stage5Aws lambda get-function-configuration --function-name fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws lambda get-function-concurrency --function-name fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws lambda get-function-event-invoke-config --function-name fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Require ReservedConcurrentExecutions=0, historical CodeSha256
`1kXYlJ7lsSiytcTBVY3WGhpcD9PN6s5gNjsZ9w0WfWI=`, no trigger wiring,
expected role/environment and original failure destination. Do not invoke it.

## Interpretation and permanent-policy review

**Outcome A: IngestLogs succeeds.** With v3 previously denied, and only the
request-tag pair changed from v3, this is strong controlled evidence that those
conditions were incompatible with the provider-side dependent authorization.
A separate later Lambda failure does not erase successful log creation. This
cannot reveal the exact absent/wrong tag key, prove CalledVia compatibility,
exclude every propagation/effective-policy confounder, or prove the full Lambda
runtime. Record the exact version/session/timestamps and unchanged controls.
If log creation succeeds but expected tags cannot be evidenced, record partial
isolation and investigate before permanent approval.

Do not make the diagnostic default permanent automatically. The smallest proposed
permanent replacement, subject to a new review, is the same exact-ARN/regional
TagResource-only statement shown above, while retaining both ownership request
tags and CloudFormation mediation on CreateLogGroup and all other statements.
The tradeoff is direct arbitrary retagging of this one named group by this role;
verify actual template tags and protect ownership tags through a separately
validated mechanism if required. No generic Logs access or extra tagging action.
Do not reintroduce CalledVia solely on the basis of this test: it remained absent
in both diagnostic experiments and has not been proven compatible.

**Outcome B: same TagResource denial.** Request-tag removal was insufficient.
Restore v2 and stop broadening IAM. Investigate the actual dependent-resource
and authorization evaluation, provider behavior, effective role attachments,
SCPs, boundary, session policy and explicit denies. Simulator allowance is not
proof of live authorization. No wildcard workaround or additional tagging action.

**Other outcomes.** A failure before IngestLogs is evaluated is inconclusive;
a different failure after its successful creation is a separate issue. Stop and
report the exact first failure. No guesses, retries, package change or unrelated
permissions. Restoration only restores policy; it does not undo created resources.

## Evidence filenames and capture

Use existing docs/EVIDENCE folders; do not replace earlier screenshots.

| Proposed file | Contents |
| --- | --- |
| 08-lambda/20-stage5-diagnostic2-policy-validation.json | Exact diff, canonical/template hashes and focused-test result |
| 08-lambda/21-stage5-diagnostic2-iam-simulations.json | Actual simulation inputs and all seven results |
| 08-lambda/22-stage5-diagnostic2-access-analyzer.json | Full findings[] result |
| 02-iam/27-stage5-diagnostic2-version-default.png | Returned temporary version default, v2/v3 retained |
| 08-lambda/23-stage5-diagnostic2-stack-deleted.png | Successful deletion waiter and explicit absent-stack result |
| 08-lambda/24-stage5-diagnostic2-log-group-absent.json | Exact-group discovery [] before retry |
| 08-lambda/25-stage5-diagnostic2-change-set-reviewed.png | Three expected Add entries, CREATE_COMPLETE/AVAILABLE |
| 08-lambda/26-stage5-diagnostic2-stack-result.json | Exact status, waiter exit, start/end time and stack ID |
| 08-lambda/27-stage5-diagnostic2-stack-events.json | Full events, including log status, reasons and request IDs |
| 08-lambda/28-stage5-diagnostic2-create-failed.json | Filtered failure events, or [] on success |
| 08-lambda/29-stage5-diagnostic2-stack-resources.json | Physical IDs and final statuses |
| 08-lambda/30-stage5-diagnostic2-log-tags-retention.json | Tags/retention if present; explicit absence otherwise |
| 02-iam/28-stage5-diagnostic2-v2-restored.png | v2 default restored after the attempt |

Validation evidence exists locally under ignored build/ paths; live-experiment
filenames are proposals, not evidence of executed work. Capture each displayed
result at its checkpoint or save JSON using Set-Content -Encoding utf8; never
capture credentials/MFA. Keep existing ZIP manifest/CI/version evidence alongside
these records. If capture is interrupted, restore v2 first and retain the error.

## Resources, cost and recovery after the attempt

No new database, CMK, bucket, NAT, endpoint, IAM role or provisioned concurrency.
Success may leave an unwired standard Lambda, async configuration and retained
14-day log group. No execution is authorized; standard Lambda request/duration
charges require usage, and no provisioned capacity is configured. Log ingestion
and retained bytes can incur charges if present; do not assert that rollback
means zero remaining storage. Existing RDS, CMK and S3 costs continue unchanged.
[Lambda pricing](https://aws.amazon.com/lambda/pricing/).

Failure may leave retained logs or partial function resources. Save physical IDs,
status and data/evidence; stop for separate administrator cleanup approval.
Do not automatically delete a successful Lambda, retained group or diagnostic
policy version. Neither restoration nor failed-stack deletion grants permission
to alter Stage 1-4 resources. If restoration fails, the plan requires approved
administrator recovery before further work.

SECOND DIAGNOSTIC PLAN READY: exact diff, local tests, seven read-only simulations,
zero Analyzer findings, pinned historical artifact and explicit restoration are
prepared. The live cause remains unproven; current-source release remains blocked.
No IAM version, stack deletion, change set, deployment, rebuild/upload, activation,
trigger wiring, RDS/SQS/DynamoDB change or push occurred.

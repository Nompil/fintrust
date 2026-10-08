# Stage 5 temporary CalledVia diagnostic plan

Decision: DIAGNOSTIC PLAN READY for review, not authorized to run.
The canonical stage5-deployment-policy.json is unchanged. The separately named
stage5-deployment-diagnostic-policy.json is a temporary experiment, not a proven
permanent fix. Do not attach, activate or execute it without explicit approval.

## One variable and security effect

Only TagIngestLogGroup.Condition.ForAnyValue:StringEquals is removed in the
candidate. Its only key was aws:CalledVia=cloudformation.amazonaws.com.
Every other policy statement, action, resource and condition is identical.
This is the best first experiment because request-tag conditions are documented
for TagResource, whereas CalledVia availability depends on the service request
chain. The candidate retains exact account/log-group scope, Cape Town and both
request tags. It does temporarily permit direct tagging of that one named group
by the deployer with FinTrust/dev request tags; create and all other mutations
still require CloudFormation. Do not use that direct permission during the test.
An administrator can restore v2 without deleting any resources.

Sources: [Logs action/condition mapping](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html),
[IAM CalledVia availability](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-calledvia),
[Log-group ARN semantics](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_LogGroup.html).

Before (live v2 and canonical):

```json
{
  "Sid": "TagIngestLogGroup",
  "Effect": "Allow",
  "Action": ["logs:TagResource"],
  "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "af-south-1",
      "aws:RequestTag/Project": "FinTrust",
      "aws:RequestTag/Environment": "dev"
    },
    "ForAnyValue:StringEquals": {
      "aws:CalledVia": ["cloudformation.amazonaws.com"]
    }
  }
}
```

Temporary diagnostic statement:

```json
{
  "Sid": "TagIngestLogGroup",
  "Effect": "Allow",
  "Action": ["logs:TagResource"],
  "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "af-south-1",
      "aws:RequestTag/Project": "FinTrust",
      "aws:RequestTag/Environment": "dev"
    }
  }
}
```

## Validation already performed, without mutation

99 focused tests passed, zero failures/skips, across Stage 5, Stage 4, processing,
ingest and package tests. Two added regression checks compare the complete
candidate to a deep copy of canonical with only that condition removed, enforce
the exact action/ARN/tags and policy-size limit, and preserve the control policy.
Access Analyzer returned zero findings for the complete candidate.

Seven actual read-only SimulateCustomPolicy cases on isolated tagging statements:

| Case | Result |
|---|---|
| Canonical v2, required tags/region but no CalledVia | implicitDeny |
| Candidate, required tags/region but no CalledVia | allowed |
| Candidate, required tags/region and CalledVia | allowed |
| Candidate, request tags absent | implicitDeny |
| Candidate, Project=Other | implicitDeny |
| Candidate, region=us-east-1 | implicitDeny |
| Candidate, unrelated log-group ARN | implicitDeny |

Inputs/results are retained in ignored build/stage5-diagnostic-sim-*.json and
build/stage5-diagnostic-simulation-results.json. These show policy behavior under
supplied contexts, not the real provider's internal authorization context.

Inventory confirmed account 966467878406, v2 default with v1/v2 retained. No
new policy version was created. Prior read-only evidence found the failed stack
ROLLBACK_COMPLETE and the physical group absent. Recheck these immediately
before any approved mutation; a newly appeared resource changes the plan.

## Manual experiment sequence — approval required

All following commands are instructions only; none were run during preparation.
Use PowerShell from C:\Users\Nompilo\Desktop\fintrust. Do not change other
policies, role attachments, execution role, template, package version, concurrency
or triggers. Keep the approved template byte-for-byte unchanged for the retry.

```powershell
Set-Location 'C:\Users\Nompilo\Desktop\fintrust'
$aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$policyArn = 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
& $aws sts get-caller-identity --profile fintrust-admin --region af-south-1 --no-cli-pager
& $aws iam list-policy-versions --policy-arn $policyArn --profile fintrust-inventory --no-cli-pager
& $aws iam get-policy-version --policy-arn $policyArn --version-id v2 --profile fintrust-inventory --no-cli-pager
& $aws cloudformation describe-stacks --stack-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $aws cloudformation list-stack-resources --stack-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Require approved administrator identity in the exact account, v2 still default,
only the expected failed log resource recorded, and no matching physical group.
Do not proceed if anything differs. Preserve v2 JSON and failure/resource evidence.
There were two policy versions at preparation time; do not delete versions to
make space blindly if that changes.

Create a new nondefault version first, inspect it, then activate only after its
JSON matches the local diagnostic candidate:

```powershell
& $aws iam create-policy-version --policy-arn $policyArn `
  --policy-document file://infrastructure/iam/stage5-deployment-diagnostic-policy.json `
  --no-set-as-default --profile fintrust-admin --no-cli-pager
$diagnosticVersion = 'REPLACE_WITH_RETURNED_VERSION_ID'
& $aws iam get-policy-version --policy-arn $policyArn --version-id $diagnosticVersion `
  --profile fintrust-inventory --no-cli-pager
& $aws iam set-default-policy-version --policy-arn $policyArn --version-id $diagnosticVersion `
  --profile fintrust-admin --no-cli-pager
& $aws iam get-policy --policy-arn $policyArn --profile fintrust-inventory --no-cli-pager
```

v3 is expected from current history, but always use the returned ID. Keep v2.
Console alternative: IAM > Policies > FinTrustStage5Deployment > Edit > JSON;
replace with the diagnostic file and save a new version as default, retaining
v2 under Policy versions. The CLI route above allows inspection before activation.
No role reattachment is needed. Wait for propagation and obtain a fresh MFA-backed
deployer session using the existing session procedure. Verify its account/role
with get-caller-identity; do not assume that call always forces a new session.

With separate failed-stack deletion approval:

```powershell
& $aws cloudformation delete-stack --stack-name fintrust-ingest-dev `
  --profile fintrust-admin --region af-south-1 --no-cli-pager
& $aws cloudformation wait stack-delete-complete --stack-name fintrust-ingest-dev `
  --profile fintrust-admin --region af-south-1
& $aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

The failed CREATE stack must be removed before same-name fresh CREATE. No physical
log-group deletion is currently required. If a group exists on recheck, stop for
ownership/retention/tags/stream reconciliation and separate deletion approval.
Do not alter Stage 1-4 resources, runtime role or package object.

Verify the existing object/version metadata using inventory (head-object), and
retain the previous administrator checksum evidence. Inventory cannot decrypt
and rehash its bytes; do not broaden its permissions. No upload is part of this
experiment. Exact version is 8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.

```powershell
& $aws s3api head-object `
  --bucket fintrust-reports-966467878406-af-south-1-dev `
  --key deployment/lambda/d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62/fintrust.zip `
  --version-id 8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx. --expected-bucket-owner 966467878406 `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $aws sts get-caller-identity --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $aws cloudformation create-change-set `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-review `
  --change-set-type CREATE --template-body file://build/stage5-ingest.json `
  --parameters ParameterKey=CodeObjectVersion,ParameterValue=8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx. `
  --resource-types AWS::Lambda::Function AWS::Lambda::EventInvokeConfig AWS::Logs::LogGroup `
  --tags Key=Project,Value=FinTrust Key=Environment,Value=dev `
  --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $aws cloudformation wait change-set-create-complete `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-review `
  --profile fintrust-deployer-role --region af-south-1
& $aws cloudformation describe-change-set `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-review `
  --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
```

Require CREATE_COMPLETE/AVAILABLE and exactly the same three Add actions:
IngestLogs, IngestFunction and IngestAsync. No IAM capabilities, service role,
imports or extra resources. Inspect GetTemplate for ReservedConcurrentExecutions=0
and unchanged environment/destinations. Stop for explicit diagnostic execution
approval before running the following:

```powershell
& $aws cloudformation execute-change-set `
  --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-review `
  --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $aws cloudformation wait stack-create-complete --stack-name fintrust-ingest-dev `
  --profile fintrust-deployer-role --region af-south-1
& $aws cloudformation describe-stack-events --stack-name fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $aws cloudformation list-stack-resources --stack-name fintrust-ingest-dev `
  --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

A failed waiter is not permission to retry. Capture the first failed event and
IngestLogs status before any cleanup. Do not invoke Lambda or add sample objects.
If the function is created, inspect GetFunctionConfiguration, GetFunctionConcurrency
and GetFunctionEventInvokeConfig using inventory; require CodeSha256 matching
1kXYlJ7lsSiytcTBVY3WGhpcD9PN6s5gNjsZ9w0WfWI= and reserved concurrency zero.
Also inspect logs tags and retention after any IngestLogs success. No log events
need to be read for the authorization result.

## Interpretation and restoration

- IngestLogs CREATE_COMPLETE, whether or not the rest of the stack succeeds:
  strong controlled evidence that the v2 CalledVia restriction blocked this
  provider-side tagging check. Preserve actual FinTrust/dev tags and retention
  evidence. This does not reveal the internal missing/wrong CalledVia value,
  prove all Lambda permissions, or justify a permanent policy change automatically.
- Same tagged-creation denial after confirming the candidate is default and
  propagated: removing CalledVia alone was insufficient. Investigate dependent
  request-tag context and other effective controls; it does not conclusively prove
  the request tags were missing or exclude a dependent-resource discrepancy.
- A different failure after log creation is a separate blocker: stop and report it.
  Do not make another IAM edit in this experiment.
- Failure before IngestLogs is reached is inconclusive for this hypothesis.

Record and restore v2 after this single attempt for any outcome; do not leave
the temporary condition relaxation active while awaiting a permanent decision:

```powershell
& $aws iam set-default-policy-version --policy-arn $policyArn --version-id v2 `
  --profile fintrust-admin --no-cli-pager
& $aws iam get-policy --policy-arn $policyArn --profile fintrust-inventory --no-cli-pager
& $aws iam get-policy-version --policy-arn $policyArn --version-id v2 `
  --profile fintrust-inventory --no-cli-pager
```

Console restoration: IAM > Policies > FinTrustStage5Deployment > Policy versions
> v2 > Set as default. This restores permissions, not the previous infrastructure
state. Keep diagnostic version nondefault for evidence; deleting it is a separate
administrator decision. Do not delete v2 or revert to v1. If policy restoration
fails, stop and use the approved administrator recovery route; do not deploy again.

A successful attempt may leave an unwired Lambda, async configuration and a
14-day retained log group. Keep concurrency zero. A failed attempt may leave
retained logs or partial Lambda resources and can need administrator cleanup due
to absent deployer delete grants. Do not delete them automatically. Record physical
IDs and preserve data/evidence before separately approved cleanup. Restoring v2
can affect later stack operations, so use the administrator for approved recovery.

## Evidence and cost boundary

Under docs/EVIDENCE/08-lambda, proposed names:
- 10-stage5-diagnostic-v2-baseline.json
- 11-stage5-diagnostic-policy-diff.txt
- 12-stage5-diagnostic-version-default.png
- 13-stage5-diagnostic-change-set-reviewed.png
- 14-stage5-diagnostic-stack-events.json
- 15-stage5-diagnostic-log-group-tags-retention.png
- 16-stage5-diagnostic-result.txt
- 17-stage5-v2-default-restored.png

Keep package manifest/CI evidence and exact object VersionId/checksum evidence
alongside the result. Do not capture STS credentials or MFA codes. If log creation
fails, replace the tags/retention screenshot with the exact absent-group result.
Record the actual diagnostic version ID, approved template hash, request IDs,
start/end time and before/after policy IDs; explain partial success explicitly.

Offline package consistency passed again for the retained Linux-verified digest.
No application, template or dependency change occurred; no rebuild or re-upload.
The experiment creates no new CMK, bucket, database, endpoint or IAM role. Lambda
has no provisioned concurrency and remains unwired with zero reserved concurrency.
Stored logs have usage/storage costs even after rollback; the function/config
may remain after success but introduces no provisioned-capacity standing charge.
No function invocation is authorized. Existing RDS, CMK and package storage costs
continue. Cleanup of any retained resource remains approval-gated.

DIAGNOSTIC PLAN READY: one policy condition changes, exact scope and request tags
are preserved, validation passed, and v2 restoration is explicit. This does not
mean the root cause is proven or AWS mutation is approved. No IAM update, deletion,
change set, deployment, activation, trigger wiring, upload or push occurred.


## Experiment-one live outcome and second proposal (2026-10-08)

Operator evidence confirms temporary v3 still failed with the same tagged
CreateLogGroup/TagResource denial, request ID
`e9ed29b3-f2dc-48d0-befb-801908dce534`. Removing CalledVia alone was insufficient.
Read-only inventory reconfirms v2 restored/default, v3 nondefault, both matching
their local policy documents. The failed stack is ROLLBACK_COMPLETE and the
physical group is absent despite DELETE_SKIPPED.

[Experiment two](STAGE5_DIAGNOSTIC2.md) preserves that v3 control and removes only
the two request-tag prerequisites in a separate temporary file. 106 focused
tests, seven read-only IAM simulations and zero Access Analyzer findings passed.
No canonical-policy edit or AWS mutation occurred. Follow the second plan rather
than repeating experiment one. Historical package integrity still passes, but
current hardened source differs; a current-source release requires a separate
Linux build approval. The experiment only tests the pinned historical package.


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

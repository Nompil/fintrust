# Stage 5 targeted TagLogGroup diagnostic proposal

Status: **TAGLOGGROUP DIAGNOSTIC READY** — prepared only; live execution requires
separate approval. No AWS mutation occurred in this preparation.

## Evidence and justification

Diagnostic three and the direct v5 test both failed. The direct test was a
boto3 SDK call using credentials exported in memory from the verified AWS CLI
MFA-backed role session, not a direct AWS CLI Logs call. Its RequestId is
9aa1ba5a-1a43-4238-bd8d-a62f4b038348, and RetryAttempts=0. No group exists; v2 is
restored default. The failed CloudFormation stack is left alone.

The current AWS API-to-IAM mapping lists CreateLogGroup, TagLogGroup and
TagResource for CreateLogGroup. The action table associates TagLogGroup with
log-group resource scope and lists aws:RequestTag/${TagKey},
aws:ResourceTag/${TagKey} and aws:TagKeys. This mapping does not prove that all
three grants are mandatory: the CreateLogGroup API explicitly documents either
TagResource or TagLogGroup as sufficient for tagging during creation.
[Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html),
[CreateLogGroup API](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html).

TagLogGroup remains available but AWS recommends TagResource and describes
TagLogGroup as on the path to deprecation. Its API page also warns about limits
on enforcing selected tags through aws:Resource/key-name and aws:TagKeys. That
warning and the action table are not treated as a guarantee that every listed
condition is supplied/enforced in the dependent creation check.
[TagLogGroup API](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_TagLogGroup.html).

AWS documents the suffixed log-group ARN for most actions; only TagResource,
UntagResource and ListTagsForResource have the documented unsuffixed exception.
Therefore the proposed TagLogGroup grant uses the existing exact group plus :*,
while the unchanged TagResource grant keeps the unsuffixed ARN.
[LogGroup ARN forms](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_LogGroup.html).

Historical primary evidence: the published AWS CloudFormation Logs provider
schema lists TagLogGroup in its create-handler permissions. This is older than
the live regional schema previously inspected, which lists TagResource. It
supports testing the legacy path, not a claim that this account requires it.
No current first-party evidence found establishes that an account/region must
have both permissions or that adding legacy permission will resolve this case.
Third-party anecdotes are not relied upon as authorization proof.
[Published AWS provider schema](https://raw.githubusercontent.com/aws-cloudformation/aws-cloudformation-resource-providers-logs/master/aws-logs-loggroup/aws-logs-loggroup.json).

The observed response header x-amzn-log-group-authz: outdated remains an
uninterpreted service observation, not proof of old SDKs or a legacy mode.
The new action is a justified, untested alternative permission path, not a
proven root cause. No existing grant or condition is loosened in this candidate.

## Exact candidate

File: iam/stage5-deployment-tagloggroup-diagnostic-policy.json.
The full policy is byte-equivalent as parsed JSON to diagnostic v5 plus one
appended statement:

```json
{
  "Sid": "LegacyTagIngestLogGroup",
  "Effect": "Allow",
  "Action": ["logs:TagLogGroup"],
  "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev:*",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "af-south-1"
    }
  }
}
```

No Resource="*", new queue/bucket/log group, retention/delete/untag action,
CalledVia removal or change to the existing creation request tags. Account,
region and log-group name are exact. The :* suffix is the documented ARN form,
not a wildcard log-group name. Request tags are supported in the action table,
but intentionally not imposed on the new dependent legacy grant: the baseline
creation permission already requires Project=FinTrust and Environment=dev, and
this experiment isolates action availability without another context hypothesis.
Resource tags are not assumed to exist before creation. The temporary grant
can directly retag the one named group while active; it is not automatically
approved as a permanent control.

## Policy-version plan (not executed)

Read-only inventory confirms five versions: v1-v5, v2 default. Preserve canonical
v2 and the v5 direct-test control. Proposed deletion: **v3 only**, the oldest
nondefault condition diagnostic. Its live content equals the committed
stage5-deployment-diagnostic-policy.json. v1/v4/v5 are left in AWS.

The exact v2/v3/v5 documents, creation dates, default flags, policy ARN and local
hashes are archived in iam/evidence/stage5-tagloggroup-version-baseline.json.
Commit that archive, candidate, validation evidence and this plan before any
approved deletion. Deleting a nondefault version removes a rollback copy; it
has no current effective-permission change. Require a fresh match/nondefault
check immediately before the future delete. Do not delete v2, automatically
select an arbitrary version, or delete more than v3.

Then create one replacement candidate **nondefault**, capture its returned ID
(do not assume v6), and temporarily activate it only within the restoration
block below. If creation fails, v2 remains default and the v3 archive remains
recoverable locally. Version IDs may be nonsequential and deleted IDs are not
promised to be reused. Restoration uses v2, not recreation of v3.
[AWS managed-policy versioning](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html).

## Validation completed

Focused suite: 135 passed, zero failures/skips. Regression tests require the
complete v5 policy plus exactly the new grant, canonical/v5 byte hashes,
nondefault archived v3, unchanged modern tagging, and recorded real AWS
simulations bound to the candidate digest. The existing canonical policy,
previous diagnostics, Lambda/runtime code, template, SQL and ZIP are unchanged.

Access Analyzer: zero findings for the complete new candidate, using
fintrust-inventory. Eleven read-only SimulateCustomPolicy cases:

| Case | Result |
| --- | --- |
| v5, TagLogGroup exact suffixed ARN | implicitDeny |
| candidate, TagLogGroup exact suffixed ARN / region | allowed |
| candidate, different group | implicitDeny |
| candidate, different region | implicitDeny |
| candidate, different account | implicitDeny |
| candidate, unsuffixed TagLogGroup ARN | implicitDeny |
| candidate, UntagLogGroup | implicitDeny |
| candidate, DeleteLogGroup | implicitDeny |
| candidate, CreateLogGroup + required request tags | allowed |
| candidate, modern TagResource exact unsuffixed ARN | allowed |
| candidate, CreateLogGroup with wrong Project tag | implicitDeny |

Results: iam/evidence/stage5-tagloggroup-validation.json. Raw inputs/results:
ignored build/stage5-tagloggroup-review/. Simulations evaluate independent
permissions, not the service's full dependent tagging checks. No live success
is inferred. Access Analyzer does not guarantee effective runtime authorization.

## Exact future one-shot procedure — DO NOT RUN WITHOUT SEPARATE APPROVAL

Use PowerShell from C:\Users\Nompilo\Desktop\fintrust. This is a prepared
mutation plan, not permission to execute it now. MFA/admin sessions must be
valid. Stop on identity, policy-content, absence, version-state or data mismatch.
The helper uses the same direct SDK/CLI-session method as the previous direct
control, with total_max_attempts=1, so only the permission changes.

First inspect identity/version/group and freshly export v3 for comparison with
the committed archive. Do not proceed unless v2 is default, v3/v5 are nondefault,
v3 matches its archive, the exact group is absent, and identity matches account
966467878406 plus assumed-role/fintrust-deployer-role/.

```powershell
$stage5Aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$stage5Python = 'C:\Users\Nompilo\AppData\Local\Programs\Python\Python314\python.exe'
$stage5Policy = 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
$stage5Group = '/aws/lambda/fintrust-ingest-dev'
$stage5GroupArn = 'arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev'
$stage5Stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$stage5ProbeEvidence = "docs/EVIDENCE/08-lambda/52-stage5-tagloggroup-direct-result-$stage5Stamp.json"

function Invoke-Stage5Aws {
    param([string[]]$Arguments, [string]$Profile = 'fintrust-inventory')
    $stage5PriorAttempts = $env:AWS_MAX_ATTEMPTS
    try {
        $env:AWS_MAX_ATTEMPTS = '1'
        $stage5Response = & $stage5Aws @Arguments --profile $Profile --region af-south-1 --no-cli-pager --output json --cli-connect-timeout 10 --cli-read-timeout 10
        $stage5ExitCode = $LASTEXITCODE
    }
    finally { $env:AWS_MAX_ATTEMPTS = $stage5PriorAttempts }
    if ($stage5ExitCode -ne 0) { throw 'AWS command failed; stop without retrying.' }
    if ($stage5Response) { $stage5Response | ConvertFrom-Json }
}

Invoke-Stage5Aws -Arguments @('sts','get-caller-identity') -Profile fintrust-deployer-role
Invoke-Stage5Aws -Arguments @('sts','get-caller-identity') -Profile fintrust-admin
Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
Invoke-Stage5Aws -Arguments @('iam','get-policy-version','--policy-arn',$stage5Policy,'--version-id','v3')
Invoke-Stage5Aws -Arguments @('logs','describe-log-groups','--log-group-name-prefix',$stage5Group)

# After the checks and separate approval, delete only archived nondefault v3.
Invoke-Stage5Aws -Arguments @('iam','delete-policy-version','--policy-arn',$stage5Policy,'--version-id','v3') -Profile fintrust-admin
$stage5NewVersion = Invoke-Stage5Aws -Arguments @('iam','create-policy-version','--policy-arn',$stage5Policy,'--policy-document','file://infrastructure/iam/stage5-deployment-tagloggroup-diagnostic-policy.json') -Profile fintrust-admin
$stage5NewId = $stage5NewVersion.PolicyVersion.VersionId
if (-not $stage5NewId -or $stage5NewVersion.PolicyVersion.IsDefaultVersion) { throw 'Unexpected new version state.' }
$stage5NewVersion | ConvertTo-Json -Depth 100 | Set-Content "docs/EVIDENCE/02-iam/34-stage5-tagloggroup-version-$stage5Stamp.json" -Encoding UTF8

try {
    Invoke-Stage5Aws -Arguments @('iam','set-default-policy-version','--policy-arn',$stage5Policy,'--version-id',$stage5NewId) -Profile fintrust-admin
    $stage5Active = Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
    if (-not ($stage5Active.Versions | Where-Object { $_.VersionId -eq $stage5NewId -and $_.IsDefaultVersion })) { throw 'Temporary activation not confirmed.' }
    if ($stage5Active.Versions | Where-Object { $_.VersionId -eq 'v2' -and $_.IsDefaultVersion }) { throw 'v2 still default.' }
    $stage5Active | ConvertTo-Json -Depth 100 | Set-Content "docs/EVIDENCE/02-iam/35-stage5-tagloggroup-default-$stage5Stamp.json" -Encoding UTF8
    Start-Sleep -Seconds 10

    # Exactly one direct CreateLogGroup request; no CloudFormation or automatic retry.
    & $stage5Python tools/stage5_tagloggroup_probe.py --approved-direct-create --expected-policy-version $stage5NewId --evidence $stage5ProbeEvidence
    if ($LASTEXITCODE -ne 0) { throw 'Probe preflight failed; do not rerun.' }
}
finally {
    try {
        # Only clean a group attributable to the one attempt, after inspecting it.
        if (Test-Path -LiteralPath $stage5ProbeEvidence) {
            $stage5Result = Get-Content -LiteralPath $stage5ProbeEvidence -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($stage5Result.creation_attempts -eq 1) {
                $stage5Groups = Invoke-Stage5Aws -Arguments @('logs','describe-log-groups','--log-group-name-prefix',$stage5Group)
                $stage5Exact = @($stage5Groups.logGroups | Where-Object { $_.logGroupName -eq $stage5Group })
                if ($stage5Exact.Count -eq 1) {
                    $stage5AttemptStart = [DateTimeOffset]::Parse($stage5Result.started_at_utc).ToUnixTimeMilliseconds()
                    if ($stage5Exact[0].creationTime -lt $stage5AttemptStart -or (-not $stage5Result.success -and -not $stage5Result.outcome_unknown)) { throw 'Group is not attributable to this attempt; restore v2 and request manual review.' }
                    $stage5Tags = Invoke-Stage5Aws -Arguments @('logs','list-tags-for-resource','--resource-arn',$stage5GroupArn)
                    $stage5Streams = Invoke-Stage5Aws -Arguments @('logs','describe-log-streams','--log-group-name',$stage5Group)
                    @{logGroups=$stage5Exact; tags=$stage5Tags; streams=$stage5Streams} | ConvertTo-Json -Depth 100 | Set-Content "docs/EVIDENCE/08-lambda/53-stage5-tagloggroup-inspection-$stage5Stamp.json" -Encoding UTF8
                    if ($stage5Tags.tags.Project -ne 'FinTrust' -or $stage5Tags.tags.Environment -ne 'dev' -or @($stage5Tags.tags.PSObject.Properties).Count -ne 2 -or @($stage5Streams.logStreams).Count -ne 0) { throw 'Unexpected tags/data; restore v2 and request manual cleanup review.' }
                    Invoke-Stage5Aws -Arguments @('logs','delete-log-group','--log-group-name',$stage5Group) -Profile fintrust-admin
                }
                $stage5AfterCleanup = Invoke-Stage5Aws -Arguments @('logs','describe-log-groups','--log-group-name-prefix',$stage5Group)
                if (@($stage5AfterCleanup.logGroups | Where-Object { $_.logGroupName -eq $stage5Group }).Count -ne 0) { throw 'Diagnostic group remains; report cleanup incomplete.' }
                $stage5AfterCleanup | ConvertTo-Json -Depth 100 | Set-Content "docs/EVIDENCE/08-lambda/54-stage5-tagloggroup-cleanup-$stage5Stamp.json" -Encoding UTF8
            }
        }
    }
    finally {
        Invoke-Stage5Aws -Arguments @('iam','set-default-policy-version','--policy-arn',$stage5Policy,'--version-id','v2') -Profile fintrust-admin
        $stage5Restored = Invoke-Stage5Aws -Arguments @('iam','list-policy-versions','--policy-arn',$stage5Policy)
        if (-not ($stage5Restored.Versions | Where-Object { $_.VersionId -eq 'v2' -and $_.IsDefaultVersion })) { throw 'URGENT: v2 restoration not verified.' }
        if ($stage5Restored.Versions | Where-Object { $_.VersionId -eq $stage5NewId -and $_.IsDefaultVersion }) { throw 'URGENT: diagnostic still default.' }
        $stage5Restored | ConvertTo-Json -Depth 100 | Set-Content "docs/EVIDENCE/02-iam/36-stage5-tagloggroup-v2-restored-$stage5Stamp.json" -Encoding UTF8
    }
}
```

The helper emits the exact SDK response/error and RequestId without debug traces,
credentials or a second creation attempt. It independently requires that the
new default's full document matches the candidate, the group is absent and STS
identifies the expected role. It refuses missing approval flags, old v2/v5,
and reused evidence paths. A network error is recorded as outcome_unknown;
inspect physical state and clean up only the attributable empty tagged group.
Unexpected data/name/tag collisions require manual review, with v2 restored
regardless. Do not retry if propagation, preflight or creation fails.

If tags/retention inspection or cleanup fails, restoration still runs through
nested finally. If restoration itself fails, immediately report it and restore
v2 with the same administrator command; do not run another creation request.
Neither the helper nor these commands delete the existing failed stack. No
CloudFormation execution, package upload, Lambda invocation or trigger occurs.

## Outcome interpretation and stopping rule

If direct tagged creation succeeds relative to the v5 control, adding the exact
legacy grant is strongly implicated as the missing effective allowance for this
account/test. It still does not prove a global requirement for both tagging
permissions or justify promoting all relaxed v5 conditions permanently. Clean
up, restore v2, propose the smallest permanent correction separately, then seek
approval before any CloudFormation retest.

If the same denial remains, clean up any attributable group, restore v2 and stop
speculative IAM broadening. Recommend an AWS service-level/support investigation
using direct request 9aa1ba5a-1a43-4238-bd8d-a62f4b038348 and prior CFN requests,
plus the new response if a later test is approved. No support message is sent.

No new policy version, deletion, activation, log group, stack change, package
build/upload or deployment was performed here. No additional recurring-cost
resource exists from preparation. Historical ZIP and VersionId remain unchanged;
current hardened application code is not deployed by this proposed experiment.

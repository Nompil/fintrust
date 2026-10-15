# Stage 5 async IAM correction and CREATE rollback recovery

> Latest live state: Stage 5 disabled ingest infrastructure is VERIFIED / CREATE_COMPLETE.
> See the final live checkpoint below. Prior failure/recovery instructions are historical.

Status: preparation only; no AWS mutations authorized or performed in this review.
This supersedes the retry instructions in STAGE5_PERMANENT_FIX.md for the current
stack. Stages 1â€“4 remain verified; Stage 5 is not verified; AWS Integration is In Progress.

## Proven deployment outcome

The permanent legacy logs fix created IngestLogs and IngestFunction successfully.
IngestAsync failed on lambda:PutFunctionEventInvokeConfig against
`arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev:$LATEST`
(request b9d6a986-09a3-435d-a6fd-0297ba74fca3). Rollback then failed on
lambda:DeleteFunctionEventInvokeConfig against the same ARN
(request 0c93f458-2189-4d99-8f2b-03f837bb95ba).
The stack reached ROLLBACK_FAILED; v2 was restored as default afterward.

Surviving resources from the captured post-attempt evidence: Lambda active but
reserved concurrency 0, Python 3.12/x86_64, outside the VPC; log group with
FinTrust/dev tags, 14-day retention, zero stored bytes and no streams. Async config
is physically absent although its CloudFormation deletion failed. SQS mappings,
raw-bucket notifications and Lambda invocation policy were absent. This review
has not re-enumerated all API Gateway/EventBridge sources or invoked the function.
Historical evidence: docs/EVIDENCE/08-lambda/62â€“68-stage5-permanent-*.

## Root cause and exact policy change

An exact unqualified ARN does not match its qualified $LATEST ARN. The original
policy also omitted the async delete action entirely. Real AWS simulations below
reproduce all three qualified async denials against the original document.

Existing statements are preserved exactly, including unqualified concurrency:

```json
[
  {
    "Sid": "ConfigureNamedIngest",
    "Effect": "Allow",
    "Action": [
      "lambda:PutFunctionConcurrency",
      "lambda:PutFunctionEventInvokeConfig"
    ],
    "Resource": "arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev",
    "Condition": {
      "StringEquals": {
        "aws:RequestedRegion": "af-south-1"
      },
      "ForAnyValue:StringEquals": {
        "aws:CalledVia": [
          "cloudformation.amazonaws.com"
        ]
      }
    }
  },
  {
    "Sid": "InspectNamedIngest",
    "Effect": "Allow",
    "Action": [
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:GetFunctionConcurrency",
      "lambda:GetFunctionEventInvokeConfig",
      "lambda:ListTags"
    ],
    "Resource": "arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev",
    "Condition": {
      "StringEquals": {
        "aws:RequestedRegion": "af-south-1"
      }
    }
  }
]
```

Add the following separate customer-managed policy, `FinTrustStage5Async`, to
fintrust-deployer-role only after approval. The reviewed base deployment policy is
unchanged; restore its already-archived permanent v7 instead of creating another
version. The supplemental file is infrastructure/iam/stage5-async-policy.json:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ConfigureIngestAsync",
      "Effect": "Allow",
      "Action": [
        "lambda:PutFunctionEventInvokeConfig",
        "lambda:DeleteFunctionEventInvokeConfig"
      ],
      "Resource": "arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev:$LATEST",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "af-south-1"
        },
        "ForAnyValue:StringEquals": {
          "aws:CalledVia": [
            "cloudformation.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "InspectIngestAsync",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunctionEventInvokeConfig"
      ],
      "Resource": "arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev:$LATEST",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "af-south-1"
        }
      }
    }
  ]
}

```

This split is required by policy size: base 6065 non-whitespace characters;
adding two dedicated statements to it would total 6686 (even removing the old
unqualified Put grant would still exceed the limit), above the 6144 managed-policy limit.
The supplemental policy is 659 characters. Existing inline role policies cannot
fit it; the verified managed attachment quota is 20, with 10 attached, so this
proposal uses 11/20. No quota increase or unrelated policy consolidation is needed.

Only DeleteFunctionEventInvokeConfig is a new action; Put/Get gain authorization
for the exact qualifier. No function, account, version or alias wildcard is added.
The existing unqualified Put/Get grants remain unchanged; they do not authorize
another qualifier. Mutation retains the existing regional and CalledVia guards;
read access uses the existing region-only read pattern. Caller-context simulation
cannot prove live CalledVia propagation; a subsequent approved attempt remains
necessary. No diagnostic-only logs relaxations are promoted.

The regional EventInvokeConfig schema explicitly lists Put for create, Get for
read and Delete for delete. It lists UpdateFunctionEventInvokeConfig for update
and ListFunctionEventInvokeConfigs for list. Neither update/list is needed for
this frozen CREATE-only retry, and neither is granted. Future updates require a
separate review. The template explicitly sets Qualifier=$LATEST; no qualifier
wildcard is necessary. Delete permission is required so a failed forward operation
can be cleaned up by CloudFormation during rollback.

Sources (read 2026-10-08):
- https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html
- https://docs.aws.amazon.com/lambda/latest/dg/lambda-api-permissions-ref.html
- https://docs.aws.amazon.com/lambda/latest/api/API_PutFunctionEventInvokeConfig.html
- https://docs.aws.amazon.com/lambda/latest/api/API_DeleteFunctionEventInvokeConfig.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_ContinueUpdateRollback.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DeleteStack.html
The regional provider schema is archived in iam/evidence/stage5-async-version-baseline.json.

## Version capacity and evidence

Live versions are v1, v2(default), v5, v6, v7. All five slots are occupied.
v7 equals the unchanged local permanent policy; v5 and v6 equal their committed
diagnostic files. Their complete live documents and default flags are archived
in iam/evidence/stage5-async-version-baseline.json. Preserve v2 rollback, v6 useful
legacy success diagnostic, and v7 permanent failure history. If a future new base
version is needed, v5 is the oldest remaining archived nondefault diagnostic
candidate; recheck and archive it before separately approved deletion. This plan
needs NO version deletion: reuse v7 and create a separate managed policy.

## Safest recovery: administrator deletes the failed CREATE stack

ContinueUpdateRollback applies to UPDATE_ROLLBACK_FAILED, not this ROLLBACK_FAILED
CREATE path. Do not call it or skip resources. Use controlled fintrust-admin
DeleteStack after policy review/approval. No service role is attached; CloudFormation
uses caller credentials. The deployer still lacks physical DeleteFunction by
design, so deploying the async correction alone does not authorize full stack
cleanup with the deployer. Do not broaden deployment permissions for administrator
recovery. DeletionPolicy=Retain means the log group will remain. CloudFormation
should remove its owned Lambda and async config; verify physical absence afterward.
If deletion fails, stop and capture exact events rather than force-delete, retain
additional resources, or manually remove owned resources by assumption.

The retained named log group would collide with a new CREATE. After stack deletion,
inspect and archive its tags, retention, bytes and streams again. Only after
separate approval may the administrator delete the exact empty group. If streams
or bytes now exist, preserve/export evidence and stop for a revised cleanup decision.
Do not import/reuse/rename resources as an unreviewed template change.

## Future manual commands â€” DO NOT RUN without approval

Run from C:\Users\Nompilo\Desktop\fintrust. Use PowerShell single quotes for $LATEST.
Before any mutation verify admin account 966467878406 and user/fintrust-admin;
verify inventory identity for reads. Check every exit code and stop on failure.

```powershell
$stage5Aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$stage5Policy = 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
$stage5Stack = 'arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-ingest-dev/27ea8670-c34f-11f1-abe3-0a4d42dee247'
$stage5Group = '/aws/lambda/fintrust-ingest-dev'
& $stage5Aws sts get-caller-identity --profile fintrust-admin --region af-south-1 --no-cli-pager
& $stage5Aws iam get-policy-version --policy-arn $stage5Policy --version-id v7 --profile fintrust-inventory --no-cli-pager
# Require archived v7 equality and unchanged attachment; check quotas/names again.
```

After explicit IAM approval, create and attach ONLY the supplemental policy and
select existing v7. If the policy name already exists, stop and inspect it; do not
overwrite or create duplicate versions. Keep v2 available as rollback.

```powershell
& $stage5Aws iam create-policy --policy-name FinTrustStage5Async --policy-document file://infrastructure/iam/stage5-async-policy.json --profile fintrust-admin --no-cli-pager
& $stage5Aws iam attach-role-policy --role-name fintrust-deployer-role --policy-arn arn:aws:iam::966467878406:policy/FinTrustStage5Async --profile fintrust-admin --no-cli-pager
& $stage5Aws iam set-default-policy-version --policy-arn $stage5Policy --version-id v7 --profile fintrust-admin --no-cli-pager
& $stage5Aws iam list-attached-role-policies --role-name fintrust-deployer-role --profile fintrust-inventory --no-cli-pager
& $stage5Aws iam get-policy-version --policy-arn arn:aws:iam::966467878406:policy/FinTrustStage5Async --version-id v1 --profile fintrust-inventory --no-cli-pager
& $stage5Aws iam list-policy-versions --policy-arn $stage5Policy --profile fintrust-inventory --no-cli-pager
```

After separate stack cleanup approval, archive events/resources, confirm exact
stack still ROLLBACK_FAILED with no RoleARN and expected physical names, then:

```powershell
& $stage5Aws cloudformation describe-stack-events --stack-name $stage5Stack --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation list-stack-resources --stack-name $stage5Stack --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation delete-stack --stack-name $stage5Stack --profile fintrust-admin --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation wait stack-delete-complete --stack-name $stage5Stack --profile fintrust-admin --region af-south-1 --no-cli-pager
& $stage5Aws lambda get-function --function-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --query Configuration --no-cli-pager
# Require ResourceNotFoundException, not AccessDenied, before treating Lambda as absent.
& $stage5Aws cloudformation describe-stacks --stack-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
# Require exact stack-not-found ValidationError before fresh CREATE.
& $stage5Aws logs describe-log-groups --log-group-name-prefix $stage5Group --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws logs list-tags-for-resource --resource-arn arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $stage5Aws logs describe-log-streams --log-group-name $stage5Group --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

After exact retained-empty-log cleanup approval only:

```powershell
& $stage5Aws logs delete-log-group --log-group-name $stage5Group --profile fintrust-admin --region af-south-1 --no-cli-pager
& $stage5Aws logs describe-log-groups --log-group-name-prefix $stage5Group --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Require exact log group absent; similarly named groups are not cleanup targets.
Execution role and S3 artifact remain. Before fresh CREATE verify MFA-backed
role identity, both reviewed policy documents, template/hash and historical
object version/checksum. No rebuild, renderer run or upload is required.

After separate change-set preparation approval only:

```powershell
& $stage5Aws sts get-caller-identity --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation create-change-set --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-async-review --change-set-type CREATE --template-body file://build/stage5-ingest.json --parameters 'ParameterKey=CodeObjectVersion,ParameterValue=8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.' --resource-types AWS::Lambda::Function AWS::Lambda::EventInvokeConfig AWS::Logs::LogGroup --tags Key=Project,Value=FinTrust Key=Environment,Value=dev --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation wait change-set-create-complete --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-async-review --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $stage5Aws cloudformation describe-change-set --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-stage5-async-review --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
```

Require CREATE_COMPLETE/AVAILABLE, exactly three Adds: IngestLogs/Logs::LogGroup,
IngestFunction/Lambda::Function, IngestAsync/Lambda::EventInvokeConfig. No IAM
capabilities, service role, imports, triggers or other resources. STOP for separate
execution approval. Concurrency stays 0. A successful disabled deployment proves
provisioning only, not runtime processing or the hardened source.

If a separately approved attempt fails, capture exact events/resources first.
Restoring permissions does not stop a running CloudFormation operation; wait for
a safe terminal checkpoint before separately approved restoration. Then restore
v2 and detach only the supplemental policy (do not delete its evidence):

```powershell
& $stage5Aws iam set-default-policy-version --policy-arn $stage5Policy --version-id v2 --profile fintrust-admin --no-cli-pager
& $stage5Aws iam detach-role-policy --role-name fintrust-deployer-role --policy-arn arn:aws:iam::966467878406:policy/FinTrustStage5Async --profile fintrust-admin --no-cli-pager
```

These are future recovery commands, not an automatic rollback script. No deletion
of v5 is needed or proposed for immediate execution.

## Costs and frozen artifacts

IAM policies and selecting v7 add no standing resource charge. Disabled ingest has
no provisioned concurrency and cannot process at reserved concurrency 0. Retained
logs/storage may incur usage charges; current captured log data is empty. Existing
RDS and KMS charges continue independently; this review did not stop or alter them.

Reuse VersionId `8Y7mCJGc.s2QG2NdP1n9qy_KxntXbdx.` at the existing reports bucket/key.
ZIP SHA256 d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62.
Frozen build/stage5-ingest.json SHA256
01d8eae2ac57e7c4ae28c0e5c763f3d48f42d840d217a9164cea37c6c2d3720b.
No runtime or SQL changes are part of this correction.

Evidence to capture after future approval: 41-stage5-async-policy-attached.json/png;
42-stage5-v7-async-base-default.json; 69-stage5-async-recovery-events.json;
70-stage5-async-failed-stack-deleted.json; 71-stage5-retained-log-reviewed.json;
72-stage5-retained-log-cleanup.json; 73-stage5-async-change-set-reviewed.json/png.
Use 02-iam for policy evidence and 08-lambda for recovery/change-set evidence.
No screenshots are fabricated by this preparation.

## Validation

See iam/evidence/stage5-async-validation.json for candidate/base LF-normalized
SHA256, real positive/negative AWS simulations, Access Analyzer and limitations.
Local test results are recorded after the focused suite below. Live deployment
has not been retried; the existing stack and v2 default remain unchanged.

Focused result: **189 passed, 0 failed, 0 skipped** (7.55 seconds).
Read-only validation: **29/29 AWS simulation cases matched; Access Analyzer
zero findings**. Managed attachment capacity verified at 11/20 for the proposal;
base remains 6065/6144. AWS v2 remains default; no new policy/version was created,
attached, activated or deleted. **STAGE5 ASYNC IAM FIX READY** means ready for
reviewed manual IAM/recovery approval, not deployed or runtime verified.


## Live checkpoint: Stage 5 disabled ingest infrastructure verified

The approved async recovery deployed fintrust-ingest-dev and all three resources
to CREATE_COMPLETE in exactly one attempt. FinTrustStage5Async is attached only
to the deployer role, v7 is default, and v2 is preserved. Failed stack cleanup and
empty retained-log cleanup completed through the administrator. Python 3.12/x86_64
uses the unchanged historical artifact; reserved concurrency is 0 and trigger
checks are clear. The async $LATEST settings match the template. See
[verification report](../docs/EVIDENCE/08-lambda/82-stage5-async-verification-result.md)
for live evidence and the resolved post-deploy empty-OnSuccess comparison.
Stage 5 infrastructure is Verified; AWS Integration remains In Progress. Runtime
processing and the hardened-runtime release are separate and have not begun.
Earlier recovery commands are historical: do not repeat them against this
CREATE_COMPLETE stack. No package upload, invocation, SQL, RDS/SQS/DynamoDB
mutation or Git push occurred.

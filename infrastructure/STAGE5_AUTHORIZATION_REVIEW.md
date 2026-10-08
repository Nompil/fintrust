# Stage 5 complete tagged-log creation authorization review

Current checkpoint: the approved v6 direct test succeeded; canonical v2 plus one
scoped legacy grant is prepared locally. See [permanent fix and recovery](STAGE5_PERMANENT_FIX.md).
Earlier hypotheses/results below are preserved as chronological evidence.

Status: **ROOT CAUSE NARROWED — READY FOR NEXT CONTROLLED TEST** (local proposal
for approval only). Most likely remaining policy gate: CreateLogGroup request
context, with CalledVia the next single-variable test. No root cause is proven.
No IAM mutation, stack deletion, change set or deployment was performed here.

## Findings and authorization path

1. Human `fintrust_deployer` obtains the MFA-backed `fintrust-deployer-role`
   session. CloudTrail records the role issuer and mfaAuthenticated=true.
2. ExecuteChangeSet is authorized by the role's attached/inline policies.
3. The stack has no RoleARN. CloudFormation forwards caller credentials; the
   failed Logs requests retain that role principal and invokedBy=CloudFormation.
4. Tagged creation needs an Allow for CreateLogGroup on the exact named group
   and a supported tagging permission. Here the design uses TagResource.
   Both permissions must pass their applicable resource/context checks and any
   effective boundaries/session restrictions/denies. An isolated TagResource
   simulation does not authorize the entire API request.
5. Retention configuration and later Lambda creation are downstream steps.
   This failure happened before those steps; their permissions are not changed.

AWS's API documents either TagResource or legacy TagLogGroup permission for
creation with tags. The live regional provider schema advertises TagResource.
Do not add the legacy action as a speculative workaround.
[CreateLogGroup API](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_CreateLogGroup.html),
[authorization actions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html),
[CloudFormation caller credentials](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html).

The public API documentation does not specify the server's authorization check
order, error selection when multiple checks fail, or the dependent TagResource
resource/context. Consequently this review cannot confirm that a failed primary
CreateLogGroup Allow produces this exact secondary-permission message. The text
alone does not expose every policy decision; no claim is made that AWS mislabeled
it. Backend evaluation evidence or a controlled test is needed.

## CreateLogGroup and TagResource audit

Canonical/live v2 matches `infrastructure/iam/stage5-deployment-policy.json`.
CreateIngestLogGroup is unchanged across v2, v3 and v4:

- Only logs:CreateLogGroup.
- Resource: `arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev:*`.
- Region af-south-1; Project=FinTrust and Environment=dev request tags.
- ForAnyValue:StringEquals CalledVia includes cloudformation.amazonaws.com.

AWS documents the suffixed ARN for most log-group permissions, with unsuffixed
ARN exceptions for TagResource, UntagResource and ListTagsForResource. Create
supports log-group resource scope, aws:RequestTag/${TagKey}, aws:TagKeys and
resource tags in the action table. Existing request-tag controls are supported;
resource tags should not be assumed to exist before resource creation. No need
for CreateLogGroup Resource="*" is established.
[ARN forms](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_LogGroup.html).

CalledVia is a multivalued FAS context key; correct use is the existing set
operator. AWS documents conditional availability. CloudTrail invokedBy is not
an IAM CalledVia trace. Absence of a service role supports caller credential use
but does not by itself establish that this particular provider/API/dependent
check supplied CalledVia. Do not assert its guaranteed presence.
[CalledVia availability](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-calledvia).

TagIngestLogGroup uses the exact unsuffixed ARN, documented for direct tagging.
Canonical v2 retains tags and CalledVia. v3 removed only CalledVia. v4 retained
only the exact ARN and region. All failed with the same message. These results
prove that those TagResource condition removals were insufficient; they do not
eliminate all TagResource authorization hypotheses. In particular the actual
CreateLogGroup-dependent resource/context is not disclosed in this evidence.

## Higher-level policy and session review (read-only)

| Layer | Observed result |
| --- | --- |
| Role boundary | None on GetRole |
| Source-user boundary | None on GetUser |
| Attached role policies | All 10 current managed documents/defaults fetched and reviewed |
| Inline role policies | All 3 Stage 1 documents fetched and reviewed |
| Logs grants | Only Stage 5 deployment policy contains Logs actions |
| Explicit denies | Only observed role deny concerns EC2 endpoint subnet/SG attachment; no Logs match |
| Organizations/SCP | DescribeOrganization returns AWSOrganizationsNotInUseException: account not a member; organizational SCP does not apply |
| CloudFormation service role | Stack RoleARN absent; request evidence identifies original assumed role |
| Trust | Exact source user PrincipalArn plus MFA=true required; matches verified role session |
| Default/attachment | FinTrustStage5Deployment attached; v2 default locally/live; diagnostic v4 retained nondefault |
| Explicit AssumeRole session policy | Recorded requests for all relevant sessions have no policy or policyArns fields |
| Internal/forwarded session restrictions | Not exposed in the failed Logs events; cannot fully rule out |

Source-user grants control establishment of the role session and do not simply
intersect with the role's Logs permissions after successful role assumption.
Relevant recorded AssumeRole request identifies the exact source IAM user and
MFA device. No root caller is used. Trust's account principal is narrowed by
aws:PrincipalArn; it does not mean this execution used root.

The current session is botocore-session-1791474409, assumed 15:47:14Z. CloudTrail
reports packedPolicySize=22 and sessionTokenUtilization=22. These metrics do not
reveal a policy body or prove the existence/cause of a restrictive session policy.
No credentials/caches were read to inspect session secrets. Access-key identifiers
and credential fields are redacted from saved CloudTrail evidence. No additional
role, user, trust, boundary or Organizations permissions are proposed.

## CloudTrail findings

All three request IDs found in af-south-1, logs.amazonaws.com/CreateLogGroup:

| Request ID | UTC time | Role session |
| --- | --- | --- |
| 4405018a-9e3c-4599-bd04-4f10a38f16cb | 2026-10-08 13:07:08Z | botocore-session-1791463216 |
| e9ed29b3-f2dc-48d0-befb-801908dce534 | 2026-10-08 14:20:31Z | botocore-session-1791468863 |
| 21ae5b40-b1d9-421a-a113-87728de892de | 2026-10-08 15:52:22Z | botocore-session-1791474409 |

Each reports AccessDenied and the tagged-creation/TagResource message. Each
has assumed-role userIdentity, session issuer fintrust-deployer-role, MFA=true,
invokedBy=cloudformation.amazonaws.com, sourceIPAddress=cloudformation.amazonaws.com
and userAgent=cloudformation.amazonaws.com. RequestParameters and responseElements
are null, and no resource/evaluation details expose the evaluated ARN or keys.
Thus the actual tag map and CalledVia cannot be recovered from these events.
CloudFormation resource events/template separately show the intended exact name
and Project/Environment tags; those are not proof of actual Logs request context.

Day-scoped CreateLogGroup, TagResource, CreateChangeSet, ExecuteChangeSet and
AssumeRole lookups were paginated. No related standalone TagResource event was
found for this group. A tagging authorization check within CreateLogGroup need
not generate a separate TagResource API event. Surrounding successful change-set
and execution events identify the same session. AssumeRole requests identify the
source user, role and serialNumber, without policy/policyArns fields. No sourceIdentity
is exposed; record absence rather than inventing one.

## Resource-provider behavior and limits

Read-only DescribeType in af-south-1 returns a live default AWS::Logs::LogGroup
schema. Its create handler declares CreateLogGroup, PutRetentionPolicy and
TagResource; tagging has tagOnCreate=true and cloudFormationSystemTags=true.
The schema supports other optional features; its broad handler list is not a
reason to add every declared action to this minimal template.

Published AWS provider CreateHandler invokes createLogGroup with the desired
tags, then applies retention. Translator places those tags in the initial request.
Published update handling uses legacy TagLogGroup paths. However public master
is older than the live regional schema (which now uses TagResource). It is an
illustration, not proof of the deployed binary or its complete current call chain.
The actual failure is a CreateLogGroup event, not a failed standalone TagResource
call. Initial-call tagging is supported by the available evidence; later tagging
on successful creation or update can vary with the deployed provider version.
[Published CreateHandler](https://raw.githubusercontent.com/aws-cloudformation/aws-cloudformation-resource-providers-logs/master/aws-logs-loggroup/src/main/java/software/amazon/logs/loggroup/CreateHandler.java),
[Translator](https://raw.githubusercontent.com/aws-cloudformation/aws-cloudformation-resource-providers-logs/master/aws-logs-loggroup/src/main/java/software/amazon/logs/loggroup/Translator.java),
[public schema](https://raw.githubusercontent.com/aws-cloudformation/aws-cloudformation-resource-providers-logs/master/aws-logs-loggroup/aws-logs-loggroup.json).

## Fifteen read-only IAM simulation cases

Multiple-action/multiple-resource calls produce resource cross-pairs. Aggregate
EvalDecision can be implicitDeny even when both correct action/resource pairs
are allowed, because CreateLogGroup does not match the tagging ARN and TagResource
does not match the creation ARN. Inspect ResourceSpecificResults. This is not a
real combined CreateLogGroup API evaluation and does not reproduce its backend
additional-permission check. MissingContextValues on unrelated unmatched policy
statements are not proof of missing live context.

| Case | Create gate (:*) | Tag gate (unsuffixed) |
| --- | --- | --- |
| Canonical v2, all expected context | allowed | allowed |
| Full v4, all expected context | allowed | allowed |
| Full v4, CalledVia absent | implicitDeny | allowed |
| Full v4, request tags absent | implicitDeny | allowed |
| Full v4, wrong region | implicitDeny | implicitDeny |
| Live principal/current role policies, full context | allowed | allowed |
| Candidate relative to v4, only Create CalledVia removed, context no CalledVia | allowed | allowed |

Eight independent creation-statement cases complete the 15 runs: current/full
context allowed; current/no CalledVia denied; current/no tags denied; only CalledVia
condition removed/no CalledVia allowed; only tag conditions removed/no tags allowed;
unsuffixed target denied; wrong log name denied; wrong region denied.

## Ranked hypotheses and smallest proposed next test

1. **Unchanged primary CreateLogGroup context gate.** This is the most useful
   next discriminating layer, not a proven root cause. v4's standalone TagResource
   allowance did not establish CreateLogGroup permission. Missing CalledVia or
   tag context denies the primary action in real simulations. Region and supported
   ARN forms already match documented design. Prefer removing only primary
   CalledVia first while retaining supported request-tag restrictions.
2. **Service-side dependent authorization/resource evaluation.** Standalone
   TagResource's documented ARN may not reveal the resource used by the tagged
   creation pre-check. AWS error text still points to additional permission.
   No evaluated resource/context trace exists. Do not add suffixed TagResource
   resources or legacy actions on this unproven hypothesis.
3. **Unreported session/provider restriction or service defect.** Visible role
   policies permit the documented pairs with expected context. No boundary,
   SCP or relevant explicit deny is established. Backend restrictions remain
   unknown, not excluded by SimulatePrincipalPolicy.

Smallest local candidate: `iam/stage5-deployment-diagnostic3-policy.json`.
**Starting from reviewed v4**, remove only
CreateIngestLogGroup.Condition.ForAnyValue:StringEquals (its sole CalledVia key).
TagResource stays exactly as v4, with exact unsuffixed ARN and region only. Every
other statement is identical to v4. Compared directly to live v2, there are also
the already-tested TagResource condition removals; never describe that whole
v2-to-candidate transition as a single-variable comparison. v4 is the control.

Exact changed creation statement:

```json
{
  "Sid": "CreateIngestLogGroup",
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup"
  ],
  "Resource": "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev:*",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "af-south-1",
      "aws:RequestTag/Project": "FinTrust",
      "aws:RequestTag/Environment": "dev"
    }
  }
}
```

This is justified as a controlled test of a remaining unmatched primary gate,
not as a repair proven by CloudTrail. It temporarily permits direct creation of
this one log group with FinTrust/dev request tags in Cape Town. Template tags,
region, exact group, resource types, package, runtime role, concurrency 0 and
trigger isolation remain unchanged. No simultaneous change of tagging grant,
Create ARN or request tags. No new AWS policy version was created.

For a later approved attempt only: compare a new version to this local candidate,
keep v2 as restoration control, reconfirm failed-stack resources and absent group,
then obtain separate failed-stack deletion/change-set/execution approval using
the diagnostic-two workflow. Use a uniquely named fintrust-ingest-* change set
and the same frozen template and historical object version. Execute once and
restore v2 for every outcome. No commands were executed here. Four IAM versions
exist by the previous live check; a new version uses the last free slot, so do
not delete any version implicitly or invent a version ID.

If IngestLogs then succeeds, primary CalledVia is strongly implicated relative
to v4; verify actual tags/retention and stop on any separate downstream failure.
If the same denial persists, do not loosen creation tags or ARN automatically.
Restore v2 and require AWS backend evaluation for the exact request IDs or a
separately approved diagnostic designed from new evidence. If the error changes,
record it; do not use it as permission for an automatic retry. Successful simulator
gates never prove live operation success.

## Tests, validation, evidence and preserved scope

117 focused tests passed, zero failures/skips. The new tests cover both required
gates, a denied creation action despite allowed tagging, explicit denies, missing
or wrong resource evidence, misleading aggregate cross-pair decisions, exact
resource forms and the complete one-variable candidate diff. The summarizer in
`tools/stage5_authorization.py` makes no AWS calls and is not an IAM policy engine.

Access Analyzer returned findings=[] for both the full canonical policy and the
full diagnostic-three candidate. Canonical policy, earlier diagnostics, frozen
Stage 5 template, package, runtime code and SQL are unchanged. No rebuild/upload,
RDS/SQS/DynamoDB action, invocation, concurrency change or trigger wiring. The
historical ZIP remains separate from the already-hardened current source release.
No AWS mutation or push occurred in this investigation.

Raw sanitized read-only evidence and simulation inputs/results are retained in
ignored `build/stage5-authorization-review/`. Curated evidence:
`docs/EVIDENCE/08-lambda/34-stage5-authorization-review.json` and
`docs/EVIDENCE/02-iam/29-stage5-authorization-review.json`.
These remain local/untracked; existing evidence is preserved.

The failed stack remains ROLLBACK_COMPLETE; last diagnostic's read-only result
showed no physical group/Lambda/async config. No cleanup was performed here.
The regional provider's internal authorization resource/context and policy
check order remain externally invisible. This is explicitly a hypothesis-testing
approval checkpoint, not ROOT CAUSE IDENTIFIED or permission to deploy.

## Later live results and targeted legacy-path proposal

Diagnostic three activated v5 once and again failed at IngestLogs
(request 0d0c4c54-315a-4bf6-80e3-02e70f34ec93); v2 was restored. A subsequent
approved one-shot direct SDK CreateLogGroup with the same v5 permissions also
failed (request 9aa1ba5a-1a43-4238-bd8d-a62f4b038348). The direct test used the
MFA-backed CLI role credentials in process memory; it was not a CloudFormation
call or a direct CLI Logs invocation. The group stayed absent and v2 was restored.
These results show that removing primary CalledVia was insufficient and a
CloudFormation-only explanation is insufficient; they do not prove the backend
condition/resource decision.

The next locally prepared candidate adds only the documented legacy alternative
logs:TagLogGroup on the exact suffixed group ARN to v5. See
[TagLogGroup diagnostic](STAGE5_TAGLOGGROUP_DIAGNOSTIC.md) for sources, exact
scope, tests, real simulations, archived nondefault-v3 deletion proposal and
future one-shot commands. This preparation made no AWS mutation. No existing
control policy was changed and no additional live test was executed.

## Successful live TagLogGroup diagnostic and permanent correction

On 2026-10-08 the approved one-shot direct SDK experiment used v6, exactly v5
plus one scoped logs:TagLogGroup grant. It returned HTTP 200, RetryAttempts=0,
RequestId e641540c-a094-42b4-9411-b06bfeda7e8b. FinTrust/dev tags were verified;
the empty diagnostic group was deleted and canonical v2 restored. V6 remains
nondefault. This strongly isolates the missing effective legacy permission for
the tested direct path; it does not prove all canonical CloudFormation conditions.

The permanent local policy preserves EVERY archived v2 statement and adds only
LegacyTagIngestLogGroup, logs:TagLogGroup on the exact suffixed group ARN, with
region af-south-1. Modern TagResource and primary creation keep request tags and
CalledVia. The new legacy grant can directly retag the single group; this security
tradeoff is explicit, not hidden behind primary creation's tag restrictions.
Do not promote relaxed v6 wholesale. No other Logs action, source/template/package
or runtime change is part of this fix.

Eighteen real read-only custom-policy simulations matched expected scope/context
decisions; Access Analyzer findings=[]. Results and successful live diagnostic/
cleanup are archived in iam/evidence/stage5-permanent-validation.json. The current
version snapshot archives v2/v4/v5/v6; only v4 nondefault cleanup is proposed after
fresh content verification, preserving v2 rollback and the direct test controls.
See [permanent fix](STAGE5_PERMANENT_FIX.md) for the exact future policy-install,
failed-stack removal, frozen CREATE review, one execution and recovery commands.
No AWS mutation occurred during permanent-fix preparation; the deployment remains
unproven, disabled, and subject to separate approvals.


## Current checkpoint: async qualified ARN and CREATE rollback failure

The permanent logs fix created IngestLogs and IngestFunction. IngestAsync failed
on PutFunctionEventInvokeConfig for the exact $LATEST ARN; rollback failed on
missing DeleteFunctionEventInvokeConfig. The stack is ROLLBACK_FAILED and v2
is restored as default. See [STAGE5_ASYNC_FIX.md](STAGE5_ASYNC_FIX.md) for the
size-constrained supplemental policy, read-only evidence and administrator cleanup
plan. Earlier ROLLBACK_COMPLETE retry instructions are historical and must not
be executed for this state. No AWS mutations or runtime/SQL changes in this review.

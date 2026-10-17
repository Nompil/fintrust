# Deployment gates — consolidated candidate

Status: **local candidate verified; not deployed** (16 October 2026 SAST).

## Evidence completed

- One isolated candidate combines the current UI, Cognito authentication and production migration runner for 003–006. Current country/assignee filters, report currency separation, SAST report dates, high-risk colors and text repairs are preserved.
- 1072 unique Linux tests passed across the full run and affected rechecks. The initial full run had 1,068 passes and one browser-harness failure caused by a Windows-only executable path. That failure was repaired and passed in the 190-test recheck. Three new scanner tests also passed. This is a full run plus targeted rechecks, not a claim that the original full run had zero failures.
- Final shared Lambda ZIP passed archive/content/source checks and all five handler imports, plus all-production-module checks, on Linux x86_64 Python 3.12. It was not uploaded.
- Migrations 003–006 passed the production-handler PostgreSQL 16.15 rehearsal, including ordering, reruns, privilege guards and rollback checks. Its new disposable cluster was stopped and removed. Existing clusters and saved ledger were preserved.
- Three immutable migration phase ZIPs were accepted only after every SQL/runner binding matched this candidate, then reimported on Linux and bound to the fresh rehearsal and 107 focused tests.
- Local Stage 5 deployment IAM now matches the verified live v8, including CloudFormation-only, exact-function AddPermission/RemovePermission. The superseded standalone proposal is archived under build/consolidation, not an active IAM source.
- No AWS changes, quota changes, emails, endpoints, schedules or live consumers were activated during this consolidation.

Source manifest identity: `d87b1c676b40df5326e477093a402c5b444800446273c1752407310aa6a33367`.
Lambda ZIP SHA256: `ebf94636046662736b6f77bec1616bd122e0f14c856e189f1d90fc9fa77ea1ff`.
Detailed receipts in this branch: `docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/verification-summary.json`, `full.xml`, `repair.xml`, `runner/extensions-verification.json`, `pg16-extensions-rehearsal.json`, and `fintrust-consolidated.manifest.json`.

## Live state carried forward from verified receipts

- SES mailbox identity verified; application alert delivery not yet live-tested.
- Ingest S3 invoke resource permission applied and verified. Reserved concurrency remains zero and raw bucket notifications remain absent.
- Six service templates validated; remaining service stacks are prepared, not deployed. Use the cost-gated `infrastructure/service_preparation` templates for remaining services. Existing SES identity creation stays false; optional alarms and recovery add-ons remain false; report scheduling is separately disabled.
- Temporary migration PrivateLink/network/IAM resources were removed. No temporary endpoint was recreated.

## Remaining gates and order

1. Release source has been assembled on the dedicated `release/fintrust-consolidated-20261016` branch. Its runtime source must match the retained manifest before commit. The running main checkout, local auth registry and saved database remain untouched; no production deployment is implied.
2. Resolve the regional Lambda concurrency restriction through the account's quota/support workflow. No confirmed support case ID is available. Do not request 1,001 or change the quota without the owner's decision.
3. Prove an approved migration access path and live RDS IAM/TLS/schema preflight. No interface endpoint or other recurring network cost is authorized by this candidate verification. Keep live migration blocked until both capacity and access gates pass.
4. Run and verify live migrations, then deploy/wire scoring, query/API Gateway, Cognito account scopes and backend RBAC, alert/SES, reports/EventBridge, DLQs and logging/monitoring under least privilege. Prepared templates still require real IDs and immutable artifact versions. Any optional paid alarms/features require the existing cost decision.
5. Enable consumers and the raw S3 notification only when the downstream system is ready. Run a real ingestion-to-scoring-to-persistence-to-authorized-retrieval-to-alert/audit E2E. System completion remains blocked until it passes.

No live RDS changes or live E2E have been performed by this verification.

## Post-freeze live checks

- Runtime source frozen as commit `3368f4c31373291d11d5ef852884abb669f6dca8` on `release/fintrust-consolidated-20261016`. This does not deploy or switch the running local checkout.
- Deployer identity reauthenticated and verified. Existing foundation/ingest stacks are present and healthy.
- Quota read permissions were missing. Admin was used only to publish FinTrustConsoleReadOnly v4, adding exact-quota GetServiceQuota/history and region-bounded Lambda GetAccountSettings. Existing v3 grants were preserved. Access Analyzer returned no findings; all three new reads succeeded with deployer after propagation.
- Regional quota is still 10, unreserved quota 10, and function count 1. Service Quotas request history is empty. This does not prove there is no separate AWS Support case. No quota write was attempted.
- Existing foundation outputs are mapped in `docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/live-deployment-inputs.json`. Unresolved values remain explicit; the worksheet cannot be used as an execution-ready parameter file.
- The separate AWS Support console session requires interactive sign-in. The Support case remains a draft; paid support, a 1,001 quota request and endpoint recreation remain unauthorized.

## Support case submitted - latest evidence

The owner-provided case-details screenshot confirms submission of AWS Support
case **179210878300923**, created **16 October 2026, 01:59:43 SAST**
(`2026-10-15T23:59:43.512Z`). Its displayed status is **Unassigned**.
The console shows case type **Account**, category **Service Quotas, General**,
severity **General question**, and **Basic Support**. Earlier draft-only and
no-case-ID statements above describe the earlier state and are superseded here.

Evidence is saved without visual editing as
`docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/aws-support-case-179210878300923-details.png`.
The adjacent status JSON records the PNG SHA256, dimensions and provenance.

The quota gate remains **BLOCKED_PENDING_AWS_REVIEW**. The screenshot does not
confirm a quota increase, an assigned agent, or approval for live migration.
No live migration, service activation, support-plan upgrade or endpoint creation
was performed while saving this evidence. Keep the case-access IAM policy only
for required case follow-up, then execute its recorded cleanup plan.

## Remaining runtime prerequisites and gateway repair - latest source

- Created and read back `fintrust-scoring-dev`, `fintrust-alert-dev`, `fintrust-api-dev` and `fintrust-report-dev` IAM execution roles using admin only for IAM administration. Existing ingest was untouched. These IAM prerequisites did not create functions, triggers, networks, database objects or paid services. The role creation journal, validation results and policy documents are retained.
- All four runtime policies passed Access Analyzer with no findings. They reference actual foundation outputs, per-service database users, scoped log groups, queue/table/bucket/KMS resources, exact alert stream ARN and the approved SES sender/recipient. VPC ENI permissions are regional and explicitly denied to function code.
- Fixed the confirmed API Gateway stage-path bug: the served HTML now derives asset/API prefixes from trusted Gateway context, preserving `/dev/`, `/staging/` and `/prod/` URLs. Local and custom-domain root URLs retain the root prefix. Trusted claims and prefix contexts reset even on adapter failure. The Cognito browser check now exercises the real Lambda proxy adapter at `/dev/`.
- 216 focused Linux tests passed with zero failures/skips, plus seven offline service-configuration checks. These include local/Cognito browser sign-in, API Gateway stage sign-in, filters, authorizer/RBAC and package guards. Earlier full regression evidence remains historical and has not been presented as a fresh full run for this repair.
- Rebuilt the shared Lambda archive and verified its content, source binding, all five handlers and all production modules under Linux Python 3.12. New ZIP SHA256: `ff6324d64a5d65dab18523a30ea72bb1594d2fa5ca7fbe6b8391c52f03ed589d`. It is local only and supersedes the earlier archive for future deployment.
- Disabled optional API Gateway detailed method metrics in the cost-gated prepared template. Existing alarms and schedules remain disabled. The changed API template still needs AWS ValidateTemplate under normal deployer credentials; prior API validation applies to the previous template.
- Normal deployer role credentials expired during this check; no new interactive authentication was requested merely for offline preparation, and admin was not used for non-IAM inventory/deployment. SSM parameter existence and live DB name/grants remain unverified.

Next preparation work: complete remaining deployment-policy scopes, verify/provision the exact nonsecret SSM values after identifying the live database name, and verify API Gateway logging account configuration. Live migration remains blocked on case **179210878300923**, a cost-compatible access path and live RDS preflight. No endpoint is authorized by these checks. Live Cognito scope enrollment, alert delivery and end-to-end evidence remain outstanding.

## SSM and API logging prerequisites completed - 16 October 2026

- The owner restored the monthly budget to USD 10. This is an owner-reported monitoring threshold, not a quota change or authorization for new recurring charges.
- Deployer read-back identified the available database as `fintrust`, with IAM authentication enabled. This does not prove database users, migrations or grants.
- Added FinTrustConsoleReadOnly v5, preserving v4 and adding only GetParameters on nine exact dev settings plus GET on the regional API Gateway account. Access Analyzer returned no findings and v5 was read back. All five policy-version slots are now used; review version retention before a future policy update.
- Created and read back nine Standard String SSM parameters: host/name/user for scoring, report and API. Values match the live RDS metadata and the already-installed per-service runtime policies. No passwords, tokens or advanced parameters were stored. Existing parameters were absent; no overwrite was used.
- Configured the regional API Gateway CloudWatch role `fintrust-apigateway-logs-dev` and read it back through the deployer. API Gateway rejected the custom exact-log-group policy; AWS's documented AmazonAPIGatewayPushToCloudWatchLogs service-role policy succeeded. Its seven CloudWatch Logs operations use Resource `*`; this is a recorded scope exception, not an exact-log-group permission claim. Trust allows API Gateway only. The rejected inline policy was removed.
- Prepared API access logs now use the stable name `/aws/apigateway/fintrust-${StageName}`. AWS validated the changed template. Detailed metrics and data tracing remain false; seven focused offline configuration checks passed. No new application runtime code or package changed.
- The temporary FinTrustServicePrerequisiteSetup policy was detached, deleted and its absence verified. The read-only permissions and API Gateway service role remain as prerequisites.
- Evidence: `infrastructure/service_preparation/evidence/service-prerequisites-live.json`. No function, API stage, log group, alarm, report schedule, endpoint, live migration, email or consumer was created/activated by this work. Actual log delivery remains unverified until API deployment and E2E.

Next: prepare/review the remaining stack deployment permissions, bind immutable uploaded artifacts and real Cognito/API outputs, then deploy disabled resources in dependency order when their gates permit. The quota case, cost-compatible database access, live migrations/grants and full cloud E2E still gate activation.

## Remaining deployment IAM installed - 16 October 2026

- Six managed policies are attached only to `fintrust-deployer-role` and read back: remaining CloudFormation control, four application functions, release dependencies, Cognito/scope-table configuration, API bootstrap, and monitoring/report scheduling. Existing grants were preserved. Attachment use is 19 of the account's verified 20-policy role quota; no new attachment-quota request was made.
- All seven documents, including the separate API scope-read grant, passed IAM Access Analyzer with no findings. Every managed document is below 6,144 nonwhitespace characters. No aggregate inline policy was added to the deployer role.
- Downstream mutation grants require CloudFormation. Four exact stack names and resource-type allowlists prohibit IAM/custom-resource types, imports and substituted CloudFormation service roles. Four Lambda roles/functions, exact artifact key, nine SSM settings, own log destinations, two function-bound mappings, one report rule/target/failure-queue policy, the tagged workforce pool, exact scope table and eighteen optional alarm names form the new resource boundaries.
- Twenty-six AWS IAM custom-policy scenarios passed, including denied direct function writes/invocation, unrelated functions/roles, IAM role-policy edits, endpoint/NAT creation, missing/forbidden CloudFormation resource types, and incorrect Cognito/API scope. The final additive scoped log-read grant has a separate two-resource simulation receipt. These tests do not prove the complete principal/SCP/resource-policy union or live service execution.
- The admin separately installed `FinTrustApiUserScopes` on `fintrust-api-dev`, granting only GetItem on the exact future scope table. The prepared Cognito template no longer contains an IAM policy or ApiExecutionRoleArn parameter. Existing runtime policies remain preserved. Explicit dev tags were added to prepared functions, mappings, logs, API and workforce pool for reliable ownership checks.
- `FinTrustApiDeployment` deliberately remains bootstrap-only. It can create the named REGIONAL API and read metadata needed for CloudFormation to return its generated ID. Full API mutation scope is not granted until that actual ID is verified and bound. No API or Cognito stack was created during this IAM work.
- Current template edits passed seven offline configuration checks. AWS validation receipts for earlier templates are historical; the latest tagged templates and Cognito IAM removal still need normal-deployer ValidateTemplate. The deployer authentication attempts returned the wrong identity/expired sessions; identity guards prevented using them for deployment. The exact reported browser error remains pending from the owner. Admin was used only for IAM administration/validation/simulation, not as a deployment workaround.
- Evidence and the concrete staged deployment sequence are in `infrastructure/service_preparation/deployment_iam/`. The existing runtime ZIP/source is unchanged. No artifact was uploaded, live RDS SQL run, function/consumer/API stage deployed, email sent, schedule/paid alarm enabled, network endpoint created, support plan upgraded or quota changed by this work.

Next live step, after verified deployer authentication: validate the latest templates and review the API-shell change set, then bind its real ID before configuring Cognito. Runtime activation remains blocked on capacity, approved database access/migrations/grants, cost review and live E2E. Support case **179210878300923** remains the retained quota-review path; no new AWS reply is claimed here.

Final log-read diagnostic remains open: IAM custom-policy simulation returned
implicitDeny for the owned log stream as well as the unrelated stream. A separate
single-resource test and a bare explicit-allow exact-ARN policy also returned
implicitDeny for the owned stream, with no missing context reported. The 26
earlier boundary scenarios passed; these extra log diagnostics are not passes.
The installed log read grant retains the documented exact group/stream ARN scope;
it was not broadened to force a simulator result. Verify the normal deployer's
real CloudWatch Logs read once authentication is restored. This discrepancy is
not evidence that log delivery or log inspection works in the live application.

Cross-platform deployment bindings were also repaired: generators now write
explicit LF newlines and Git preserves them for hash-bound JSON documents.
Canonical policy/template/runtime-file hash verification passed on Windows and
Ubuntu Linux. Policy JSON objects and installed permissions did not change;
the previous Windows manifest binding is retained in installed.json alongside
the canonical binding. AWS revalidated all seven canonical policy documents
with no findings. The runtime Lambda ZIP was not changed or rebuilt.


## API identity and empty Cognito configuration deployed - latest 16 October 2026

This section supersedes earlier authentication, template-validation and API-bootstrap pending statements.

- The normal deployer identity was verified. AWS accepted the four latest prepared templates (API shell, API, application functions and Cognito). Admin remained limited to IAM validation/installation.
- `fintrust-api-dev` is CREATE_COMPLETE with API ID `qzgzopn8o4`. It has no serving stage or methods. Its exact callback is `https://qzgzopn8o4.execute-api.af-south-1.amazonaws.com/dev/`.
- API tag-on-create initially failed before resource creation. The verified empty failed stack was replaced after correcting the encoded tagging ARN. The installed API policy now binds the actual API ID and removes root API creation and bootstrap tag/metadata wildcards.
- `fintrust-auth-dev` is CREATE_COMPLETE: pool `af-south-1_NnmfBS0y9`, public browser client, hosted domain and four groups. Read-back confirmed Lite tier, mandatory software MFA, authorization-code flow and exact callback/logout URLs. No users or invitations were created.
- The on-demand `imbokodo-dev-user-account-scopes` table was created with point-in-time recovery disabled. No scope records were written. Cognito's first attempt failed on its pre-creation TagResource check; the correction retains required request tags, account/region and CloudFormation boundaries. The first failed stack was removed only after checking no pool existed and its cancelled table was deleted. Both attempts are retained as evidence.
- The deployment worksheet now contains actual Cognito/API values. The immutable S3 code key/version remains unresolved because the new archive is not uploaded; the API function remains undeployed. This is still a worksheet, not execution-ready parameters.
- A real deployer GetLogEvents call returned ResourceNotFoundException for the not-yet-created owned log group rather than AccessDenied. Historical simulator implicitDeny diagnostics remain recorded. Actual log delivery and an existing-stream read are untested.
- The last regional Lambda quota read remains 10. No support response or quota increase is claimed. Case 179210878300923 remains the manual-review path.

SES identity/runtime permissions are prepared; delivery awaits Alert Lambda and a real delivery test. EventBridge report wiring and CloudWatch alarms are prepared, with schedules/optional alarms off. No application function, consumer, raw S3 notification, report schedule, paid alarm, endpoint, database migration or email was activated by this step. The local ledger and running app were untouched.

Next: verify an approved database access path and live schema/users/grants, complete migrations once capacity permits, bind the uploaded immutable package, deploy the application functions/API, then validate each service and the full cloud flow before activation. A USD 10 budget is a monitoring threshold, not a spending cap or service-quota change. AWS review and the remaining live gates prevent a deployment-ready claim today.

Evidence: `infrastructure/service_preparation/deployment_iam/evidence/{api-shell-live,auth-configuration-first-attempt,auth-configuration-live,live-deployer-checks-20261016}.json`.


## Existing gateway scope path corrected - final network read-back

Fresh deployer inventory confirms only the existing S3/DynamoDB gateway endpoints, private RDS available, no public database access/default internet route/IPv6 assignment, SES email verification SUCCESS, and Lambda capacity still 10. The monthly rule `fintrust-monthly-dev` is absent, consistent with prepared-but-undeployed reports.

The inventory revealed that the DynamoDB gateway policy excluded the new account-scope table. A network change set modified only `DynamodbEndpoint.PolicyDocument`, with Replacement=false. It preserves the risk-table statement and adds only GetItem on the exact scope table for `fintrust-api-dev` in this account. Its first update and rollback failed on endpoint CreateTags. A CloudFormation-only CreateTags grant on the one tagged endpoint passed Access Analyzer and was installed/read back. Normal rollback recovered without skipped resources; the retry completed UPDATE_COMPLETE. The gateway is available, its physical ID and all network stack outputs are unchanged, and the new policy was read back. No route, subnet, security group, RDS, gateway count or interface endpoint was changed.

The failed/recovered attempt and successful retry are retained in `deployment_iam/evidence/gateway-account-scope-*.json`; `infrastructure/network-account-scope-update.json` is hash-bound to the receipt and reproducible by the network generator. The full seven-policy bundle was revalidated without findings. Six focused network tests and seven offline preparation checks passed; Windows/Linux policy/template/live-receipt binding verification passed. These are configuration checks, not new full-suite or live end-to-end results.

Current remaining gates are recorded in `infrastructure/service_preparation/service-completion-status.json`. Runtime ZIP/upload state is unchanged. Paid monitoring/schedules and processing remain off. The quota review, private database access/migrations/grants, immutable upload/deployment, approved enrollment and full cloud E2E remain outstanding.


## Shared-capacity individual-test candidate - 17 October 2026

The regional limit of 10 blocks the planned positive reserved allocations; it
does not establish that all unreserved Lambda execution is unavailable. A
separate `infrastructure/service_preparation/shared_manual/` candidate now
supports reviewing individual functions against shared capacity. Defaults
retain zero concurrency for all four functions. Explicit manual selection can
omit reservation for one function only; the other three remain zero. Consumers
and scheduled reports are hard-disabled, and no provisioned capacity is added.
All other resource configuration is preserved. The original reserved template,
installed IAM, deployed stacks, ingestion and runtime ZIP are unchanged.

Eleven configuration tests passed on Windows and Linux: seven existing checks
and four candidate checks covering default throttling, every manual selection,
selection-rule behavior, automatic-path restrictions and preserved resources.
The manifest binds candidate/base bytes. After deployer authentication was
renewed, AWS ValidateTemplate accepted this exact candidate with no IAM
capabilities. The separate receipt records its hash and AWS result. Template
acceptance is not stack creation or runtime execution. No upload, new
cost-bearing resource, runtime invocation, email or activation occurred.

This option has no per-function execution cap when selected: one selected
function could consume the available shared pool. Sequential synchronous tests
require reviewed invocation permissions, inactive upstream paths and applicable
database prerequisites. It is not a production rollout or a changed migration
runner. The private-access/migration/grant gates, artifact/version binding,
approved enrollment and full cloud E2E remain outstanding; the current migration
plan still needs its own reviewed capacity decision. Retain the quota support
case while evaluating this limited alternative. See the candidate guide and
`offline-verification.json`; do not count the local checks as live AWS evidence.


## Approved package staging completed - 17 October 2026

The owner authorized the bounded upload-only cost exception. One 26,537,014-byte
verified release package was staged in the existing reports bucket under its
content-addressed deployment key, using conditional creation rather than
unconditional overwrite. Bucket location, enabled versioning, KMS encryption
and absent delivery notifications were checked first; their configuration was
not changed. Actual S3 version: `VZCWpaBXZO9pL2XONICW63qQcH4udM02`.

That exact version was downloaded and its bytes, size, SHA256, S3 checksum and
KMS key matched the approved package. The SHA256 remains
`ff6324d64a5d65dab18523a30ea72bb1594d2fa5ca7fbe6b8391c52f03ed589d`. The deployment worksheet now binds
the real code key/version; it remains an operator worksheet, not approval to
execute a stack. The temporary exact-object upload grant passed Access Analyzer,
was read back, detached/deleted after verification, and its absence and original
role attachment set were verified. Existing policies were preserved. Its
30-minute expiry was a backup safeguard, not the cleanup mechanism.

Receipt: `infrastructure/service_preparation/shared_manual/artifact-staging-live.json`.
Admin was used only for IAM/Access Analyzer and the normal deployer role for
S3/KMS operations. No new bucket, Lambda deployment/invocation, CloudFormation
execution, trigger, schedule, database statement or email was performed. Storage,
requests and associated usage may incur charges; no USD 10 total-cost guarantee
is claimed. Function deployment, database/migration/grant gates, approved test
invocation, enrollment and full cloud E2E remain outstanding.

## Report async deployment permission corrected - 17 October 2026

The report EventInvokeConfig deployment/read permissions now bind the exact
`fintrust-report-dev:$LATEST` ARN used by the template. The application policy
was validated through Access Analyzer, installed and read back; the source,
manifest and installed policy hashes match (`verify_bindings.py`: PASS).
No runtime invocation or additional service activation is established by this
IAM correction. Application deployment completion requires its separate live
receipt; a terminal completion report alone does not clear that gate.

## Disabled application stack verified - 17 October 2026

AWS stack `fintrust-application-dev` reached CREATE_COMPLETE. The exact staged
package checksum was read back on scoring, alert, report and API functions.
All five functions including ingest remain at reserved concurrency zero; both
event-source mappings and the monthly EventBridge rule are disabled. Four
application log groups have 14-day retention. No raw S3 notification or API
stage exists. No application invocation, SQL, email or automatic processing
was performed. The live receipt is
`infrastructure/service_preparation/shared_manual/application-disabled-live.json`.

The deployment worksheet now contains the actual API function name; its
template adds the dev alias. API configuration, live RDS access/migrations/
grants, approved enrollment and runtime/end-to-end evidence remain gates.

The next API UPDATE change set `fintrust-api-bound-review-20261017` is prepared
and reviewed, not executed. It adds 19 resources, with no API replacement and
no IAM capabilities; the existing API ID and OAuth callback remain bound.
Receipt: `infrastructure/service_preparation/deployment_iam/evidence/api-update-reviewed.json`.
Execution would create the public dev stage while the API function remains at
zero concurrency, so it would not yet provide a working application. External
API requests/logging can incur usage charges; no request was sent in this review.

## API configuration deployed and verified - 17 October 2026

The owner authorized the reviewed public-dev-stage configuration with functions
disabled. `fintrust-api-dev` reached UPDATE_COMPLETE, preserving API ID
`qzgzopn8o4` and the exact registered callback. Seven methods, Cognito authorizer,
alias-qualified integration and exact API/stage invoke permission were read back.
Access logs have 30-day retention; detailed metrics, tracing, caching and payload
tracing remain disabled. No test traffic, application invocation, SQL or email
was performed. Five functions remain at zero, both mappings disabled, monthly
rule disabled and raw S3 notification absent.

The first attempt failed on the encoded dev-stage tag ARN; normal rollback also
needed permission to remove its new empty API log group. The corrected policy
adds only that exact stage tag resource, still through CloudFormation. A separate
exact-log cleanup grant had a 30-minute expiry and was detached/deleted afterward;
the original attachment set was verified. CloudFormation completed normal
rollback with no resource skips and removed the empty group itself. Existing
application/data resources were preserved. Failure/recovery receipts are retained.

Final receipt: `infrastructure/service_preparation/deployment_iam/evidence/api-configuration-live.json`.
Configured does not mean operational: private RDS access/migrations/grants,
approved user/account scopes, capacity and cloud E2E remain gates. External API
requests and logs can incur usage charges even while Lambda is throttled.

Fresh metadata after API verification still reports Lambda total/unreserved
capacity 10 and five deployed functions. RDS is available, private, IAM-auth
enabled, deletion-protected, with one-day backups and latest restorable time
`2026-10-17T06:42:24Z`. This proves no schema, grant or SQL outcome. Receipt:
`infrastructure/service_preparation/deployment_iam/evidence/remaining-live-gates-20261017.json`.

## Read-only database preflight alternative prepared - 17 October 2026

A preflight-only candidate can use shared Lambda capacity without requesting a
positive reserved slot. It is disabled by default and leaves canonical write
phase templates unchanged. It provides no per-function concurrency cap when
released. No AWS resource, secret read, SQL or invocation was performed.

AWS accepted the exact network and runner templates. The 20,673,673-byte
preflight ZIP was built from current bound sources and verified dependency
bytes; SHA256 `667f1aba96d8deed5033bb4f9ec14b1ac02e8e36b4db04b77f20d9699fdb4d57`.
Linux Python 3.12 native imports passed. The disposable PostgreSQL 16 run passed
65 tests with no failures/errors/skips, and its temporary cluster was removed.
This is local verification, not a live RDS handshake or migration result.

The private route still requires a temporary charged Secrets Manager endpoint,
a separate scoped operator (existing endpoint Deny preserved), actual-endpoint
IAM binding/validation, exact artifact staging and cleanup verification. The
owner's no-paid-endpoint constraint remains in force. The prepared decision is
one read-only inspection with a USD 1 incremental operating allowance and
one-hour endpoint cleanup target, not an AWS-enforced cost cap. No data-changing
phase is included. See `infrastructure/service_preparation/database_preflight/README.md`.

Fresh metadata still reports Lambda capacity 10. Support DescribeCases returned
SubscriptionRequiredException on Basic Support; no upgrade or new case was
made. Preserve case 179210878300923; its current correspondence is unverified.

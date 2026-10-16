# Remaining dev deployment permissions

Account `966467878406`, region `af-south-1`, dev only. These documents grant
deployment capabilities; installing them does not deploy, activate or authorize
paid workloads. Keep the release's cost and migration gates in force.

Six customer-managed policies attach only to `fintrust-deployer-role`:

| Policy | Scope |
| --- | --- |
| FinTrustRemainingCloudFormation | Four exact stacks; named change sets; explicit resource-type lists; no IAM/custom resources, imports or service-role substitution |
| FinTrustApplicationDeployment | Four exact new functions, API version/alias, report async settings, four exact Lambda PassRole grants, exact invoke principals and nine nonsecret SSM reads |
| FinTrustReleaseDependencies | The content-addressed approved code key, scoped S3 KMS decrypt, five owned log configurations, and two function-bound mappings with owned tags |
| FinTrustIdentityDeployment | Tagged dev workforce pool configuration and the exact account-scope table; no user enrollment, account-scope data writes or IAM role-policy editing |
| FinTrustApiDeployment | Named regional API creation and bootstrap metadata reads; full API mutation scope is deliberately absent until its generated ID is read back and bound |
| FinTrustMonitoringDeployment | Eighteen exact optional alarm names, one monthly report rule/target/delivery-queue policy, and reads of five owned application/API log destinations |

Downstream writes require `aws:CalledVia` to include CloudFormation. Deployer
cannot use this bundle for direct function changes/invocations, NAT/endpoint
creation, uploading arbitrary artifacts or editing role policies. Existing
stage policies remain separate; this document is not a claim that the complete
principal has no other rights. Current aggregate attachment count is 19 of 20.

`AdminInstalledApiScopeRead.json` is installed by the administrator as inline
`FinTrustApiUserScopes` on `fintrust-api-dev`. It grants only GetItem on
`imbokodo-dev-user-account-scopes`. The prepared Cognito template therefore no
longer contains an IAM policy or ApiExecutionRoleArn parameter. Historical
generic/source templates are retained for provenance and must not be deployed
instead of the prepared cost-gated templates.

## Bindings and validation

`build_policies.py` is offline. Its manifest records per-document SHA256 and
nonwhitespace sizes, exact stack resource types and the approved runtime ZIP
SHA256. All managed documents must stay below 6,144 nonwhitespace characters.
The code key is a proposed content-addressed destination, not proof of upload.
An actual immutable S3 version still needs verification before function creation.
Generated JSON uses explicit LF newlines, with matching Git attributes, so the
hashes survive Windows/Linux checkouts. `verify_bindings.py` checks policy,
template and runtime-file hashes against both their manifests and the installed
policy read-back documents. It passed under Windows and Linux; it deliberately
reports the pending sign-in, template-validation and live log-read gates.

AWS receipts live in `evidence/`:

- `validation.json`: Access Analyzer findings and the exact manifest hash.
- `simulation.json`: 26 AWS IAM custom-policy boundary scenarios. This checks
  the new bundle, not every existing policy/SCP/resource-policy combination.
- `installed.json`: per-policy default versions and read-back documents,
  attachments, and the separate API role grant. Installation is not a runtime test.
- `log-read-*.json`: final log-read diagnostics remain unresolved. Both the
  scoped bundle and an isolated bare exact-ARN allow returned implicitDeny for
  the owned stream; the unrelated stream was also denied. Do not count these as
  successful positive checks or broaden the actual grant to force a pass. A real
  normal-deployer Logs read is still required after sign-in is restored.

For a future API ID, first verify that it belongs to `fintrust-api-dev` and the
CloudFormation logical resource `Api`. Run the offline builder with `--api-id`
using that actual ID, revalidate, then have the admin update only the owned API
deployment policy. This removes bootstrap-wide metadata reads and limits writes
to that API and its children. Do not substitute a guessed ID or grant wildcard
API mutation access to get past the dependency.

## Deployment sequence after authentication and gates

1. Use the verified deployer role for service operations, admin only for IAM.
2. Review a shell change set for `fintrust-api-dev` from `api-shell.json`. It
   creates the API identity only, with no stage, methods, Lambda or API traffic.
   Read its real ID and callback URL; bind the API policy as above.
3. Prepare `fintrust-auth-dev` from `cognito.json`, using the actual callback
   and logout URLs, `StageName=dev`, and a verified available domain prefix.
   Keep scope recovery false, Cognito Lite and software MFA. No invitations or
   account-scope records are implied by pool/table creation.
4. Bind real Cognito outputs and the verified uploaded package version in the
   application worksheet. Check the current report-failure queue policy before
   applying the SQS::QueuePolicy resource; preserve any unrelated statements.
5. Review separate change sets, supplying each manifest resource-type list and
   Project=FinTrust/Environment=dev stack tags. Do not use CAPABILITY_IAM or
   bypass resource-type guards with a service role.
6. Keep EnableFunctions, EnableConsumers, EnableMonthlyReports, EnableAlarms and
   EnableScopeRecovery false. Optional alarms are not free merely because
   ActionsEnabled is false. Do not deploy optional paid monitoring to claim it
   is configured. Use existing service metrics/logs within the cost decision.
7. Verify quota, cost-compatible live database access, migrations, users/grants
   and data isolation before activation. Then prove ingestion, scoring,
   persistence, Cognito/RBAC retrieval, SES delivery, reports and failure paths.

The owner-reported USD 10 budget is a monitoring threshold. It is neither a
service quota increase nor an automatic spending cap. No endpoint recreation,
paid support upgrade, 1,001 quota request or activation is part of IAM setup.

# Remaining AWS service preparation

Initially prepared locally on 15 October 2026 (SAST). Subsequent live progress:
cloud-status.json records the verified SES email identity, scoped IAM changes
and cleanup. cloudformation-validation.json records six accepted AWS template
validations. No application/monitoring stacks, schedules or alarms were deployed.
No test alert was sent. Initial manifest fields describe the initial offline render;
cloud-status.json is the later live status. Validation is not live E2E proof.

## What is ready for review

- templates/ses-identities.json: email identity proposals using
  nompilomabuya@outlook.com as both sender and recipient. Creation defaults off;
  inspect the regional SES identity inventory first. The same mailbox creates
  only one identity. If absent, set CreateSenderIdentity=true in the reviewed
  SES change set; do not deploy this stack with all identity creation disabled.
  Creating an email identity sends a verification email. The owner must click
  the verification link before sending can succeed. There is no dedicated IP,
  VDM, email archive, custom MAIL FROM or paid sending add-on in this template.
- templates/alert-ses-policy.json: SES SendEmail restricted to this exact sender,
  recipient, account and af-south-1. This is a permission fragment, not a complete
  alert execution role or a CloudFormation template. Merge/review alongside the
  existing runtime role proposal, including DynamoDB stream and failure queue
  permissions. Do not overwrite an execution role with this fragment alone.
- templates/application-functions.json: four remaining functions using existing
  queues/buckets/roles and a versioned package. Functions and event-source
  mappings default disabled. The monthly EventBridge schedule is independently
  disabled through EnableMonthlyReports=false. Enabling consumers does not turn
  on scheduled reports. Its cron is 02:00 UTC / 04:00 SAST on day 1 of the month.
  EventBridge invocation permission, delivery retries, target DLQ and report
  async failure routing are included. Existing ingest is not recreated.
- templates/monitoring.json: 18 OPTIONAL standard-metric alarms: errors/throttles
  for five functions, four DLQ depth alarms, transaction age, alert stream lag,
  RDS CPU and free storage. EnableAlarms=false means none are created. No SNS,
  notifications, automatic remediation, dashboard, custom metric or metric filter
  is created. ActionsEnabled=false is NOT a billing switch: existing alarms can
  still be billed even if their actions are disabled. These are operator-visible
  alarms only; notification destinations are a separate future decision.
- templates/api-shell.json, api.json and cognito.json: existing candidate API and
  Cognito templates copied with source provenance. Cognito Lite/software MFA is
  retained. Optional scope-table point-in-time recovery now defaults off through
  EnableScopeRecovery=false to avoid silently selecting a recurring cost. This
  removes that optional recovery capability until approved. Encryption and
  deletion protection remain. API/auth application code is NOT included here;
  it still needs consolidation with the current app and Linux verification.

## Cost and ownership rules

Do not deploy this folder as an all-in-one stack or automatically enable flags.
Rendering files and the six local tests make no AWS calls and add no AWS cost.
Live services, API requests, log ingestion/storage, emails, DynamoDB, Cognito and
alarms are not promised free. Check actual account credits/eligibility and the
owner's no-new-paid-resource rule before creation or activation. Do not recreate
the removed interface endpoint, NAT gateway or other paid migration path.

Logs for the four new functions retain 14 days and are retained on stack removal.
This preserves evidence; retained logs may continue to incur storage charges.
The monitoring stack must not adopt/recreate those groups or existing ingest logs.
Actual queue names and database identifier must come from verified live outputs.
Existing policies, notification bindings, identities, RDS and financial rows
must be preserved. A template is not proof of live IAM or database grants.

## Commands (local only)

From this folder: `python -m unittest -v test_preparation`, then
`python prepare_services.py`. Both are offline. No --apply path exists.

manifest.json binds rendered outputs by SHA-256. source-provenance.json records
the separate candidate source files used. required-inputs.json lists unresolved
parameters as null; it is an operator worksheet, NOT an AWS CLI parameter file.
Do not invent S3 version IDs, Cognito IDs, DB resource IDs or network identifiers.

## Actual next steps

1. In Amazon SES, af-south-1, inspect Verified identities for the chosen address.
   If absent, review/create the one email identity and complete inbox verification.
   Do not resend verification to an already verified identity unnecessarily.
2. Read SES sandbox/account sending status and current runtime role permissions.
   This preparation has not inspected or changed either. Same sender/recipient
   is suitable for the small sandbox test once verified. No email was sent here.
3. Complete actual inputs and review deployment IAM. The historical ingest-only
   deployer permissions do not establish permission to deploy these new stages.
4. Consolidate current application/auth/migration source; verify Linux archives.
   Resolve quota and establish a cost-compatible live migration path, then verify
   migrations, RDS IAM/TLS and runtime grants before application activation.
5. Use reviewed change sets per resource owner. Verify disabled resources first,
   then activate dependencies in order and retain live end-to-end evidence.

References checked:
https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ses-emailidentity.html
https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-events-rule.html
https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cloudwatch-alarm.html

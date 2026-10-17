# Remaining FinTrust cloud release steps

Account `966467878406`, region `af-south-1`, stage `dev`.
This is an ordered execution checklist, not approval to enable processing or
incur new resource charges. Current service status is in
`service-completion-status.json`; source and live configuration receipts are in
`deployment_iam/evidence/`. Use the prepared templates in this directory.

A separate [manual shared-capacity candidate](shared_manual/README.md) is now
locally verified for individual function checks without reserving positive
slots. It keeps consumers and reports disabled and permits selecting only one
service at a time. AWS accepted the exact template and it is now deployed with all functions
reserved at zero. No test function has been selected; selecting one later
would remove its individual concurrency cap. This does not replace the migration
runner's capacity/security plan or the full integrated-release gates below.

1. **Resolve the capacity gate.** Follow existing AWS Support case
   `179210878300923`. The latest read-back still reports total/unreserved
   concurrency of 10. Obtain AWS's supported minimum target and confirm the
   applied limit before allocating reserved slots. Do not submit 1,001, upgrade
   support or remove throttles as a workaround.
2. **Approve and prove database access.** Follow
   `../PRIVATE_RDS_MIGRATION_PLAN.md` and `../PRIVATE_RDS_RUNNER.md` against the
   consolidated release evidence. The proposed temporary private endpoint has
   a charge and remains unapproved. Do not recreate it under the USD 10 budget
   merely to proceed. Start with the fixed read-only preflight; preserve the
   private RDS instance, existing financial records and administrative recovery.
   Review live schema/owners/grants and the backup gate before migration DDL.
   Then run the bound migration phases and verify each service's IAM/TLS login
   and privileges. Local PostgreSQL rehearsal is not live RDS evidence.
3. **Package staging is complete.** The current archive has SHA256
   `ff6324d64a5d65dab18523a30ea72bb1594d2fa5ca7fbe6b8391c52f03ed589d`.
   Its key is `deployment/lambda/<SHA256>/fintrust.zip` in
   `fintrust-reports-966467878406-af-south-1-dev`, version
   `VZCWpaBXZO9pL2XONICW63qQcH4udM02`. The owner approved upload only; its exact
   downloaded version passed verification and the temporary permission was
   removed. `CodeKey` and `CodeObjectVersion` are now bound in the deployment
   worksheet. Do not re-upload it or substitute the older ingest version.
4. **Completed: four application functions deployed disabled.** The live
   receipt is `shared_manual/application-disabled-live.json`; all four are at
   zero concurrency, both mappings are disabled and the report rule is disabled.
   The following describes the safeguards used: a reviewed CREATE
   change set for `fintrust-application-dev`, explicit resource types and
   Project/Environment tags; use the normal deployer role. Preserve the existing
   ingest stack. Keep `EnableFunctions=false`, `EnableConsumers=false` and
   `EnableMonthlyReports=false`. Verify reserved concurrency zero, disabled
   mappings and disabled monthly rule after creation. Before applying the
   report failure queue policy, read its current policy and preserve unrelated
   statements. Do not use CAPABILITY_IAM or an alternative service role.
5. **Completed: API configuration deployed; runtime disabled.** The existing
   API `qzgzopn8o4` now has a `dev` stage, seven methods, Cognito authorizer,
   exact-source permission to the `dev` Lambda alias and a 30-day access-log
   group. Read-back evidence is `deployment_iam/evidence/api-configuration-live.json`.
   The registered `/dev/` callback is preserved. All functions remain at zero
   concurrency. No traffic was sent; browser access, authorization, scoped
   retrieval and log delivery remain untested. The initial tagging failure was
   rolled back normally, the exact stage-tag scope corrected, and temporary
   empty-log cleanup permission removed and verified. The stage is configured
   but does not yet provide a working application.
6. **Align ingest with the release, then enroll approved test identities.** The
   saved ingest template references the earlier deployment artifact. A disabled,
   code-key-only proposal is in `ingest_release/`; it preserves the saved
   resources and binds the already verified consolidated package/version.
   Freshly read the live ingest template and runtime policy, validate the
   proposal, and review its exact UPDATE before applying it. This offline
   proposal changes no live resource or notification. Then configure each required Cognito
   identity, its one approved group, software MFA and approved account scopes.
   No identities or scope records have been created by preparation. Use real
   approved cloud account IDs; do not copy local account assignments blindly.
   Include allowed retrieval, unauthenticated denial and cross-account denial
   in step 7's tests.
7. **Run controlled service and end-to-end checks.** Only after the preceding
   gates pass, allocate approved capacity and enable dependencies deliberately.
   Keep the raw S3 notification disconnected until downstream checks succeed.
   Use an approved small test batch, preserve source versions and correlation
   IDs, and check the outcomes below. Snapshot evidence must distinguish local
   tests from AWS execution. Technical failures stop further activation.

| Service path | Evidence required before completion |
| --- | --- |
| Ingest / SQS / scoring | Accepted, quarantined and duplicate outcomes reconcile; retries create no duplicate financial rows; FIFO failure/retry behavior is verified |
| RDS / DynamoDB / API | Stored transactions and risk projections agree; authenticated users see only assigned accounts; no public database exposure |
| SES | Alert Lambda delivers to the verified test mailbox with a recorded SES outcome; retries and uncertain-delivery handling preserve deduplication |
| Reports / EventBridge | One controlled report has correct currency/date grouping and S3 output; rule target, retries and DLQ permissions are verified |
| CloudWatch / failures | Actual function/API logs are readable with intended retention; failure queues and correlation IDs support diagnosis without secrets |

Keep scheduled reports disabled after a manual test unless explicitly required.
The 18 optional CloudWatch alarms remain undeployed pending cost approval;
disabling alarm actions would not remove their potential charge. Do not create
an empty monitoring stack to count monitoring as complete. Any temporary
migration resources need the recorded same-session cleanup and deletion checks.

The latest read-only safety receipt confirms healthy network/auth/API stacks,
the reviewed live network template, zero ingest reserved concurrency, no raw
bucket notification before the API stage was configured. The later API receipt
confirms the dev stage with all functions still at zero. It does not prove migration readiness,
current support correspondence, application operation or future cost coverage.

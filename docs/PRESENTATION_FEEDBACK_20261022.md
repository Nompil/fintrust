# Presentation feedback: verified cloud release

Verified on 22 October 2026, with final cloud/cleanup checks at 11:35:55 UTC (13:35:55 SAST). [Open the Workbench](https://qzgzopn8o4.execute-api.af-south-1.amazonaws.com/dev/). Detailed receipts are in [the cloud evidence directory](EVIDENCE/14-presentation-feedback-2026-10-22/).

Deployed source: `fc7875589edf17a086534ee9a1b4fdb32f1de009`. Artifact SHA256: `1c744305df7f5c8c60c5ac87a3fd2331f7799bcf7a1579c48013b6cbd99c96f0`. Documentation-only commits may follow this runtime source version.

## Source integrity and quarantine

Original files, source evidence and accepted transaction values remain unchanged. Analysts can append source-review notes or reject a quarantined row with a reason. The API denies legacy `RESUBMIT` actions, the worker refuses `manual-correction` envelopes, and the correction-outbox drainer is paused. Existing correction history remains readable as historical evidence; pending legacy correction entries are not automatically executed.

Replacement values must arrive through a new source-system file and pass ordinary validation, identity and duplicate checks. A quarantine outcome can indicate missing context, an unsupported value or a validation problem; it does not establish fraudulent activity. The quarantine report is separate from the accepted-ledger report, uses the existing account/ownership permissions, and excludes raw payloads and storage keys. Its date filter is the time the row was quarantined, in South African calendar time.

Each upload's processing detail includes an exact partition of accepted Low, Medium, High and unassessed rows, quarantined rows, duplicate rows, technical failures and pending rows. A completed ten-row synthetic example is eight Low, one High and one quarantined. No score is invented for quarantined or unassessed rows. Existing scoring weights and boundaries are unchanged.

Evidence: `tests/test_immutable_quarantine.py`, `tests/test_source_row_reports_pg.py`, `tests/test_owned_unknown_quarantine.py`, `tests/test_evidence_continuity.py`, `tests/test_transaction_lifecycle.py`, and browser journey checks under `tools/verify_*`.

## Sign-in and data loading

Access and refresh tokens stay in memory. Requests share one refresh operation before access-token expiry. Logout invalidates in-flight refreshes; transient network errors do not silently convert into logout. A failed DynamoDB authorization-store read denies access with a temporary-service response rather than incorrectly reporting an invalid password/session. A page reload can return through the existing Cognito SSO session using PKCE. Only a non-secret signed-in marker is stored in session storage; tokens and passwords are not stored there. Revoked or expired refresh credentials still require sign-in.

Overview and insight aggregates omit per-row source enrichment. Related metadata reads share a defensive request-only cache, and unknown-account ownership queries inspect only candidate batches. Identity grants are not cached across requests. Read snapshots reuse one read-only database connection; charts no longer request an extra review-queue page for data already in the overview response. These changes reduce avoidable work; they are not a live latency guarantee.

Evidence: `tools/test_cloud_session.cjs`, `tests/test_cognito_auth_browser.py`, `tests/test_request_evidence_cache.py`, `tests/test_dashboard_read_session.py`.

## Admin user creation

The cloud Admin form accepts username, display name, invitation email, application role, assigned accounts and a reason. It never accepts passwords. Cognito generates the invitation, forces the user's password change and applies the existing pool MFA policy. The initiating Admin must still be active, belong to Administrators and grant only accounts within their own scope.

The isolated provisioning Lambda uses the existing authorizer, user pool and scope table. It has no VPC, database, Secrets Manager or IAM permissions. Durable request receipts and username reservations prevent replays from creating another user or resending an invitation. Partial or uncertain outcomes require reconciliation; an accepted invitation request does not prove mailbox receipt. The directory is bounded at 100 users.

Infrastructure generator: `infrastructure/user_administration.py`. New resources include the Lambda, scoped execution role, retained encrypted on-demand request table, fourteen-day log group and protected API methods. These have usage costs; no NAT or interface endpoint is added. The function defaults to zero concurrency until explicitly enabled.

Evidence: `tests/test_cloud_user_creation.py`, Admin scenarios in `tests/test_cognito_auth_browser.py`.

## Completed release verification

The [Linux CI run](https://github.com/Nompil/fintrust/actions/runs/39766764595) passed 1,181 pytest cases with zero failures, errors or skips. Five token-session checks and the separate candidate browser gate also passed. The packaged code was bound to the exact source commit and imported on Linux x86_64 / CPython 3.12, with all production modules checked and no external I/O during the import probe. Mocked AWS/isolated SQL tests are distinct from the real cloud checks below.

The application, ingest and API stacks reached `UPDATE_COMPLETE`. All six functions, including the isolated Admin function, were active on the same verified artifact and used shared regional capacity. The API alias was verified against that artifact. No database migration or paid network endpoint was introduced; the support plan and regional quota were unchanged.

A disposable synthetic Analyst completed the real Cognito MFA login, obtained a fresh token through the refresh flow, and returned through existing Cognito SSO using a new PKCE authorization code. Live API reads verified stored rows, Overview, Insights, quarantine reporting and batch reconciliation. The legacy value-editing request returned 403 and the original evidence was unchanged. An Analyst was denied the Admin provisioning route.

In that read check, Overview took 0.898 seconds and Insights 0.460 seconds. The first session request took 3.584 seconds. These are single observed requests, not a production latency or load guarantee.

The labelled file `SYNTHETIC-FEEDBACK-20261022-1c49c074.csv`, batch `a9466354-b62c-53b6-94b6-f2a60f64295f`, completed the real cloud intake/queue/scoring/storage journey. It added nine fictional accepted transactions and one quarantine case. Eight records scored 0/Low; the cross-border amount of 200000.01 ZAR scored 55/High (40 amount points plus 15 cross-border points), under `fintrust-r2-rules-2026-10-13`. The exact partition was ten received, eight Low, one High and one quarantined, with zero pending, duplicate, unassessed or technical-failure rows. Existing transaction values were not edited. This file is retained evidence of an already processed test, not a new demonstration upload.

The synthetic quarantine case accepted one append-only note; an identical note replay created no duplicate. Rejection preserved its original values and evidence version, and the separate quarantine report returned the rejected case. Its processing outcome remained quarantined; no amended transaction was submitted.

A disposable synthetic Admin used the protected live API to create `nompilo-auditor` as a read-only Auditor for ACC-0001, with the owner's approved Outlook invitation. Cognito accepted the invitation request, the group and active scope were verified, and the account was in `FORCE_CHANGE_PASSWORD`. Replaying the same request returned its durable result without another invitation. Temporary test identities were removed; the auditor account remains for the owner.

The deployment encountered missing exact-function/previous-artifact permissions for ingest and a missing read-only role lookup during Admin activation. Each rollback was inspected and completed without skipping resources, then a newly reviewed retry succeeded. The temporary policy and all its versions were deleted, restoring exactly the original nineteen deployer attachments. The permanent new Lambda role retains only its required workforce-provisioning permissions.

## Access and remaining boundaries

Refresh the Workbench once to load the new browser code. Use the existing `nompilo` administrator or `nompilo-analyst` credentials. Administrators can open **Administration → Add User**. Processing History contains the per-file row summary. Reports offers a separate quarantined-source-row dataset and exports the authorized current page.

The new auditor's mailbox receipt and first sign-in have not been confirmed. The owner must use its own invitation, choose a password and enroll MFA. No passwords or tokens appear in this evidence. Existing real-user passwords were not changed.

Serverless cold starts and the existing shared quota of ten remain operational constraints; this release is not a production load certification. The synthetic High record can trigger the previously configured alert route, but this release does not claim mailbox placement or alert-delivery confirmation. Cloud creation is available in the Admin UI; existing cloud-user changes/disable operations remain operator-controlled. Historical corrections remain readable, while new manual value resubmissions and pending correction draining stay disabled.

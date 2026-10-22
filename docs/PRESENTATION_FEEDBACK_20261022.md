# Presentation feedback: implementation and release gates

Date: 22 October 2026. This record describes the candidate branch, not a live deployment receipt.

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

## Required before claiming live completion

1. Complete the regression and browser suites against a disposable PostgreSQL database; retain dated results tied to the release commit.
2. Verify that exact commit on Linux and package the tested release.
3. Read the current AWS state; review the specific CloudFormation change set, scoped permissions and costs. Create a new API deployment snapshot for the additional routes.
4. Update the application and gateway through the reviewed release process. Do not enable legacy correction processing or change regional quotas/support plans.
5. Verify cloud login and refresh, scoped Admin creation, immutable quarantine review/reporting, row-summary reconciliation and an explicitly synthetic transaction journey. Check permissions before relying on new S3 note paths.
6. Record actual cloud results and outstanding limits. Prior deployment receipts do not prove these candidate changes are live.

No infrastructure or application database change is performed by the local regression tests.

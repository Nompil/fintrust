# Cloud demonstration

Application: https://qzgzopn8o4.execute-api.af-south-1.amazonaws.com/dev/

Use **Sign in with Imbokodo**. The administrator username is **nompilo**, and the analyst username is **nompilo-analyst**. Both invitations reached the owner's mailbox. The owner subsequently chose personal passwords in a private terminal; the original temporary invitation passwords are no longer the login passwords. The owner confirmed that the analyst username and stored transaction rows are visible in the cloud app. Mandatory authenticator MFA is configured on Cognito. Keep passwords and MFA codes out of project files and chat. Sign out at the end of the demonstration. Tokens are held in browser memory, so refreshing the page can require signing in again.

Current checkpoint: cloud API authentication, real owner analyst login, ingestion, ledger storage, scoring, SES acceptance, review decisions, correction recovery and an actual EventBridge report run passed. Final live configuration read-back passed. The corrected fictional row was processed through EventBridge and raised the cloud ledger from three to four transactions. Temporary paid endpoints and master-secret access were removed. Temporary repair stacks, the dependency layer, setup IAM roles and temporary operator credential caches have been removed. Audit logs, artifact versions and the live application are preserved.

## Demonstration path

1. Open Overview, then Transactions to see the stored ledger. Cloud demonstration accounts and transactions are fictional; the preserved local ledger was not copied into AWS.
2. Open Risk Events. High risk uses red text and a red score bar. Open an investigation, claim it, add a note and record an appropriate decision.
3. Open Processing History to inspect the upload's accepted, quarantined and duplicate row counts. Pending means rows whose final processing outcome has not yet been recorded; it is separate from a review awaiting investigation.
4. Open Quarantined Rows. Inspect the original source evidence before submitting a correction. The EventBridge recovery worker runs every minute; a correction can take a little longer than one tick.
5. Open Review Queue. SLA is the review's configured deadline. Due soon and overdue are calculated against that deadline; an overdue review is still available for investigation. Historical demonstration timestamps can already be overdue.
6. Inspect the generated October CSV/JSON report in the existing reports bucket under `monthly/2026-10/`. An actual EventBridge invocation generated the verified report. That report is a three-transaction snapshot generated before the correction; the live ledger now has four transactions. The original monthly schedule is enabled for 02:00 UTC on the first of each month. The report is a point-in-time export, not a live ledger view.

The live evidence distinguishes SES accepting a message from confirmation that it reached the recipient's inbox. Built-in SES account counters recorded two sends and two receiving-server deliveries with no bounces or rejections, and the recipient is not currently suppressed. These aggregate counters do not prove per-message Inbox placement. The owner reported no transaction alert email. Search all Outlook folders for the subject `FinTrust high-risk transaction`; both sender and recipient are the owner's Outlook address. DKIM signing is not configured for that email-address identity, and no per-message delivery-event destination was configured for those original sends.

Cloud user provisioning remains an AWS operator workflow. The cloud administrator user-management view is read-only; it cannot create Cognito users. Clearer future invitation wording has passed AWS template validation but has not been applied to the live user pool. Current users should use their privately chosen personal passwords rather than the old invitation passwords.

## Capacity and cost

The application uses the existing regional Lambda concurrency quota of 10 through shared capacity. This supports a controlled demonstration, not a claim of production load capacity. API throttling and a maximum of two SQS processing invocations limit bursts. The quota support case remains separate from the demonstration.

The AWS account and Basic Support plan must remain unchanged. The $10 budget sends alerts; it is not a hard spending cap. Existing database/storage/log resources can still consume credits or incur charges. Temporary database setup endpoints must be removed; the final cleanup evidence records removal.

## Stop after the presentation

Do this after the owner confirms the presentation has finished, not before submission or Monday's demonstration:

1. Disconnect the reviewed raw S3 notification to stop accepting new ingestion events.
2. Disable `fintrust-outbox-dev` and `fintrust-monthly-dev` EventBridge rules and both event-source mappings. Check for in-flight work before stopping functions.
3. Set reserved concurrency to zero for the five `fintrust-{api,ingest,scoring,alert,report}-dev` functions. The application will become unavailable.
4. Stop `fintrust-ledger-dev` without deleting it, its snapshots or ledger. RDS stops are temporary and AWS can restart the database after seven days. Schedule a follow-up review before that point.
5. Check for remaining interface VPC endpoints, NAT gateways and other hourly resources. Preserve the S3 gateway and DynamoDB gateway configuration unless performing a reviewed teardown.
6. Preserve ledger evidence, S3 object versions, DynamoDB records and audit logs. Storage and backups can still cost money while compute is stopped. Permanent deletion requires a separate, explicit retention and teardown decision.

Use the deployment configuration as the source of truth when disabling resources so that future CloudFormation updates do not accidentally re-enable processing. Do not purge queues or delete financial records to reduce costs.

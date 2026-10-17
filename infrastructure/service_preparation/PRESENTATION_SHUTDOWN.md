# Presentation environment shutdown checklist

Owner timeline: submission Sunday **18 October 2026**; presentation Monday
**19 October 2026**, South African time. Presentation end time is not yet known.
Do not stop the environment before the presentation or treat this document as
an instruction to delete financial records. Basic Support must remain unchanged.

Temporary migration/preflight endpoints and operator privileges must be removed
at the end of their bounded session, rather than left until the presentation.

After the owner confirms the presentation has ended:

1. Capture the deployed commit, stack outputs, sanitized E2E evidence and ledger
   reconciliation/counts. Record all pending queue work and in-flight operations.
   Preserve the private RDS ledger, local ledger, source objects and evidence.
2. Disable raw S3 delivery, queue/stream mappings and EventBridge schedules through
   reviewed stack changes. Drain or explicitly reconcile in-flight work; do not
   purge queues or discard work to obtain an empty dashboard.
3. Return every application function to reserved concurrency zero, verify the
   disabled state, and remove the public API stage through a reviewed API stack
   change. Merely throttling Lambda leaves an API endpoint which can still receive
   billed requests. Preserve the code, configuration and stable API identity if a
   later demonstration is needed.
4. Verify that no temporary interface endpoint, NAT, migration runner, operator,
   invocation grant, bootstrap secret permission or orphan Lambda ENI is left.
   Preserve gateway endpoints and the existing protected network.
5. Stop RDS only after confirming no migration, transaction or required operation
   remains active. Record its actual stopped state. Stopping preserves the data
   but **RDS automatically restarts after seven days**, and storage/backups still
   incur charges. Review or remind before that restart; stopping once does not
   provide indefinite zero-cost archival.
6. Review remaining storage, retained logs, snapshots, Secrets Manager and KMS
   resources against the budget. Keep notifications active. Do not delete the
   database, its managed secret, encryption keys, ledger objects or backups under
   a generic instruction to stop services. Permanent archival/deletion requires a
   separate, concrete data-retention decision and verified recoverability.
7. Save a final receipt of actual state, residual recurring costs and any scheduled
   restart/reminder. Do not claim the account is cost-free merely because compute
   is stopped. Leave Basic Support unchanged.

Sources: [RDS temporary stop and automatic restart](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html),
[RDS stopped-instance storage and backup charges](https://aws.amazon.com/blogs/database/implementing-db-instance-stop-and-start-in-amazon-rds/).

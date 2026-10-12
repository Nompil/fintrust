> Archived historical narrative. Current project authority: [Master PDF](../../FinTrust_Project_Master.pdf); current status: [Progress PDF](../../FinTrust_Project_Progress.pdf). Original assumptions below are not deployment instructions.

# Week 13 Day 3: Ingest Resilience and Monitoring

## Failure Boundaries

| Failure | Handling | Expected operational result |
|---|---|---|
| Invalid CSV row | Store the row and reason as JSON Lines under `quarantine/`; continue with valid rows | The file partially succeeds and the log reports received, valid, and quarantined counts |
| Database integrity violation | Retry rows individually inside savepoints; quarantine rejected rows | Good rows remain committed; rejected rows are traceable |
| RDS connection or other database infrastructure failure | Roll back and re-raise | Lambda's asynchronous retry policy retries the invocation; exhausted events go to the SQS DLQ |
| S3 read/access failure or malformed event | Log structured failure and re-raise | Lambda retry/DLQ path preserves the failed event for investigation |
| CSV too large for one Lambda invocation | Split before upload, or orchestrate chunk processing with Step Functions | Avoid relying on Lambda's 15-minute maximum or loading an unbounded file into memory |

The S3 trigger invokes Lambda asynchronously. `infrastructure/sqs/configure_ingest_dlq.py` configures two retries and a standard SQS dead-letter queue. Transaction IDs are deterministic for a source object version and row number, and inserts use `ON CONFLICT DO NOTHING`, so replaying an event does not duplicate successfully loaded rows.

## Metrics and Alarms

Each successfully processed source file emits one JSON log event containing `rows_received`, `rows_valid`, `rows_quarantined`, `quarantine_rate_percent`, `bucket`, `s3_key`, and `duration_ms`. Failed invocations emit an `ingest_failed` JSON event and are re-raised.

`infrastructure/monitoring/configure_ingest_monitoring.py` creates:

- A CloudWatch Logs metric filter for files where `quarantine_rate_percent > 5`.
- An alarm for any such file in the alarm window.
- An SQS alarm when `ApproximateNumberOfMessagesVisible` on the ingest DLQ is greater than zero.

Lambda `Errors`, `Duration`, `Throttles`, and concurrency metrics are provided by AWS. These scripts configure log filters and alarms, but do not create a visual CloudWatch dashboard.

## Recovery

After the underlying dependency is healthy, inspect DLQ event bodies and CloudWatch logs before replay. Use `python infrastructure/sqs/replay_ingest_dlq.py` to resubmit an original S3 event to the ingest Lambda. The tool deletes a DLQ message only after Lambda accepts the asynchronous invocation (HTTP 202); the Lambda's configured retries and DLQ still handle a replay that fails again.

## Operational Checks

1. Upload one valid CSV and verify all rows load.
2. Upload a mixed-validity CSV and verify invalid rows are quarantined while valid rows load.
3. Temporarily test with an unavailable database only in a controlled test environment; verify the invocation is retried and eventually appears in the DLQ.
4. Confirm the quarantine-rate and DLQ alarms enter ALARM for their respective test cases.
5. Restore dependencies, replay the DLQ message, and verify the transaction count does not increase for rows already committed.

`rows_valid` counts accepted rows, including rows already present on replay; it is not a count of newly inserted records. Quarantine keys derive from source identity/version to avoid collisions between files with the same basename. Multiple event records are processed sequentially; a later failure retries the event, so earlier files rely on idempotent inserts.

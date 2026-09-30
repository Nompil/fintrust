# Week 13 Days 1-3 Infrastructure and Data Layer

These scripts create AWS resources when explicitly run. Do not run them until the AWS account, region, cost controls, and credentials have been checked. No deployment is performed by the project tests.

## Prerequisites

This is an incomplete provisioning sequence. Before deployment, add the Day 1 customer-managed KMS configuration, separate access-log bucket, private VPC/service access, SQL grants and required Lambda VPC permissions. See `project-reference/requirements_day1_day3.md`. The current S3 script alone does not satisfy the Day 1 security checklist.

- Python 3.11 (use the same runtime targeted by the Lambda functions)
- Install dependencies from the repository root: `python -m pip install -r requirements.txt`
- AWS CLI credentials configured for a non-production learning account
- Set `AWS_REGION=af-south-1`
- Check the account billing alarm before creating resources

## Day 1: S3, IAM, SSM, and trigger

1. Choose a globally unique bucket name and set `FINTRUST_INGEST_BUCKET`.
2. Run `python infrastructure/s3/create_ingest_bucket.py`.
3. Set `FINTRUST_DB_HOST`, `FINTRUST_DB_NAME`, `FINTRUST_DB_USER`, and `FINTRUST_DB_PASSWORD` in the current shell, then run `python infrastructure/ssm/put_parameters.py`. The password is stored as `SecureString`; never commit it or place it in this document.
4. Run `python infrastructure/iam/create_roles.py` after setting the intended resource names. IAM changes are account-level and should be reviewed before execution.
5. Deploy the `fintrust-ingest` Lambda before running `python infrastructure/s3/add_event_trigger.py`. The function must use the role created for it and be in the same region as the bucket.

The bucket script enables versioning, blocks public access, and moves objects under `raw/` to Glacier after 90 days with expiration after 2,555 days. Confirm the retention period against the bank's approved policy before production use.

## Day 2: PostgreSQL and DynamoDB

1. Create the PostgreSQL database in private subnets and allow inbound port 5432 only from the Lambda security group.
2. Run `sql/schema.sql`, then `sql/seed.sql` using a PostgreSQL client connected to the database.
3. Run `python infrastructure/dynamodb/create_risk_scores.py` to create the on-demand `risk_scores` table and enable TTL on the `ttl` attribute.
4. Use `samples/transactions_day2.csv` as a local test fixture. Its account UUIDs correspond to the deterministic account IDs in `sql/seed.sql`; the negative amount and unsupported currency should be quarantined.
5. Upload a test CSV to `s3://<bucket>/raw/` only after deploying the Lambda and configuring its S3 trigger.

## Day 3: DLQ, Monitoring, and Read API

1. After the ingest Lambda exists and its role has been updated with `sqs:SendMessage` permission on the intended DLQ ARN, run `python infrastructure/sqs/configure_ingest_dlq.py`.
2. Run `python infrastructure/monitoring/configure_ingest_monitoring.py` to create the quarantine-rate metric filter and DLQ/quarantine alarms.
3. For local API development, copy `.env.example` to `.env`, configure a local database and DynamoDB endpoint/table, install dependencies, and run `python -m fintrust.api`.
4. Configure API Gateway routes separately: `GET /v1/transactions` and `GET /v1/insights` use AWS_IAM authorization; `GET /v1/health` returns status only.
5. To recover DLQ events after fixing the dependency, inspect the message and logs, then run `python infrastructure/sqs/replay_ingest_dlq.py`. It deletes a DLQ message only after Lambda accepts the asynchronous invocation.

Large CSVs must be split before upload or orchestrated with Step Functions; the current implementation reads each CSV into memory and should not be used for unbounded file sizes.

## Verification checkpoints

- Inspect bucket versioning, public access block, and lifecycle configuration in the AWS console.
- Confirm the Lambda role contains only reviewed actions for the needed resources.
- Confirm the S3 notification is restricted to `raw/` keys ending in `.csv` and Lambda permission includes the bucket ARN and account.
- Confirm `/fintrust/dev/db_password` is a `SecureString` and is not in Git.
- Confirm PostgreSQL CHECK constraints reject invalid amount/currency/type values.
- Confirm `idx_tx_account_date` appears in `EXPLAIN ANALYZE` when the table has enough representative rows.
- Confirm `risk_scores` is `ACTIVE`; write/read an item with `account_id`, `score_date`, and a TTL timestamp.
- Confirm the Lambda async retry count is two, the ingest DLQ receives failed events, and the DLQ alarm fires.
- Confirm the metric filter emits `FilesOverQuarantineThreshold` when a file's quarantine rate exceeds 5%.
- Run `python -m pytest tests/data_quality/test_constraints.py -q` against a disposable PostgreSQL database.
- Run `python -m pytest -q` for the local validation suite. Tests do not create AWS resources.

## Important design boundary

The Week 13 Day 2 exercise loads validated rows directly from ingest Lambda to RDS. The overall capstone brief later introduces SQS FIFO and a separate scoring Lambda. Keep that change as a clearly documented next phase; do not claim the SQS path is running until it is implemented and deployed.

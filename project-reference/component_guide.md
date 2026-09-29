# FinTrust Component Guide

This guide is for understanding the system, not memorising a pitch. For every component, learn its responsibility, inputs, outputs, failure behavior, and whether it is working code or only a planned part of the final architecture.

## 1. Keep the Two Architectures Straight

### Implemented code path (not yet deployed to AWS)

```text
CSV object in S3
  -> S3 notification invokes ingest Lambda
  -> ingest reads and parses the CSV
  -> invalid rows go to S3 quarantine
  -> valid rows are inserted directly into PostgreSQL
  -> structured completion/failure logs go to CloudWatch
```

The Flask API is implemented for local use. It reads transactions from PostgreSQL and scores from DynamoDB. The infrastructure scripts for the ingest DLQ and alarms exist, but have not been run in AWS.

### Final capstone target path

```text
S3 -> ingest Lambda -> SQS FIFO -> scoring Lambda -> RDS + DynamoDB
                                                   -> alerting/API/reporting
```

The current ingest Lambda does **not** send valid rows to SQS. The scoring function is not connected to ingest and does not persist scores. Do not describe that target flow as deployed or end-to-end working until you implement and verify it.

## 2. Components by Responsibility

| Component | What it does | Current status |
|---|---|---|
| `config.py` | Loads local `.env` values and AWS settings. For database values not supplied through environment variables, reads SSM Parameter Store with decryption; caches settings during a warm Lambda runtime. | Implemented; AWS parameters/profile not configured here. |
| `db.py` | Opens a PostgreSQL connection, executes parameterized reads, converts rows to dictionaries, rolls back query exceptions, and closes the connection. | Implemented; opens a new connection per call, no pool/RDS Proxy yet. |
| `dynamo.py` | Creates a reusable module-level DynamoDB resource and provides put/get/query helpers. | Implemented; score writer is not integrated. |
| `models.py` | Defines `Transaction` and `RiskScore` dataclasses for typed data representations and conversion. | Present, but current ingest/API path does not use these models. |
| `validators.py` | Contains a general transaction validator plus a sample risk-score calculation/classification. | Present, but `ingest.py` currently uses its own schema-specific `validate_row`; risk scoring is not called during ingest. |
| `ingest.py` | Reads the S3 event/object, checks CSV fields and values, transforms rows, writes valid transactions to RDS, quarantines invalid/constraint-failing rows, logs counts, and re-raises infrastructure failures. | Main implemented processing path; not deployed. Direct-to-RDS, not FIFO. |
| `score.py` | Calculates a risk score and returns approve/hold metadata. | Skeleton: not connected to queue, does not store to DynamoDB, and currently expects each SQS `body` to already be a dictionary even though SQS normally supplies a JSON string. |
| `alert.py` | Represents the intended compliance alert behavior. | Placeholder: returns a simulated result; does not call SES. |
| `query.py` | Builds parameterized transaction SQL and looks up a risk-score item by account/date. | Implemented data-access functions. |
| `api.py` | Exposes `/v1/health`, `/v1/transactions`, and `/v1/insights`; validates inputs and serializes responses. | Implemented locally with Flask/aws-wsgi. API Gateway routes/auth are not deployed. |
| `report.py` | Represents monthly reporting entry point. | Placeholder: returns zero-valued summary; no SQL report, CSV/JSON output, S3 write, or EventBridge schedule. |

## 3. Follow One Row Through Ingest

Use `samples/transactions_day2.csv` and trace one line at a time.

1. **S3 event:** AWS includes the bucket and object key. The handler URL-decodes the key and requests the specific object version when available.
2. **CSV parse:** `csv.DictReader` reads the header and turns each row into a string dictionary. Missing required headers fail the invocation because the file shape is unusable.
3. **Row validation:** `ingest.validate_row` checks `account_id`, `amount`, `tx_date`, `tx_type`, currency, UUID format, and transaction type. A negative/non-finite amount or unsupported currency is row-invalid, not a reason to discard other rows.
4. **Transformation:** amount becomes `Decimal`, date becomes a timezone-aware `datetime`, account ID is normalized as a UUID, country becomes the `cross_border` flag, and the raw S3 key is kept for traceability.
5. **Idempotency:** a deterministic UUID is derived from the source object identity/version and CSV row number. Re-delivery of that same object row produces the same transaction ID. `ON CONFLICT (tx_id) DO NOTHING` avoids duplicating an already-inserted row.
6. **Database write:** rows are batch inserted. If PostgreSQL reports an integrity violation, the code retries rows individually in savepoints so one bad foreign key does not discard all valid rows. A connection/infrastructure failure is rolled back and raised for Lambda retry handling.
7. **Quarantine:** invalid rows and row-level database constraint failures are written as JSON Lines under the S3 `quarantine/` prefix with an error reason and source information.
8. **Operational log:** a successful file emits counts and duration, including `rows_received`, `rows_valid`, `rows_quarantined`, and `quarantine_rate_percent`. An invocation-level error emits `ingest_failed` and is re-raised.

For the supplied sample CSV, the positive-amount ZAR transactions are structurally valid; the negative amount and JPY currency rows should be quarantined. A UUID can still fail at the database if it is not an existing account.

## 4. Database and NoSQL Responsibilities

### PostgreSQL

The normalized ledger stores `customers -> accounts -> transactions`. `risk_events` and `alerts` separately record investigations and notifications. PostgreSQL is appropriate for foreign keys, constraints, joins, and reporting. `NUMERIC(15,2)` is used for money to avoid floating-point rounding.

### DynamoDB

`risk_scores` is designed with partition key `account_id` and sort key `score_date`, matching a read pattern like “get this account's score for this day.” TTL is for automatic expiry of old operational scores; it is not a substitute for an approved financial-record retention policy. The setup script exists; the score-writing pipeline does not yet.

## 5. API Components

- `GET /v1/health` performs `SELECT 1`; it reports service health, not customer data.
- `GET /v1/transactions` requires an account UUID, optionally filters dates, caps results at 500, and returns rows from PostgreSQL.
- `GET /v1/insights` requires an account UUID, defaults the date to today, and reads `{account_id, score_date}` from DynamoDB. It returns 404 if no score exists.
- Flask validates and routes requests; `query.py` performs data access. In AWS, API Gateway should enforce AWS_IAM for data routes. That gateway policy is not implemented here.

## 6. Monitoring and Failure Handling

- **Invalid row:** quarantine that row; continue the file.
- **Database integrity failure:** isolate the bad row with savepoints; quarantine it.
- **RDS unavailable / S3 read failure / broken event:** log and re-raise so Lambda async retries can occur.
- **Retries exhausted:** the configured Lambda DLQ script targets a standard SQS queue. This is for failed asynchronous Lambda invocations, not the later SQS FIFO transaction-processing queue.
- **CloudWatch metric filter:** counts files with quarantine rate over 5%; alarms exist as provisioning code, not deployed resources.
- **Large file:** current handler reads the object into memory and runs in one Lambda invocation. Split files or implement Step Functions/chunking before claiming support for very large files.

## 7. SQL Artefacts and What They Demonstrate

- `schema.sql`: entities, relationships, check constraints, and indexes.
- `seed.sql`: synthetic records to exercise joins and reports; these are not real customer records.
- `risk_report.sql`: identifies accounts with more than three high-risk events in a rolling 30-day period.
- `monthly_summary.sql`: uses a window function to calculate a running signed balance.
- `views.sql`: abstracts account summary fields for a reporting/API consumer.
- `procedure.sql`: flags an account by creating a risk event from its latest transaction and updating account status atomically.

Know the difference between application validation and database constraints: application validation gives an understandable quarantine reason; database constraints are the final integrity boundary if invalid data bypasses application code.

## 8. How to Study Each Component

For each session, use this loop:

1. Trace one input through the code and name the output.
2. Explain why the component exists and what would break if it were removed.
3. Trigger or inspect one failure case and state whether it is quarantined, rolled back, retried, or returned as an API error.
4. Run the narrow test for that component.
5. Explain the result in your own words without reading this guide.

Suggested order: schema and seed data -> one ingest row -> failure/quarantine path -> DLQ/monitoring -> API health and transaction read -> DynamoDB insight read -> scoring integration -> SES/reporting -> AWS deployment.

## 9. Teach-Back Questions

You should be able to answer these before moving on:

1. Why does the ingest handler return/raise on an infrastructure failure but continue after a bad row?
2. How does the deterministic transaction ID make retries safer?
3. Why do we use PostgreSQL for the ledger and DynamoDB for account/date score lookup?
4. What exactly does the API Lambda read, and what permissions should it never have?
5. What is the difference between the ingest DLQ and the planned FIFO work queue?
6. Which components are implemented locally, which are AWS provisioning scripts, and which are still placeholders?
7. What evidence would prove that a service is deployed rather than merely described in a diagram?

Use [remaining_work.md](remaining_work.md) to turn any “not yet implemented” answer into the next engineering task. The goal is to understand and verify each choice, not to memorize a polished answer.

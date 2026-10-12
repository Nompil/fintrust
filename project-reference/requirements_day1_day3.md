> Supporting source retained for traceability. Use [Project Master](../docs/FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](../docs/FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

> Historical reference retained in place. Some implementation/status descriptions are superseded. Use the [current canonical guide](../README.md) and [documentation inventory](../README.md) for current behavior and proposed disposition. No archive or deletion has occurred.

# Requirements and build review

Reviewed 30 September 2026 against the eight supplied documents and the pasted Day 3 PM API lesson. This is the current requirements record. Older daily-log entries record history, not current readiness.

## What you are building

FinTrust receives a CSV of bank transactions, checks each row, saves valid records, and lets a reviewer retrieve them. Later stages will calculate risk, send alerts, and generate reports. The project uses synthetic data and does not move money or make real compliance decisions.

## Day 1 to Day 3

| Day | Required outcome | Repository evidence | Still needed |
|---|---|---|---|
| 1 AM | Explain compute choice; AWS architecture; S3 versioning, customer-managed KMS encryption, access logs and retention; scoped roles | Architecture and IAM documents; editable diagrams | KMS/key policy, access-log bucket, network design and deployed evidence |
| 1 PM | Provision S3, roles, SSM parameters and filtered S3 trigger | `infrastructure/s3`, `iam`, `ssm` | Run against the approved account after closing security/network gaps |
| 2 AM | Validate CSV, transform types, insert valid rows, quarantine invalid rows | `fintrust/ingest.py`; ingest/regression tests | Real S3-to-RDS demonstration; 1 MiB/5,000-row bounds implemented locally |
| 2 PM | Customers/accounts/transactions schema, constraints, indexes, view; DynamoDB account/date key and TTL | `sql/`; DynamoDB script and helper tests | Local database tests passed; index plan evidence and deployed table/TTL verification remain |
| 3 AM | Row isolation, retries, DLQ, JSON counts and duration; quarantine-rate and DLQ alarms | Ingest code; SQS and monitoring scripts | Trigger actual failure, alarm, replay and duplicate-safety evidence |
| 3 PM | Health check; paginated transaction reads; account/date insights; 400/404 responses | Flask API and tests; `limit`/`offset` pagination | Local database/API tests pass; deployed API evidence and measured insights latency below the lesson's 50 ms target remain |

Code present, local test passed, AWS deployed, and end-to-end demonstrated are four different states. None implies the next.

## Conflicting instructions and working decisions

| Conflict | Decision for this milestone |
|---|---|
| Pre-build plan says FastAPI/SQLAlchemy; Day 3 lesson says Flask/psycopg2 | Keep Flask/psycopg2, matching the detailed lesson and working package. Do not maintain two APIs. |
| Suggested `src/` folders versus the brief's `fintrust/` package | Keep the existing package; do not duplicate it under `src/`. |
| Overall schedule puts API work on Day 5; supplied detailed lesson puts it on Day 3 | Use the supplied Day 1-3 lessons for the current milestone. |
| Early lessons write directly to RDS; final rubric requires FIFO before scoring/storage | Keep direct ingestion for this milestone. Replace that write path deliberately when building FIFO; do not run both writers. |
| DynamoDB timestamp/event keys versus the account/date lesson | Current `risk_scores` uses `account_id` + `score_date`. A transaction event store would be a separate access pattern. |
| Sample account strings such as `acc-001` versus SQL UUID columns | Use UUIDs consistently for implemented routes and CSV data. |
| API keys versus IAM authentication | Follow Day 1 IAM design for internal access. Usage plans/API keys can meter requests; they are not the authorization mechanism. |
| Brief says Free Tier only; Day 1 asks for customer-managed keys and private-network services | Cost and network review remains a deployment gate. No zero-cost claim is justified by a diagram or script. |
| Rubric headings say 70 build/30 presentation, but numbered criteria total 80/20 | Track the actual eight criteria: 20+15+15+10+10+10+10+10 = 100. |
| Nightly Step Functions scoring versus monthly reporting | These are separate future workflows, not interchangeable schedules. |

These are recorded implementation decisions, not confirmation that the facilitator has waived conflicting requirements.

## Final submission beyond this milestone

The final brief requires the connected FIFO/scoring pipeline, SES alerts, monthly EventBridge reports, write endpoints (`POST /upload`, `/flag`, `/resolve`), monitoring/tracing, a deployed end-to-end test, green CI evidence, and a Well-Architected review. The pre-build plan also names `POST /score` and nightly orchestration; reconcile these before building the later API/workflow stage.

Submit six SQL artefacts: schema, 200+ synthetic transactions over three months, rolling 30-day risk report, hand-checked running balance, view, and stored function. Submit the architecture PDF, matching ERD, endpoint contract, IAM matrix, governance document, and screenshots. Ten filenames alone do not satisfy the Python requirement: the functions must work.

## Findings from the cleanup

Fixed: result pagination; malformed CSV rows; quarantine filename collisions; ignored extra S3 event records; altered version IDs; missing version-read IAM permission; overly broad S3 read/write pairing; rollback during row retry; false alert/report success; repeated risk events inflating a transaction count; invalid account-summary view grouping; duplicate validation and mismatched model field names.

Still open: connection reuse, approved scoring weights and high-velocity logic, infrastructure encryption/logging/network configuration, broader SQL business-case verification, and deployed evidence. Prototype scoring uses 70 as High; the risk report now uses that same threshold. The prototype is not an approved fraud model.

## Source notes

Course sources: Pre-Build Project Definition; Capstone Project Brief; Capstone Assessment Rubric; W13 D1 AM/PM; W13 D2 AM/PM; W13 D3 AM; and the Day 3 PM lesson pasted in the request. The lesson's 'Save as PDF' navigation labels are not additional backend requirements.

Technical corrections were checked against [S3 version-read permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html) and [API Gateway access controls](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-to-api.html). Diagram assets come from the [official AWS architecture icon pack](https://aws.amazon.com/architecture/icons/).

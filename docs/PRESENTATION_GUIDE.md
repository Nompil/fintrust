# FinTrust presentation guide

## Explain the problem

FinTrust turns transaction files into a searchable ledger and repeatable risk decisions. Invalid records remain traceable, analysts can inspect transactions, and high-risk results can initiate an email alert. Business effectiveness, fraud reduction and financial savings have not been measured.

## Explain the system

Start with [architecture](architecture.md), then the [ERD](erd.md), [security](SECURITY.md) and [operations](OPERATIONS.md). Follow one transaction through the system:

1. A CSV lands in S3. Ingest validates its rows and records rejection reasons.
2. Valid rows enter an SQS FIFO queue grouped by account.
3. A private scoring function locks the account, calculates rule-based risk and commits the ledger and frozen result in PostgreSQL.
4. An immutable DynamoDB projection is written after the SQL commit. A retry reuses the committed result if that write fails.
5. DynamoDB Streams supplies high-risk projections to the alert function. A conditional delivery record controls retries around SES.
6. The read API supports the dashboard. A separate scheduled function produces monthly reports.

The code and local tests implement these components. AWS deployment and end-to-end behavior remain unverified. The existing browser does not sign AWS_IAM requests, so authenticated cloud dashboard access still needs integration.

## Service choices

| Service | Reason for its place in FinTrust |
|---|---|
| S3 | Durable source files, rejection records and report objects |
| SQS FIFO | Buffer scoring work and preserve ordering within an account |
| Lambda | Separate ingestion, scoring, querying, reporting and alert responsibilities |
| PostgreSQL on RDS | Relationships, constraints and a transaction boundary for the financial ledger |
| DynamoDB and Streams | Immutable lookup projections and event-driven alert processing |
| SES API | Email submission outside the private database network |
| API Gateway | Authenticated boundary for account-data routes |
| EventBridge | Monthly report scheduling, disabled until approved |
| IAM, KMS and SSM | Scoped service permissions, encryption and nonsecret deployment configuration |
| CloudWatch | Logs and the intended operational alarm surface |

## Demonstrate only what is available

Use synthetic data and the local commands in [operations](OPERATIONS.md). Show a valid row, an invalid row with its rejection reason, account filtering and transaction pagination. Explain the local upload shortcut before demonstrating it: it is synchronous direct ingestion, not the deployed queue path. Do not present mocked email calls as delivered messages.

Use the current Markdown architecture and ERD sources for technical discussion. The [diagram register](diagrams/README.md) marks older SVG/PDF exports that need reconciliation. Open PDFs in a PDF viewer; raw `%PDF` text in an editor is the file encoding, not its reading view. Do not use stale exports as the final submission.

The last recorded local run was 158 passed, zero failed and one skipped. The skipped database-role test requires an administrator. CI is prepared to run all 159 tests with a disposable administrator, but has not run. Explain the Windows/Linux native dependency issue and the package verifier without claiming a successful Linux result.

## Questions to prepare for

| Question | Project-specific answer |
|---|---|
| Why both SQL and NoSQL? | SQL owns the ledger and atomic scoring result; DynamoDB supplies lookup projections and stream events. There is no distributed transaction between them, so retries repair the projection. |
| What happens to duplicate transactions? | Stable IDs and payload fingerprints reuse the original result; conflicting reuse fails. This does not mean that every external producer's business duplicate is automatically recognizable. |
| Is a high score proof of fraud? | No. It is a rule-based review signal with reasons. Weights and thresholds need business validation. |
| Is quarantine the DLQ? | No. Quarantine records data rejected for a reason; the DLQ holds work that exhausted processing retries. |
| Can an alert be sent twice? | Conditional claims prevent blind replay, but SES and DynamoDB cannot commit atomically. Uncertain outcomes require reconciliation. |
| Why no NAT? | Database functions call private PostgreSQL and use S3/DynamoDB gateways. Ingest and email delivery are outside the VPC. This avoids introducing a NAT gateway's standing cost. |
| Is the system free to run? | No. Database capacity, keys, storage, retained versions, logs and requests can incur costs. Actual account allowances are unverified. |
| Does IAM protect the local browser? | No. Gateway IAM configuration and local Flask behavior are different boundaries. The browser integration is still unresolved. |
| Is data retention complete? | No. A summary report is not an archive; full export, reconciliation and restore testing must precede ledger deletion. |
| What is proven? | Repository tests and recorded offline checks. Linux execution, deployed permissions and cloud integration still need evidence. |

## Production recommendations

Before deployment: complete Linux verification, authorized resource inventory, budget reconciliation, database grants/TLS and authenticated dashboard access. Before enabling traffic: finish alarms, recovery procedures and integration tests.

Later improvements include a managed analyst identity flow, connection-capacity planning, business-approved risk rules, complete archival automation and restore exercises. These are recommendations, not implemented features or verified outcomes.

After AWS verification, reconcile the canonical docs and the seven required diagram views, then rebuild and visually inspect the PDFs. Retain the run and configuration evidence that supports each deployment claim.

> Historical reference retained in place. Some implementation/status descriptions are superseded. Use the [current canonical guide](OPERATIONS.md) and [documentation inventory](../README.md) for current behavior and proposed disposition. No archive or deletion has occurred.

# Data Governance and Compliance Statement

## 1. POPIA Classification

FinTrust handles transaction-level data linked to identifiable customers. In the current schema, `customers.full_name` and `customers.id_number` are direct identifiers. `customer_id`, `accounts.account_id`, transaction dates, amounts, merchant names, currency, and cross-border indicators are linkable financial information and must be protected as personal information in this context. The current schema does not collect card numbers or payment credentials.

These fields must be treated as personal and sensitive operational data. Access is restricted to authorised compliance and fraud teams. Storage and retention should be aligned to a formal policy that enforces access control, least privilege, and auditability.

## 2. Data Quality Framework

The ingestion layer validates each transaction before it is persisted. Checks include:
- required `account_id`, `amount`, `tx_date`, and `tx_type` fields;
- a valid account UUID, parseable ISO-8601 timestamp, and finite positive decimal amount;
- a transaction type and currency from the allowlists enforced by the SQL schema;
- referential integrity to an existing account, enforced by the database.

Invalid rows are written to the S3 `quarantine/` prefix with source row and reason; other valid rows in the file continue. Database integrity violations are isolated row-by-row. Infrastructure failures (for example, RDS unavailable) fail the invocation so Lambda can retry and eventually send the event to the ingest DLQ.

## 3. Data Lifecycle Policy

These are course design assumptions, not a legal retention determination or proof of compliance.

| Data | Intended retention | Current implementation |
|---|---|---|
| Raw S3 objects | Standard for 90 days, then Glacier; expire current version at day 2555 | Lifecycle script exists; not verified in AWS |
| Noncurrent S3 versions | Transition after 90 noncurrent days; expire after 2555 noncurrent days | This can extend total retention beyond seven years from original creation; review before deployment |
| DynamoDB daily scores | 90-day TTL for operational lookup | Table TTL setup exists; score writer is not connected |
| CloudWatch application logs | 30 days | IAM setup script configures log retention |
| RDS ledger, quarantine and reports | Formal periods and deletion/archive procedures still required | No complete purge/archive workflow |

Retention must be approved for each data class, including backups and versions. Encryption and access controls are separate requirements; lifecycle rules alone do not establish compliance.

## 4. Migration Strategy

Chosen 7R classification: **Replatform**. FinTrust preserves the existing transaction workflow while replacing the flat-file landing and manual ETL path with S3, managed PostgreSQL, and validated Lambda processing. AWS Application Migration Service can move any supporting legacy application servers that must be retained during transition; AWS DataSync is the more suitable service for transferring files from NAS to S3. This phased approach modernises the data path without requiring a big-bang rewrite.

## 5. Risk Register

| Risk | Probability | Impact | Control |
|---|---|---|---|
| Exposure of direct identifiers or linked transaction data | Medium | High | Amazon S3 Block Public Access, scoped IAM policies, and AWS CloudTrail audit events |
| Invalid or incomplete transaction records corrupting reports | Medium | High | AWS Lambda row validation/quarantine and PostgreSQL CHECK/foreign-key constraints |
| Records retained beyond the approved period | Low to Medium | High | Amazon S3 Lifecycle configuration plus a documented retention review |

## 6. Evidence still required

Verify deployed access controls, encryption, audit logs, retention and deletion behavior. Risk controls above are design commitments; this repository is not evidence of legal compliance.


### Local transaction-identity hardening checkpoint

[Identity, batch audit and duplicate-charge handling](IDEMPOTENCY.md)
records the new local implementation, additive migration and review/release gates.
Duplicate data is prevented/audited; distinct suspicious charges remain in the
ledger. No AWS migration or permission update was performed. New runtime source
requires a new Linux-verified artifact; the earlier uploaded ZIP remains evidence
for its previous source only. Stage 5 tagging recovery and deployment remain
separate, unexecuted approval checkpoints. Do not run older Stage 5 commands as a
release procedure for the new source.

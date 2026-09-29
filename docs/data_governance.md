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

### Hot data
- RDS PostgreSQL: retained for approximately 12 months
- Used for active operational review and recent financial reporting

### Warm data
- S3 analytical storage: retained for up to 3 years
- Suitable for trend analysis and operational history

### Cold archive
- S3 Glacier or equivalent archival tier: retained for up to 7 years
- Consistent with regulatory or compliance retention requirements

## 4. Migration Strategy

Chosen 7R classification: **Replatform**. FinTrust preserves the existing transaction workflow while replacing the flat-file landing and manual ETL path with S3, managed PostgreSQL, and validated Lambda processing. AWS Application Migration Service can move any supporting legacy application servers that must be retained during transition; AWS DataSync is the more suitable service for transferring files from NAS to S3. This phased approach modernises the data path without requiring a big-bang rewrite.

## 5. Risk Register

| Risk | Probability | Impact | Control |
|---|---|---|---|
| Exposure of direct identifiers or linked transaction data | Medium | High | Amazon S3 Block Public Access, scoped IAM policies, and AWS CloudTrail audit events |
| Invalid or incomplete transaction records corrupting reports | Medium | High | AWS Lambda row validation/quarantine and PostgreSQL CHECK/foreign-key constraints |
| Records retained beyond the approved period | Low to Medium | High | Amazon S3 Lifecycle configuration plus a documented retention review |

## 6. Governance Summary

The project embeds governance as a design concern rather than a final document. Access is controlled, sensitive data is classified, records are validated before storage, retention periods are defined, and alerts support operational accountability.

# Data Governance and Compliance Statement

## 1. POPIA Classification

FinTrust handles transaction-level data that may include personal information such as:
- customer names,
- account identifiers,
- transaction dates,
- merchant and location details,
- payment channel and transaction metadata.

These fields must be treated as personal and sensitive operational data. Access is restricted to authorised compliance and fraud teams. Storage and retention should be aligned to a formal policy that enforces access control, least privilege, and auditability.

## 2. Data Quality Framework

The ingestion layer validates each transaction before it is persisted. Validation checks include:
- required fields present,
- positive numeric amount,
- valid transaction type,
- valid channel type,
- supported currency,
- minimum account ID length,
- standard risk scoring inputs.

Records that fail validation should be quarantined, rejected, or routed to a manual review queue. This prevents bad data from contaminating the financial ledger and supports operational trust.

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

The legacy flat-file platform can be migrated using AWS Application Migration Service. The best classification is either Rehost or Replatform, depending on the level of change required. Rehost is the safer default if the goal is to move the existing system quickly with minimal redesign. Replatform is more suitable if the organisation wants to modernise key components as part of the migration. The key justification is that it reduces migration risk while allowing the bank to move toward an event-driven, more secure target architecture.

## 5. Risk Register

| Risk | Probability | Impact | Control |
|---|---|---|---|
| Data leakage through excessive access | Medium | High | IAM least-privilege roles and audit logging |
| Invalid data entering the ledger | Medium | High | Input validation and quarantine workflow |
| Non-compliance with retention or data handling obligations | Low to Medium | High | Lifecycle policy, access controls, and governance review |

## 6. Governance Summary

The project embeds governance as a design concern rather than a final document. Access is controlled, sensitive data is classified, records are validated before storage, retention periods are defined, and alerts support operational accountability.

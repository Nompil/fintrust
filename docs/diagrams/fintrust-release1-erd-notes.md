> Supporting source retained for traceability. Use [Project Master](../FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](../FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Physical ERD notes

Source: frozen application `10eb378abf6a4a256043cd56617378cc17ae505c`, verified local PostgreSQL 16.15 catalog. This describes the locally verified schema, not a claim that live RDS is bootstrapped.

## Scope and cardinality

17 tables are shown. Solid connectors mean actual PostgreSQL FKs; `1`, `0..1`, `0..*` describe required/optional parent and maximum children. PK/FK/UK markers label columns; composite keys apply together, not as individually unique columns. Full constraint text below remains authoritative. `transactions.batch_id` is a lineage value, **not an FK**.

Two derived views are not tables: `batch_reconciliation` aggregates ingestion batches/records; `quarantine_workflow` derives current quarantine/correction state. No separate SQL duplicate table: duplicate occurrences are `ingestion_records` with disposition DUPLICATE.

Local users/roles/account assignments/status/token hashes are in the ignored file-backed registry (`fintrust/auth.py`, `fintrust/local_users.py`); no invented SQL user/role tables. User-governance audit receipts use the S3-style receipt store (mocked/local in the presentation), not a SQL identity table. Browser notices are session-local, not a SQL notifications table. Cloud alert claims use DynamoDB; `alerts` remains the relational legacy/direct-path table. Outboxes and operations receipts are actual SQL tables.

## PK, FK and unique constraints

| Table | Kind | Exact catalog definition |
|---|---|---|
| `accounts` | FK | `FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT` |
| `accounts` | PK | `PRIMARY KEY (account_id)` |
| `alerts` | UK | `UNIQUE (delivery_key)` |
| `alerts` | PK | `PRIMARY KEY (alert_id)` |
| `alerts` | FK | `FOREIGN KEY (risk_event_id) REFERENCES risk_events(risk_event_id)` |
| `correction_outbox` | FK | `FOREIGN KEY (correction_id) REFERENCES quarantine_corrections(correction_id)` |
| `correction_outbox` | PK | `PRIMARY KEY (correction_id)` |
| `customers` | UK | `UNIQUE (id_number)` |
| `customers` | PK | `PRIMARY KEY (customer_id)` |
| `ingestion_attempts` | UK | `UNIQUE (batch_id, attempt_id)` |
| `ingestion_attempts` | FK | `FOREIGN KEY (batch_id) REFERENCES ingestion_batches(batch_id)` |
| `ingestion_attempts` | PK | `PRIMARY KEY (attempt_id)` |
| `ingestion_batches` | PK | `PRIMARY KEY (batch_id)` |
| `ingestion_batches` | UK | `UNIQUE (source_bucket, file_sha256)` |
| `ingestion_records` | FK | `FOREIGN KEY (batch_id) REFERENCES ingestion_batches(batch_id)` |
| `ingestion_records` | FK | `FOREIGN KEY (batch_id, source_attempt_id) REFERENCES ingestion_attempts(batch_id, attempt_id)` |
| `ingestion_records` | FK | `FOREIGN KEY (canonical_tx_id) REFERENCES transactions(tx_id)` |
| `ingestion_records` | PK | `PRIMARY KEY (batch_id, source_row)` |
| `operations_requests` | PK | `PRIMARY KEY (request_id)` |
| `processed_transactions` | PK | `PRIMARY KEY (tx_id)` |
| `processed_transactions` | FK | `FOREIGN KEY (tx_id) REFERENCES transactions(tx_id)` |
| `projection_outbox` | PK | `PRIMARY KEY (tx_id)` |
| `projection_outbox` | FK | `FOREIGN KEY (tx_id) REFERENCES processed_transactions(tx_id)` |
| `quarantine_cases` | FK | `FOREIGN KEY (batch_id, source_row) REFERENCES ingestion_records(batch_id, source_row)` |
| `quarantine_cases` | UK | `UNIQUE (batch_id, source_row)` |
| `quarantine_cases` | PK | `PRIMARY KEY (quarantine_id)` |
| `quarantine_corrections` | PK | `PRIMARY KEY (correction_id)` |
| `quarantine_corrections` | UK | `UNIQUE (quarantine_id, correction_version)` |
| `quarantine_corrections` | FK | `FOREIGN KEY (quarantine_id) REFERENCES quarantine_cases(quarantine_id)` |
| `quarantine_corrections` | FK | `FOREIGN KEY (reprocess_batch_id, reprocess_source_row) REFERENCES ingestion_records(batch_id, source_row)` |
| `quarantine_corrections` | UK | `UNIQUE (request_id)` |
| `risk_events` | PK | `PRIMARY KEY (risk_event_id)` |
| `risk_events` | FK | `FOREIGN KEY (tx_id) REFERENCES transactions(tx_id)` |
| `risk_review_history` | PK | `PRIMARY KEY (risk_event_id, version)` |
| `risk_review_history` | UK | `UNIQUE (request_id)` |
| `risk_review_history` | FK | `FOREIGN KEY (risk_event_id) REFERENCES risk_reviews(risk_event_id)` |
| `risk_reviews` | PK | `PRIMARY KEY (risk_event_id)` |
| `risk_reviews` | FK | `FOREIGN KEY (risk_event_id) REFERENCES risk_events(risk_event_id)` |
| `schema_migrations` | PK | `PRIMARY KEY (version)` |
| `transactions` | FK | `FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE RESTRICT` |
| `transactions` | PK | `PRIMARY KEY (tx_id)` |

Transactions also have the partial unique source/account/transaction-identity index from migration 001. Fingerprints are **not** globally unique: similar genuine transactions must remain distinct.

## Actual storage outside PostgreSQL

- S3: original files, safe versioned quarantine/correction payloads, reports; SQL stores references.
- DynamoDB: immutable score projections and alert-delivery claims, with idempotency.
- Ignored local identity registry: human subjects, role, account scope, active/disabled state and hashed tokens.
- Browser session: notices and acknowledgement state.

## State vocabulary

- Ingestion records: RECEIVED / QUEUED / ACCEPTED / QUARANTINED / DUPLICATE / FAILED_TECHNICAL.
- Reviews: OPEN -> UNDER_REVIEW -> CLEARED / CONFIRMED_RISK / ESCALATED; allowed transitions remain backend-enforced.
- Alerts: PENDING / SENDING / SENT / FAILED / UNKNOWN.
- Outboxes: PENDING / COMPLETED. Operations requests: RUNNING / COMPLETED / FAILED.

The full ERD is the technical appendix: open the final A3 ERD PDF at native size/zoom for all keys. Use the data-decision flow for a screen-sized first explanation.

# Phase 2 transaction lifecycle contract

This is a local domain implementation from baseline `6fbe773`; no AWS resources, live schema or frozen migration 001/002 changed. No dashboard/AI work. Migration 003 is additive and separately approved for live use later.

## Authority and actual chronology

| Concern | Existing authority | Lifecycle visibility |
|---|---|---|
| Financial identity and storage | transactions + processed_transactions | STORED, frozen risk, source identity |
| Original row occurrence | ingestion_records + ingestion_attempts + ingestion_batches | RECEIVED, worker handoff, disposition and immutable provenance |
| Processing observations | new transaction_lifecycle_events | Append-only sequence/time/system actor and sanitized error class |
| Quarantine/correction | quarantine_cases + quarantine_corrections + correction_outbox | QUARANTINED, human CORRECTED and separate correction occurrence REVALIDATED |
| Investigation | risk_reviews + immutable risk_review_history | OPEN, UNDER_REVIEW, CLEARED / CONFIRMED_RISK / ESCALATED; human actor |
| Alerts | existing SQL receipt / DynamoDB delivery claim | ALERTED only for durable SENT evidence; UNKNOWN is not SENT |
| Operator retry | operations_requests | Human RETRY_REQUESTED distinct from actual worker RETRY/RECOVERED |

The requested conceptual `RECEIVED -> VALIDATED -> QUEUED -> SCORED -> STORED` cannot truthfully describe existing cloud transport. Ingest cannot perform account-aware SQL validation outside the VPC. The actual recorded progression is **RECEIVED -> QUEUED -> VALIDATED -> SCORED -> STORED**. QUEUED is candidate handoff observed by the consumer, not proof of successful live SQS deployment. This preserves the reviewed architecture and never marks an invalid candidate validated merely to match a diagram. File parsing/admission occurs before publication; full business validation occurs in the consumer.

Risk/review/delivery are independent dimensions. Every accepted LOW/MEDIUM/HIGH stays in the ledger; all scored results have a risk event. Medium/High create OPEN reviews at SQL commit, before and independent of High-only email success. A HIGH score is not a validation error. Existing authorized review transitions and immutable audit triggers remain unchanged.

## Additive migration and worker behavior

`sql/migrations/003_transaction_lifecycle.sql` follows verified 001/002. The existing local checksummed migration harness validates prerequisite 002, detects rerun drift and applies transactionally. It adds only one audit table, indexes and insert guard; there is no writable transaction status column or competing current-state table. Old rows are not backfilled with invented timestamps. Original source receipt remains `ingestion_batches.received_at`; audit time is the observation time, not a fabricated enqueue/provider timestamp.

An occurrence lock serializes its event sequence. Insert guards reject skipped stages, false recovery, retry without failure and terminal mutation; existing immutable-history trigger denies update/delete. Repeated delivery reuses phase events. Failure/RETRY/RECOVERED are separate observations and do not overwrite prior history. SCORED/STORED commit with the ledger outcome. DynamoDB failure leaves STORED financial data and a pending projection; replay or controlled projection repair records recovery after durable completion. Error messages and payloads are never copied into events.

QUARANTINED is terminal for its original row. Human correction creates an audited new occurrence, then ordinary validation/deduplication executes again. API lineage joins that new occurrence back to the original correction without rewriting either identity. Similar financial transactions still use the frozen identity/risk rules.

DLQ is accepted only by the trusted internal audit writer after an observed technical failure, never inferred from retry count. This phase does not wire SQS/DLQ transport or create a public state-changing route. Actual automatic redrive/dead-letter evidence integration remains in the later technical recovery phase. A DLQ occurrence cannot be automatically processed again. SQL/network outage before registration cannot produce a SQL audit; existing sanitized worker error/FIFO retry evidence remains authoritative for that failure. The API never manufactures missing history.

## API

- `GET /v1/transactions/{tx_id}/lifecycle`: stored transaction, frozen risk, review/delivery state, source occurrences and merged audit timeline.
- `GET /v1/ingestion/{batch_id}/rows/{source_row}/lifecycle`: original disposition, processing state, receipt/source metadata, event observations and correction lineage. Allows inspection before a canonical tx_id exists.

Both require existing authenticated/account-scoped read authority; Maintainer financial reads stay denied. Unknown and out-of-scope records are hidden. Admin unknown-account quarantine authority matches existing quarantine reads. SQL business outcomes do not become TECHNICAL_FAILURE merely because projection delivery failed. Reads are bounded (100 occurrences, 1000 occurrence/review observations, 100 correction/operator links); `timeline_complete=false` discloses missing/truncated history. Alert claim read failure fails closed rather than inventing delivery success. No frontend labels or human actor supplied by a lifecycle request control state.

## Local and future deployment boundaries

Fresh isolated test schemas and the existing loopback-only demo launcher apply migration 003 after 001/002. No running database/server has been reset or reseeded by this task. Local migration rollback rolls back the new objects/history registration; there is no destructive down migration of accumulated audit evidence.

The fixed-phase live runner still supports the reviewed 001/002 phases only. Do NOT deploy this runtime to a schema without 003. A later controlled live-bootstrap plan must explicitly add migration-003 ownership/catalog proof and least-privilege grants: scoring execution identity needs INSERT/SELECT on this audit table plus identity-sequence USAGE; API identity needs SELECT only; no service gets UPDATE/DELETE. Trusted trigger prerequisites need existing ingestion-record SELECT/row-lock UPDATE and projection SELECT. Do not grant PUBLIC, broad schema ownership or broad IAM to solve it. These live changes are not performed here. A fresh Linux Python 3.12 artifact gate is also required before deployment.

Next local phase: quarantine recovery verification/wiring, then Risk Event -> Alert -> Review Queue integration, then full local scenarios. Live AWS bootstrap comes afterward under separate approval.

## Phase 2 verification

62 focused lifecycle/domain/frozen-runner regression tests passed locally and 21 lifecycle tests passed on disposable PostgreSQL 16. Broader regression: 756 passed, 1 skipped, zero failures. The existing administrator-only role skip retains its separate prior PG16 proof. Existing domain/API focused run: 144 passed. SQL 001/002 and all 163 unrelated files preserved. See [sanitized evidence](../EVIDENCE/12-e2e/transaction-lifecycle/verification-summary.json).

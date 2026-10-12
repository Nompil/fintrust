# FinTrust speaker notes

## Problem

Transaction exports need reliable admission, duplicate protection, explainable risk signals and accountable human review. FinTrust records and investigates transactions; it does not move money or prove fraud.

## People

- Administrator: manage local users, roles and access; inspect platform state and audit.
- Analyst: upload scoped CSVs, correct quarantine, investigate and resolve risk reviews.
- Auditor: read scoped transactions, batches, risk, reports, insights and audit; no mutations.
- Maintainer: investigate technical failures and perform controlled retries; no compliance decisions.

## Admission and rows

CSV only, at most 1 MiB and 5,000 rows. Reject invalid files with a safe receipt and no ledger processing. Quarantine bad rows with reasons and original lineage. Validate required identity, positive amount, timestamp, currency/country/type and known account. Correction creates a new occurrence; validation and duplicate checks run again. Release 1 does not silently reinterpret negative rows as refunds.

## Duplicate protection

An exact file replay records an attempt and returns the original batch. The same transaction in one file or another file creates no second ledger entry. Changed financial facts under the same source identity create a quarantined conflict. Similar genuine transactions with different source IDs remain separate and can receive a possible duplicate-charge risk flag. Duplicate protection protects the ledger; duplicate-charge detection protects the customer.

## Risk

Frozen score bands: LOW 0–39, MEDIUM 40–69, HIGH 70–100. LOW is stored without routine review; MEDIUM opens review; HIGH opens review and the alert path.

- Amount strictly above R50,000: 30 points; above R200,000 adds 25.
- More than five accepted transactions in the inclusive five-minute window: 30.
- Non-ZA country: 15.
- Possible duplicate debit charge with distinct identities, matching merchant/amount/currency within inclusive 120 seconds: 40.
- Outgoing transfer and high-risk merchant: 20 each; total capped at 100.

R49,999.99 and R50,000.00 do not trigger the first amount rule; R50,000.01 does. A high amount or cross-border transaction alone need not be HIGH. The 10/11/12-per-hour scenario is future exploration, not the production velocity rule.

## Review, evidence and reports

OPEN → UNDER_REVIEW → CLEARED / CONFIRMED_RISK / ESCALATED. Preserve actor, notes, versions and history. Evidence and reports support decisions; alerts do not make those decisions. Browser notifications are session UI, not an invented SQL notifications table. User identities use the local registry, with governance receipts in the receipt store.

## Failure handling

Reconcile every received row to an outcome; pending/failed work remains visible. Quarantine is a business-data problem; retry/DLQ is a technical-processing problem. FIFO groups work by account. Durable correction/projection outboxes preserve retry intent after partial failures; retries must not duplicate ledger entries or alerts. Maintainer recovery is separate from Analyst review.

## Presentation boundary

Demonstrate the verified local workflow using isolated PostgreSQL and local service substitutes. Explain the cloud target diagram separately. Do not describe local queue, mail or identity substitutes as live AWS integration. Use the [live script](LIVE_DEMO_SCRIPT.md) and [readiness checkpoint](../RELEASE1_PRESENTATION_READINESS.md).

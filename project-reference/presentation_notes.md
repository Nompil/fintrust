# Presentation Notes for Stakeholders

## 1. Elevator Pitch

FinTrust Bank SA needs a transaction monitoring capability that detects unusual or high-risk activity before it becomes financial or compliance exposure. Our solution applies serverless AWS services, business validation, and risk scoring across the transaction lifecycle so the bank can act faster and with stronger governance.

## 2. Business Problem

The organisation receives high volumes of transaction activity from multiple channels and legacy systems. Without an integrated monitoring layer, suspicious activity can be missed, review teams become overloaded, and compliance obligations become harder to evidence.

## 3. Solution Narrative

We ingest CSV-based transaction files into S3, validate each record, and push the data through an event-driven processing path. The scoring layer assesses each event against known risk patterns, and the output is persisted in both a relational ledger and a NoSQL event store. High-risk totals trigger alerts and monthly insight reporting.

## 4. Why This Design Is Strong

- Scalable: serverless components react only when needed.
- Cost-aware: the design respects the AWS Free Tier and avoids high-cost components such as NAT Gateway.
- Defensible: the architecture is built with security boundaries and clear responsibility separation.
- Auditable: every key action creates a traceable record and can be reviewed.

## 5. Key Questions to Prepare For

### Q: Why not just put everything in one database?
A: The architecture separates ledger data from event state. The relational store supports reporting and normalised financial records, while DynamoDB is suited for fast event access and session or token-level metadata. That separation improves performance, resilience, and operational clarity.

### Q: How do you prevent bad data from entering the system?
A: Every record is stripped and validated before it is stored. Required fields, amount rules, and transaction-type checks are applied before the record is persisted. Invalid rows are quarantined or routed for review.

### Q: What happens if a Lambda fails?
A: The design uses queues and dead-letter patterns to isolate failures, prevent silent data loss, and allow operational recovery without losing the transaction stream.

### Q: Why is compliance important here?
A: Financial data is sensitive. We treat it as regulated information and apply retention, access control, monitoring, and governance principles that align with POPIA and operational best practice.

## 6. Suggested Closing Statement

This system gives FinTrust a practical and scalable way to monitor transactions, protect customer trust, and support compliance and executive decision-making with a strong operational foundation.

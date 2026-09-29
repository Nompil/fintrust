# FinTrust Bank SA - Transaction Insights and Risk Monitoring System

A capstone project for a cloud-native transaction insights and risk monitoring system for a South African fintech bank.

## Current Build Status

The repository currently implements the Week 13 Day 1-2 foundation: S3 bucket/IAM/SSM infrastructure scripts, a PostgreSQL schema and seed set, a DynamoDB risk-score table script, and an S3-triggered CSV validation/load handler. The Day 2 exercise writes validated rows directly from the ingest Lambda to PostgreSQL; the later SQS scoring, API, alert, reporting, and deployed CloudWatch dashboard are target architecture items and are not yet implemented or deployed.

## Business Outcome

FinTrust needs a system that can:
- ingest transaction data from legacy sources,
- validate and risk-score each transaction,
- store an auditable ledger and event log,
- surface compliance insights through a secure API,
- alert the risk team when a transaction exceeds policy thresholds,
- produce monthly executive reporting.

The solution is built around the AWS Free Tier and follows the FinTrust capstone brief: a serverless ingestion path, SQL-backed ledger, NoSQL event log, API access for analysts, and automated reporting.

## Architecture Summary

```mermaid
flowchart LR
    A[Legacy CSV Upload] --> B[S3 Raw Bucket]
    B --> C[Ingest Lambda]
    C --> D[SQS FIFO Queue]
    D --> E[Risk Scoring Lambda]
    E --> F[(RDS PostgreSQL Ledger)]
    E --> G[(DynamoDB Event Store)]
    E --> H[SES Alert]
    I[API Gateway] --> J[Query Lambda]
    J --> F
    J --> G
    K[EventBridge] --> L[Report Lambda]
    L --> M[S3 Reporting Bucket]
```

## Folder Structure

```text
fintrust/
  __init__.py
  config.py
  db.py
  dynamo.py
  models.py
  validators.py
  ingest.py
  score.py
  alert.py
  query.py
  report.py

sql/
  schema.sql
  seed.sql
  risk_report.sql
  monthly_summary.sql
  views.sql
  procedure.sql

infrastructure/
  README.md
  s3/
  iam/
  ssm/
  dynamodb/

tests/
  conftest.py
  test_validators.py
  test_score.py

.github/
  workflows/
    ci.yml

docs/
  presentation_notes.md

samples/
  transactions_day2.csv
```

## Core Principles

1. Least privilege first: Lambda execution roles are minimal and purpose-specific.
2. Data quality before storage: validation happens before persistence.
3. Event-driven processing: ingestion is decoupled from scoring and alerting.
4. Compliance by design: POPIA-conscious data handling and retention logic are part of the design.
5. Operational trust: logs, metrics, and alerts are included in the architecture.

## Deployment Story

This solution is intended to be explained as a business-grade financial controls platform:
- raw transaction files land in S3,
- validation confirms format and business rules,
- risk scoring calculates a transaction risk profile,
- suspicious events are reviewed by compliance teams,
- management receives monthly trend analysis.

## How to Present It Confidently

When speaking to stakeholders:
- describe the business problem before the architecture,
- explain why each AWS service was chosen,
- connect every technical decision to a business outcome,
- be ready to answer what happens when a transaction fails validation or when a Lambda errors,
- show the security and compliance logic, not just the happy path.

## Suggested Presentation Narrative

- Problem: FinTrust needs a faster, safer way to detect risk in high-volume banking transactions.
- Solution: Serverless event-driven analytics and risk-monitoring pipeline.
- Why this works: real-time validation, asynchronous processing, governance controls, auditable events.
- Business value: reduced fraud exposure, lower manual review burden, improved compliance posture.

## Quick Start

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```

## Notes

AWS infrastructure scripts create real account resources when explicitly run. Review `infrastructure/README.md` and AWS costs/permissions before running them. Local tests use Moto and do not deploy AWS resources.

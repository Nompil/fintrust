# Completed Work

**Status snapshot:** 29 September 2026. This records repository work completed locally; it does not claim AWS resources have been deployed.

## Week 13 Foundation

- Added S3 bucket setup for versioning, public-access blocking, and raw-object lifecycle rules.
- Added boto3 scripts for scoped Lambda IAM roles, SSM database parameters, S3-to-Lambda notifications, and the DynamoDB `risk_scores` table with TTL.
- Built a PostgreSQL model for customers, accounts, transactions, risk events, and alerts, with UUID keys, foreign keys, check constraints, and indexes.
- Added seed data for five customers/accounts and 200 transactions.
- Implemented CSV parsing, transaction validation, UUID/date/decimal transformation, idempotent inserts, invalid-row quarantine, and structured logs.
- Added a Lambda invocation DLQ setup script, a DLQ replay script, and CloudWatch metric-filter/alarm setup scripts.
- Implemented local Flask routes for `GET /v1/health`, `GET /v1/transactions`, and `GET /v1/insights`; documented AWS_IAM as the API Gateway authorization design.
- Added the ERD, API design, IAM matrix, governance statement, resilience notes, demo script, and stakeholder presentation notes.
- Added opt-in PostgreSQL constraint tests, Moto-backed DynamoDB tests, API and ingestion tests, and a GitHub Actions workflow with unit tests and a `develop`-only PostgreSQL integration job.
- Added `.env.example`, dependency pins, and ignore rules for local secrets and generated files.

## Local Verification Evidence

- Python test result: **15 passed, 5 skipped**. The five skipped tests require `FINTRUST_TEST_DATABASE_URL` and a disposable PostgreSQL database.
- PostgreSQL integration result: **5 passed** against the local PostgreSQL 18.6 `fintrust_test` database on 29 September 2026. The tests applied the schema/seed and verified the amount, currency, transaction-type, KYC-state, and account-delete constraints.
- All Python files compiled successfully.
- PostgreSQL grammar parsing passed for all six SQL files; the schema and seed have also now been exercised by the local PostgreSQL integration tests. CI uses PostgreSQL 16, so version parity is still checked by CI.
- GitHub Actions YAML parsed successfully; the workflow has not yet run on GitHub.
- Six Conventional Commits exist locally on `main`; the working tree was clean at the last check.

## Current Repository History

- `cb729ea docs: document FinTrust capstone design and presentation`
- `8c7ad9a feat: add Day 1 AWS infrastructure scripts`
- `2c98aa7 feat: implement Day 2 transaction data layer`
- `aabc8a4 feat: add resilient ingest monitoring and read API`
- `3ae33bd test: verify PostgreSQL data quality constraints`
- `1f6403f docs: document Week 13 Days 3-5 implementation`

These commits are local only. There is no GitHub remote and nothing has been pushed.

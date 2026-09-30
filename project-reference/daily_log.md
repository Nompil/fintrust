# Daily progress

Purpose: keep a dated, factual record of what changed, what was tested, what was learned, and what comes next. Update this file at the end of every work session. Calendar dates and course days are recorded separately; a course day is not inferred from the calendar date.

## Verified implementation snapshot

Reviewed 30 September 2026. This file records current repository work; deployment is not inferred from code.

- Reviewed all eight supplied documents and the Day 3 PM lesson; recorded conflicts, scope and missing evidence.
- Implemented direct CSV-to-PostgreSQL ingestion, row quarantine, deterministic IDs, multiple S3 event records and structured per-file counts.
- Added a local Flask health/transactions/insights API with bounded limit/offset pagination.
- Added schema, seed, SQL analytics, view and stored function files. All six SQL files execute on the isolated local database. The running-balance test checks 100 - 25 - 10 = 65; deployed AWS verification remains pending.
- Added S3/IAM/SSM/DynamoDB/DLQ/CloudWatch provisioning scripts. Required KMS, access logging and network setup remain incomplete.
- Fixed version-read IAM permissions, CSV shape failures, quarantine collisions, row-retry rollback, false placeholder success, risk-report double counting and an invalid GROUP BY in the account-summary view.
- Added regression tests and presentation diagrams using official AWS icons, plus a matching five-table ERD and plain-language learning guide.

## Verification

The initial review run reported **15 passed, 5 skipped**. The five skipped tests require a disposable PostgreSQL connection. Earlier database results in the daily log are historical, user-reported evidence; they are not a fresh verification of this cleanup.

Final verification: **33 passed, zero skipped**, including seven PostgreSQL tests. All six SQL files executed; seed data contains 200 transactions across five accounts and three months. The temporary PostgreSQL instance was stopped afterward. No AWS deployment, green remote CI, measured API latency, end-to-end flow or billing evidence was verified in this review.

## 2026-09-28

**Course phase:** Capstone foundation / initial project setup
**Focus:** Establish the FinTrust project structure and initial artefacts.

### Work completed

- Created the `fintrust/` Python package structure and initial modules for configuration, database access, DynamoDB access, validation, ingestion, scoring, API queries, alerts, and reporting.
- Added initial PostgreSQL schema/seed and analytical SQL artefacts, plus unit tests and a CI workflow.
- Added the initial architecture, ERD, API, IAM, data-governance, README, and presentation documentation.
- Detected that the Python launcher was initially unavailable from the shell; later confirmed Python 3.14.7 and installed the project dependencies.

### Verification / outcome

- The initial scaffold was not yet a deployed system; early test execution was blocked by the shell not finding Python.
- No AWS resources were deployed.

### Next

- Align the repository with Week 13 Day 1-5 course requirements, run the code locally, and clearly distinguish implemented components from planned/deployed architecture.

## 2026-09-29

**Course phase:** Week 13 Days 1-5 foundation work
**Focus:** Infrastructure scripts, ingest failure handling, API/data quality, and project knowledge records.

### Work completed

- Added boto3 setup scripts for S3, IAM, SSM, DynamoDB, an ingest DLQ, CloudWatch metric filters/alarms, and DLQ replay.
- Aligned the PostgreSQL model and seed data with `customers -> accounts -> transactions`, risk events, and alerts; added check constraints, foreign keys, indexes, and a view.
- Implemented the local S3-event CSV ingest path: validation, transformation, deterministic transaction IDs, direct PostgreSQL insert, S3 quarantine, and structured success/failure logging.
- Added a local Flask read API for health, PostgreSQL transactions, and DynamoDB insights.
- Added annotated ERD/API/IAM/resilience/governance documentation and PostgreSQL data-quality tests.
- Verified local PostgreSQL 18.6 was running. The first constraint-test run had four passes and one expectation mismatch; PostgreSQL correctly raised `RestrictViolation` for `ON DELETE RESTRICT`. Updated the test to expect that class. The user reran the database tests and reported **5 passed**.
- Organized status/setup/demo documents in `project-reference/`, added a component guide and a durable handoff, and removed duplicate presentation files from `docs/`.
- Reviewed commit messages and project documentation for clarity.

### Verification / outcome

- PostgreSQL integration tests: **5 passed** against local `fintrust_test` on PostgreSQL 18.6.
- Earlier full suite without the database URL: **15 passed, 5 skipped**. The combined full suite with the database URL set has not yet been rerun; expected total is 20 passing tests.
- Python compilation, six SQL grammar parses, CI YAML parsing, project-reference links, and `git diff --check` passed at their respective checks.
- AWS provisioning scripts have not been run. No AWS services, API Gateway, visual CloudWatch dashboard, FIFO scoring pipeline, SES alerts, or monthly reporting are deployed.

### Commits recorded locally

- `8c7ad9a feat: add Day 1 AWS infrastructure scripts`
- `2c98aa7 feat: implement Day 2 transaction data layer`
- `aabc8a4 feat: add resilient ingest monitoring and read API`
- `3ae33bd test: verify PostgreSQL data quality constraints`
- `1383fce test: expect PostgreSQL restrict violation`
- `d62fd89 docs: add project handoff and organize references`
- `e1023cb docs: clarify project handoff language`

All commits are local on `main`; there is no remote configured and nothing has been pushed.

### Next

1. Run `python -m pytest -q` with `FINTRUST_TEST_DATABASE_URL` set in the project-root PowerShell session; target **20 passed**. Then remove that environment variable.
2. Trace one valid and one invalid CSV row through `ingest.validate_row`, `transform_row`, `_load_rows`, and `process_csv`; explain the distinction between mocked ingest tests and live AWS behavior.
3. Continue component-by-component learning, then deploy AWS only after confirming the correct training account, region, and billing alarm.

## Daily Entry Template

Copy this block for each new work date:

```markdown
## YYYY-MM-DD

**Course phase/day:**
**Focus:**

### Work completed
-

### Verification / outcome
- Tests/commands:
- Result:
- Not verified/deployed:

### Decisions or concepts understood
-

### Next
1.
```

## Accuracy Rules

- Record actions and results, not intended or proposed work as though it is complete.
- Say whether a result was local, PostgreSQL integration, CI, or AWS deployment evidence.
- Record failures and how they were resolved; keep useful test evidence.
- Never include passwords, access keys, tokens, or other secrets.
- Update upcoming features when the project state materially changes.

## 2026-09-30

**Course phase:** Week 13 Days 1-3 review and cleanup.

- Reviewed the eight supplied documents and pasted API lesson. Added a single requirements record with conflicts, current decisions and later-stage scope.
- Replaced repetitive presentation claims with a factual foundation demo and business narrative. Added a plain-language learning guide.
- Consolidated validation and model field names; added offset pagination; fixed short/extra CSV rows, source-version quarantine collisions, multiple event processing, S3 version permissions and rollback during row-level retry.
- Replaced false alert/report success responses and the disconnected scoring handler with explicit unimplemented errors. Pure scoring remains a prototype requiring approved weights and velocity rules.
- Fixed the rolling risk report to count distinct transactions and use the prototype High threshold consistently. Executing all SQL found and fixed an invalid GROUP BY in the account-summary view.
- Created editable draw.io diagrams, standalone SVGs and a three-page PDF using official AWS July 2026 icons. Rendered and visually inspected all pages.

**Verification:** 33 tests passed, zero skipped on an isolated local PostgreSQL instance, including seven database tests. All six SQL files executed. Seed checks: 200 transactions, five accounts, three months. Hand-calculated running balance and repeated-risk-event regressions passed. Markdown links and diagram XML validated. Temporary database stopped after verification.

**Boundaries:** No AWS deployment, remote CI verification, billing evidence, measured cloud latency, commit or push. KMS/access logging/private service connectivity, connection reuse, full risk processing, SES and reports remain open. The review does not establish production readiness or legal compliance.

**Next:** Work through the learning guide with one sample row; then close the Day 1 security/network gaps before deployment. Use current completed/remaining work rather than historical test counts above.

## 2026-09-30 - Local learning workflow

- Reduced project-reference to requirements, learning guide, daily progress, upcoming features and an index.
- Merged component explanations and presentation rehearsal into the learning guide; merged completion evidence into this log.
- Added `tools/local.py` for setup, connection checks, tests, sample ingestion and a local API.
- PostgreSQL Windows service was running. Persistent database setup still requires the learner to enter their existing PostgreSQL password in their own terminal.
- The helper creates separate practice/test databases and an application login. AWS services in the local exercises are simulated; PostgreSQL is real.
- Local output and credentials are ignored by Git. No commit, push or AWS provisioning was performed.

Next: run the commands in the learning guide and append the outputs you personally observe.

Verification for the local workflow: `py tools/local.py test` returned **33 passed, 7 skipped**. Skips are the PostgreSQL checks awaiting local setup. Helper tests cover preservation of unrelated settings, separate database selection, hidden administrator credentials not being saved, quarantine output and the preloaded API insight. During development, tests caught AWS clients created before the mock context; clients are now replaced inside the simulation and unmocked AWS HTTP calls are blocked. The helper's database provisioning was tested with mocked connections; its first real run against the persistent server remains the learner's setup exercise. Documentation links and the five-file reference index were checked.

## 2026-09-30 - Database connection and test-folder fix

The learner confirmed setup/check succeeded: fintrust_local connects as fintrust_local_app with 200 transactions across five accounts. Their full test run reported 36 passed and four setup errors: Windows denied access to the shared pytest temporary directory. The helper now uses a fresh temporary directory and cache per run, then removes its own scratch files. Post-fix verification without database checks: 33 passed, 7 skipped. The learner should rerun `py tools/local.py test --database`; expected total is 40 passed.

## 2026-09-30 - Dashboard, SDLC and delivery review

- Added a same-origin analyst dashboard, activity graph, currency totals, account/date ledger and bounded local CSV uploads with rejection reasons.
- Added request correlation, CORS checks, JSON API errors, input bounds and source-row tracking. SQL summaries keep currencies separate.
- Added SDLC evidence, user stories, service/cost decisions, API/database review, troubleshooting and enterprise limitations in the formal system record and PDF. Added activity, use-case and interaction diagrams alongside AWS architecture and ERD.
- Automated verification: 52 tests passed with the separate PostgreSQL test database. Live HTTP checks returned expected 200/400/404/405 codes. Ten serial local transaction requests measured 75.08 ms median and 115.42 ms maximum on the 200-transaction practice dataset; this is not a cloud benchmark.
- Added JUnit CI artifacts and a manual OIDC API-delivery workflow. Remote CI/CD remains unexecuted. Browser automation was unavailable; visual dashboard acceptance remains a learner exercise.
- Local commits are now authorised. No AWS provisioning or remote push was performed. Account plan, credit balance/expiry and a usable AWS profile remain required before a cost-reviewed deployment.

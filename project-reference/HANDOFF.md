# FinTrust Project Handoff

**Last updated:** 29 September 2026  
**Target submission:** 15 October 2026  
**Purpose:** Start here in a new chat, AI tool, or work session. This document is intended to preserve project context if previous chat history is unavailable.

## Start Here

1. Read this handoff first.
2. Run `git status --short --branch` before editing. There are changes not yet committed; preserve them.
3. Read [the component guide](component_guide.md) to understand the actual code path and which modules are placeholders.
4. Read [remaining work](remaining_work.md) for the delivery plan and [completed work](completed_work.md) for evidence.
5. Do not assume the target architecture is deployed. No AWS resources have been deployed from this repository.

## Project Goal

Build and explain the FinTrust Bank SA transaction insights and risk-monitoring capstone. The learner wants to understand each component, the reasons for design decisions, and failure behavior well enough to implement and explain the system themselves. Prioritize teaching through actual code, data flow, and tests over polishing presentation language. Target submission is 15 October 2026.

## Repository Snapshot

- Workspace root: `C:\Users\Nompilo\OneDrive\Desktop\fintrust`
- Local branch: `main`
- Git author identity is configured locally. Do not repeat personal identity details unless needed.
- Six existing local Conventional Commits are present through Week 13 Days 3–5.
- No `origin` remote exists; no commits have been pushed.
- The user previously authorized local commits but said not to push yet. For newly changed work, leave it uncommitted unless the user asks to commit.
- Current uncommitted changes (last checked): root `README.md` modified; old `docs/live_demo_script.md` and `docs/presentation_notes.md` removed as they were moved; `tests/data_quality/test_constraints.py` changed to expect PostgreSQL `RestrictViolation`; `project-reference/` is untracked and contains moved/new reference documents. Do not revert or overwrite these changes.

## Current State: Actual Versus Target

### Implemented in repository; not deployed to AWS

- S3/IAM/SSM/DynamoDB/DLQ/monitoring provisioning scripts.
- PostgreSQL schema, synthetic seed data, views, analytics SQL, and flag function.
- S3-event-oriented ingest handler: CSV validation/transformation, direct RDS insert, idempotent transaction IDs, row quarantine to S3, JSON logs, and invocation failure re-raise behavior.
- Local Flask API routes: `/v1/health`, `/v1/transactions`, and `/v1/insights`.
- Unit tests for validation, ingest behavior, DynamoDB helpers, query logic, and API behavior.
- Opt-in PostgreSQL constraint tests.

### Not implemented or not deployed

- AWS S3/RDS/DynamoDB/Lambda/API Gateway resources and actual live triggers.
- Final SQS FIFO work queue and connected scoring pipeline. Current ingest writes directly to PostgreSQL; it does not send valid rows to FIFO.
- `score.py` is a skeleton: it is not connected, does not persist DynamoDB scores, and assumes SQS message bodies are already dictionaries instead of JSON strings.
- `alert.py` is a placeholder and does not call SES.
- `report.py` is a placeholder and does not generate/store reports or use EventBridge.
- API Gateway routing and AWS_IAM authorization; the Flask app is local code only.
- Visual CloudWatch dashboard and all final required custom metrics.
- Full deployed end-to-end evidence.

Do not tell the user these target components are live. See [component_guide.md](component_guide.md) and [architecture.md](../docs/architecture.md).

## Verified Environment

- Windows 11, PowerShell.
- Python 3.14.7 at `%LOCALAPPDATA%\Programs\Python\Python314\python.exe`. The GitHub Actions workflow targets Python 3.11.
- Git for Windows is installed.
- PostgreSQL 18.6 installed at `C:\Program Files\PostgreSQL\18\bin`; service `postgresql-x64-18` was running and `localhost:5432` accepted connections.
- AWS CLI 2.37.5 at `C:\Program Files\Amazon\AWSCLIV2\aws.exe`; its directory is not on PATH and no AWS profiles were configured at last check.
- No `gh` CLI, Docker, or Postman was detected. MySQL Workbench is not required; this is a PostgreSQL project.
- Use the training AWS account and verify budget alarms before any provisioning. Never use root credentials. Never request or store passwords/API secrets in chat or committed files.

## Test and Database Evidence

- Before PostgreSQL was configured for pytest, the complete local suite reported **15 passed, 5 skipped**; the skipped tests were PostgreSQL integration checks.
- The user created a disposable local database named `fintrust_test` in PostgreSQL 18.6.
- The first run of `tests/data_quality/test_constraints.py` gave **4 passed, 1 failed**. The delete test failed only because it expected `ForeignKeyViolation`; PostgreSQL correctly raised `RestrictViolation` for `ON DELETE RESTRICT`.
- `tests/data_quality/test_constraints.py` has since been updated to expect `psycopg2.errors.RestrictViolation`.
- The user reran the DB tests successfully: **5 passed in 0.56s**.
- The combined full suite with the DSN configured has not yet been rerun. Next verification should combine 15 unit tests + 5 database integration tests and aim for **20 passed**.
- `schema.sql` and `seed.sql` are applied by the PostgreSQL test fixture. Test data (five synthetic customers/accounts, 200 synthetic transactions, and qualifying risk events) remains in `fintrust_test`; each invalid test operation is rolled back.
- Never run integration tests against production or the future live-demo database.

## Immediate Next Action

The user's PowerShell prompt was in the project root after the successful PostgreSQL test run. If `FINTRUST_TEST_DATABASE_URL` is still set in that same PowerShell session, run:

```powershell
$python = "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"
& $python -m pytest -q
```

Expected: 20 passed. Then remove the local DSN from that shell:

```powershell
Remove-Item Env:FINTRUST_TEST_DATABASE_URL
```

If the variable is no longer set, recreate it with a hidden local password prompt (never paste the password into chat):

```powershell
$python = "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"
$env:FINTRUST_TEST_DATABASE_URL = (& $python -c "import getpass; from psycopg2.extensions import make_dsn; print(make_dsn('host=localhost port=5432 dbname=fintrust_test user=postgres', password=getpass.getpass('Local PostgreSQL password: ')))")
& $python -m pytest -q
Remove-Item Env:FINTRUST_TEST_DATABASE_URL
```

After the full suite, continue with a learning exercise: trace one valid row and one invalid row from `samples/transactions_day2.csv` through `ingest.validate_row`, `transform_row`, `_load_rows`, `process_csv`, and the tests in `tests/test_ingest.py`. Explain each function's input, output, and error behavior to the user. The ingest tests mock storage/database boundaries; they do not prove S3 or RDS deployment.

## AWS / GitHub Status

- No AWS resources have been created by the assistant. Infrastructure scripts can create billable/account-level resources when run.
- No AWS CLI profile existed at last check. Configure only through the cohort's approved process after checking the training account and billing alarm.
- No private GitHub remote exists yet. User is `Nompil` on GitHub and intends a private repository; facilitator access is required. GitHub CLI is unavailable, so create the private repository in the browser, then add its URL as `origin` when ready. Do not push unless the user asks.

## Useful Files

- [Project-reference index](README.md)
- [Component guide](component_guide.md)
- [Completed work](completed_work.md)
- [Remaining work](remaining_work.md)
- [Local software setup](local_software_setup.md)
- [Live demo script](live_demo_script.md)
- [Stakeholder presentation notes](presentation_notes.md)
- [Architecture](../docs/architecture.md)
- [ERD](../docs/erd.md)
- [Data governance](../docs/data_governance.md)
- `fintrust/` application package
- `infrastructure/` AWS provisioning scripts
- `sql/` schema, seed, and analytical artifacts
- `tests/` local unit tests and opt-in PostgreSQL integration tests

## Continuation Rules for Another Assistant

- Read current file contents before editing. The user may edit or format files between sessions.
- Preserve uncommitted user/assistant work; do not reset, checkout, or discard changes.
- Work one component at a time: explain its purpose, trace its inputs/outputs, implement/test, then teach back what the result means.
- Run the narrow relevant test immediately after each code change; run the full suite at logical milestones.
- Keep the user informed about what is locally tested versus AWS-deployed.
- Do not create AWS resources without confirming the intended account/region/cost controls; never handle credentials in chat.
- Do not commit or push without checking the user's current preference. No remote or push currently exists.
- After meaningful work, update this handoff and the relevant completed/remaining status so another session can resume accurately.

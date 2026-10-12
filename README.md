# FinTrust
Transaction Monitoring & Risk Alert Platform

## Business Problem
Imbokodo Bank is a **fictional case-study client**. Its operations team needs to reconcile transaction files, identify explainable risk and investigate exceptions without losing source evidence or confusing bad data with risky transactions.

## Product North Star
**What happened? Why is it risky? What should I do next?**

FinTrust helps a Risk Analyst answer these questions quickly, consistently and with evidence.

## Solution
FinTrust admits CSV files, protects transaction identity, quarantines invalid rows, scores accepted transactions and preserves accountable human review. It monitors financial events; it does not move funds or establish fraud.

## Core Flow
```text
Risk Analyst -> CSV -> input S3 -> ingest parsing -> FIFO candidates
  -> database-aware validation -> quarantine -> correction / revalidation
  -> accepted ledger + LOW / MEDIUM / HIGH scoring -> risk event
       -> MEDIUM / HIGH review -> decision
       -> HIGH alert delivery (independent of review)
  -> transactions / insights / reports / audit
```
Actual processing order is **RECEIVED -> QUEUED -> VALIDATED -> SCORED -> STORED**. All valid risk levels remain in the ledger. Local uploads use mocked AWS and direct SQL processing; they do not prove live FIFO/Streams/SES integration.

## Users and Roles
| Role | Accountability |
|---|---|
| Risk Analyst | Upload, investigate, correct quarantine and decide scoped reviews |
| Auditor | Read-only scoped evidence, reports and audit |
| Administrator | User/account governance and oversight |
| Maintainer | Technical recovery, separate from financial review decisions |

## Architecture
S3 preserves versioned source and quarantine evidence. SQS FIFO orders candidate processing; private PostgreSQL owns financial truth and audit. DynamoDB provides immutable projections and delivery coordination. Lambda separates ingest, scoring, alerts, API and reports; SES supplies email delivery. Gateway endpoints support private workers without NAT. Region: **af-south-1**.

See the [official-icon AWS architecture](docs/presentation/diagrams/FinTrust_AWS_Architecture.pdf) and [baseline ERD](docs/presentation/diagrams/FinTrust_ERD.pdf). The ERD predates additive migration 003; its lifecycle audit extension is explained in the Master and [technical contract](docs/architecture/TRANSACTION_LIFECYCLE.md). Diagrams are not deployment proof.

## Technology
Python, PostgreSQL, JavaScript/HTML/CSS, AWS Lambda/S3/SQS/DynamoDB/RDS/SES, CloudFormation, scoped IAM, pytest and GitHub Actions. Lambda target: Linux x86_64 / Python 3.12; dedicated compatibility tests use PostgreSQL 16.

## Repository Structure
```text
frontend/       browser entries, JavaScript and CSS
backend/        fintrust/, migration_runner/, src/ runtime packages
infrastructure/ AWS templates/renderers and IAM contracts
sql/            authoritative schema, migrations and seeds
tests/          regression tests and scenario fixtures
tools/          local operations, packaging and document generation
docs/           Master, Progress, supporting contracts and EVIDENCE
build/          ignored generated artifacts and disposable verification output
```

## Running Locally
Run from the repository root with the configured dedicated loopback PostgreSQL test database and project Python environment:
```powershell
py -m pip install -r requirements.txt
py tools/local.py check
py tools/serve_release1_demo.py --role Analyst --reuse-auth
```
Open **http://127.0.0.1:5001/release1**. Reuse preserves the existing local hashed identity; it does not issue a new credential. First-time setup and identity provisioning are documented in [local operations](docs/RELEASE1_OPERATIONS.md). Never publish access tokens or reset the schema to conceal a failure.

## Testing
```powershell
py tools/local.py test
py tools/local.py test --database
```
Latest source checkpoint `7397f22`: **756 passed, 1 skipped, zero failures**; focused gate **62 passed**; disposable PostgreSQL 16 lifecycle gate **21 passed**. The administrator-only skip has separate prior PG16 proof, not live migration-003 privilege proof. [Recorded results](docs/EVIDENCE/12-e2e/transaction-lifecycle/verification-summary.json).

## Current Status
[Project Progress](docs/FinTrust_Project_Progress.pdf) is the living status/history record. AWS foundation stages are historically verified; complete current-release integration, live schema bootstrap and a fresh Linux artifact gate remain pending. Next: Quarantine Recovery.

## Full Project Documentation
[Project Master](docs/FinTrust_Project_Master.pdf) explains business rules, architecture, data, security, cost and limits. Editable sources are [Master](docs/source/project-master.json) and [Progress](docs/source/project-progress.json); regenerate both with `python tools/build_project_docs.py` (ReportLab and PyMuPDF required). [Documentation inventory](docs/source/documentation-inventory.json) records each disposition. Update these sources instead of creating new status documents. Active operational contracts remain in place; superseded narrative is under `docs/archive/`.

## Evidence
[docs/EVIDENCE/](docs/EVIDENCE/) preserves sanitized tests, historical AWS checks, failures and recovery. Local/mock success is not live deployment evidence.

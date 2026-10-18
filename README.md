# FinTrust
Transaction Monitoring & Risk Alert Platform

## Submission and live demonstration — 18 October 2026

**[Open Imbokodo Bank on AWS](https://qzgzopn8o4.execute-api.af-south-1.amazonaws.com/dev/)** · [Demonstration guide](docs/CLOUD_DEMONSTRATION_RUNBOOK.md) · [Final live evidence](docs/EVIDENCE/13-cloud-live/)

This branch contains the consolidated presentation release. The application is hosted on API Gateway and Lambda in Cape Town (`af-south-1`), with Cognito sign-in and a private PostgreSQL ledger. Demonstration data is fictional. Evaluators can read this repository without an AWS account; application access requires a separately provisioned account. Passwords and MFA codes are never published here.

Verified live workflows include analyst sign-in, CSV ingestion, stored transactions, risk scoring, review decisions, quarantine correction recovery and scheduled report generation. The final demonstration ledger contains four transactions. The October report is a three-transaction snapshot created before the correction. Temporary setup endpoints, repair stacks and operator permissions were removed.

Known limits: cloud user creation uses an AWS operator workflow; the administrator's user-management page is read-only. SES recorded receiving-server deliveries, but Outlook Inbox placement of transaction alerts remains unconfirmed. Regional Lambda capacity is shared at ten concurrent executions; this is a controlled demonstration, not production load certification. Hosting is temporary and will be stopped after the presentation to control costs.

For assessment, start with the demonstration guide and final live evidence above. Older screenshots, PDFs and progress records retain their original dates and describe earlier checkpoints; they do not override the final live verification.

## Business Problem
Imbokodo Bank is a **fictional case-study client**. The operations team needs to reconcile transaction files, investigate risk and retain source evidence. Invalid data and valid high-risk transactions need separate outcomes.

## Product North Star
**What happened? Why is it risky? What should I do next?**

FinTrust helps a Risk Analyst answer these three questions quickly, consistently and with evidence.

## Solution
Upload CSV files, protect transaction identity, quarantine invalid rows, score accepted transactions and record human review decisions. It monitors financial events; it does not move funds or establish fraud.

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

## Local User Management
Open Administration > Users to create named records and manage role/status. Enroll each record separately before sign-in. Use the hidden enrollment prompt for an existing active record:
```powershell
py tools/provision_local_user.py --username analyst03 --registry .env.release1-auth.json
```
Use a unique random credential of at least 32 characters; never put it in commands, Git or evidence. Enrollment preserves role/account scope and refuses credential replacement. This section describes local authentication; the cloud application uses Cognito. Disabled users cannot sign in; Admin explicitly reassigns unresolved reviews. Optional `FINTRUST_REVIEW_SLA_SECONDS` configures queue deadlines; none is assumed by default.

## Testing
```powershell
py tools/local.py test
py tools/local.py test --database
```
The Linux verification workflow builds the Lambda package, verifies production imports, runs PostgreSQL 16 service-role checks, browser gates and the full regression suite. [Successful release verification at `ab5302d`](https://github.com/Nompil/fintrust/actions/runs/39067872212) includes the correction batch-lock regression. Later submission updates document live results and cleanup; they do not represent a new deployment. Historical test counts remain in their dated evidence records.

## Current Status
The AWS demonstration is deployed. Use the [cloud demonstration runbook](docs/CLOUD_DEMONSTRATION_RUNBOOK.md) for its verified state, remaining limitations, presentation sequence and shutdown plan. [Project Progress](docs/FinTrust_Project_Progress.pdf) preserves earlier implementation history. AI remains planned and is not part of the demonstrated product.

## Full Project Documentation
[Project Master](docs/FinTrust_Project_Master.pdf) explains business rules, architecture, data, security, cost and limits. Editable sources are [Master](docs/source/project-master.json) and [Progress](docs/source/project-progress.json); regenerate both with `python tools/build_project_docs.py` (ReportLab and PyMuPDF required). [Documentation inventory](docs/source/documentation-inventory.json) records each disposition. Update these sources instead of creating new status documents. Active operational contracts remain in place; superseded narrative is under `docs/archive/`.

## Evidence
[docs/EVIDENCE/](docs/EVIDENCE/) preserves sanitized tests, historical AWS checks, failures and recovery. Local/mock success is not live deployment evidence.

Repeated screenshots are consolidated in the [screenshot index](docs/EVIDENCE/SCREENSHOT_INDEX.md); historical capture names resolve through its SHA-256 alias map.

## Local end-to-end scenario verification

The [20-scenario evidence record](docs/EVIDENCE/12-e2e/scenario-verification/SCENARIO_RESULTS.md) traces input, processing, database state, UI/API evidence, audit and final outcome. Those selected local runs passed 125 tests with no failures or skips. Four browser gates cover investigation, multi-user workflows, all three review outcomes and CSV A/B admission/report exports. Each scenario labels browser versus API evidence. These local scenarios mock AWS transports; the separate [live cloud evidence](docs/EVIDENCE/13-cloud-live/) records actual AWS processing and owner-confirmed analyst access.

# FinTrust: Transaction Insights and Risk Monitoring

FinTrust checks transaction CSV files, stores valid rows, and provides a read API for reviewers. This repository covers the Week 13 Day 1-3 foundation of the Praesignis capstone. Automated risk scoring, alerts and monthly reports are later milestones.

## Start here

- [Complete system documentation](output/pdf/fintrust_system_documentation.pdf)
- [System design source and SDLC record](docs/system_design.md)
- [What is required and what is still missing](project-reference/requirements_day1_day3.md)
- [Step-by-step learning guide](project-reference/learning_guide.md)
- [Architecture and ERD PDF](output/pdf/fintrust_architecture_and_erd.pdf)
- [Editable draw.io diagrams](docs/diagrams/fintrust.drawio)
- [Current status and next steps](project-reference/upcoming_features.md)

## Current implementation

The ingest handler reads CSV objects, validates rows, inserts valid records into PostgreSQL and writes rejected rows to S3 quarantine. Retries of the same source object version use the same transaction IDs. Infrastructure scripts configure S3, IAM, SSM, DynamoDB, an ingest DLQ and CloudWatch alarms.

The Flask API implements health, transactions, insights, accounts and overview endpoints. The dashboard at `/` displays activity charts, currency totals, a filtered ledger and local CSV intake. Transaction queries support date filters and `limit`/`offset` pagination. Insights read a pre-existing DynamoDB item keyed by account and date; the automated score writer is not connected.

These are repository implementations, not proof of deployment. See the [review](project-reference/requirements_day1_day3.md) for security gaps, prototype modules and evidence still required. No deployed end-to-end result or zero-cost claim is made.

## Run locally (PowerShell)

```powershell
py tools/local.py test
py tools/local.py setup
py tools/local.py check
py tools/local.py test --database
py tools/local.py ingest
py tools/local.py serve
```

Run these one at a time. Setup prompts for your local PostgreSQL administrator password without displaying it; the password is never stored. The generated application credentials go into ignored `.env`. Practice uses `fintrust_local`; tests use `fintrust_local_test`. AWS services are simulated in the local exercises.

The [learning guide](project-reference/learning_guide.md) explains each command, expected output, browser URL and troubleshooting step. Dependencies are installed on this machine; a fresh environment needs `py -m pip install -r requirements.txt` first. Use `py` if the `python` command points to the Windows Store alias.

## Repository map

| Folder | Contents |
|---|---|
| `fintrust/` | Application code and clearly identified later-stage prototypes |
| `sql/` | Schema, synthetic seed data, views, reports and stored function |
| `infrastructure/` | AWS setup scripts; not a complete deployed stack |
| `tests/` | Unit, mocked AWS and opt-in PostgreSQL tests |
| `docs/` | Technical submission documents and diagrams |
| `project-reference/` | Four working references: requirements, learning, progress and upcoming work |
| `samples/` | Synthetic transaction CSV |

The [documentation index](project-reference/README.md) links each topic once. The business aim is to reduce manual checking and make rejected data traceable; effectiveness and financial savings have not been measured.

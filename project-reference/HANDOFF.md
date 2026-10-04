# FinTrust project handoff

## Resume point

Latest checkpoint: infrastructure/FINAL_VERIFICATION.md. Full local suite: 158 passed,
0 failed, 1 skipped. Region consistency fixed and Linux verifier strengthened.
Inventory commands and blank parameters are committed. Linux execution remains
blocked by no installed Linux runner and no Git remote; no AWS access is authorized.
Resume that gate, not the audit. Preserve unrelated untracked documents.

The active task is budget-first security and deployment preparation. Read infrastructure/BUDGET_FIRST.md for decisions, evidence and remaining gates. The user authorizes small, coherent local commits and explicitly prohibits AWS account access or deployment in this phase. Do not push. Work only in this workspace; preserve existing changes.

The proposed deployed path is S3 -> ingest outside the VPC -> FIFO queue -> scoring inside the VPC -> PostgreSQL ledger and immutable DynamoDB projection -> DynamoDB Streams -> alert outside the VPC. Query and report functions remain private database clients. Conditional alert claims prevent blind resends after uncertain SES outcomes. Legacy direct SQL helpers remain for local exercises.

The shared Lambda builder targets Linux x86_64 / Python 3.12 and includes SQL, frontend assets and the RDS CA bundle. A structural archive check is distinct from Linux execution and live AWS verification. The manual GitHub workflow builds and verifies only.

## Local checks

Use C:\Users\Nompilo\AppData\Local\Programs\Python\Python314\python.exe. The bare python alias may not work. Run tools/local.py test --database for the disposable fintrust_local_test database; never print connection strings. Current test and package evidence is recorded in the budget-first report.

Check git status before editing. Continue from outstanding gates rather than restarting the audit or regenerating presentation documents. Do not add dates or implementation-status boilerplate to stakeholder-facing presentation copy.

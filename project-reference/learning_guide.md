# Step-by-step learning guide

Read the [requirements](requirements_day1_day3.md) for scope. Use the exercises below to run the project yourself.

## Test it yourself: local practice

Use this section in order. You do not need to send each result back to anyone: compare your screen with the expected output. Stop at a failed step, read the error table below, and repeat that step after correcting it.

### A. Open the right terminal

In VS Code, choose **Terminal > New Terminal**. Use PowerShell and run:

```powershell
Set-Location 'C:\Users\Nompilo\OneDrive\Desktop\fintrust'
py --version
```

Python 3.14 is installed on this computer. CI uses 3.11; local practice can use the installed version. If `py` is unavailable, replace it in these commands with:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" --version
```

Dependencies are already installed in the current interpreter. To use a separate environment instead:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then replace `py` below with `.\.venv\Scripts\python.exe`. No PowerShell activation-policy change is needed.

### B. Run tests before connecting a database

```powershell
py tools/local.py test
```

You should see dots for passing tests and `s` for skipped database tests. Current expected summary: **33 passed, 7 skipped**. The seven skipped checks require the database. The helper deliberately ignores any existing test database URL in your shell. An `F` means a failing assertion; an `E` means setup or execution failed. The summary gives the current total.

Think of this as checking the worker's instructions before opening the real filing cabinet. These tests use fake AWS credentials and mocked service calls; they do not deploy resources.

### C. Connect PostgreSQL once

The Windows service `postgresql-x64-18` was running when checked. Start the connection setup:

```powershell
py tools/local.py setup
```

1. Press **Enter** for port `5432` unless you installed PostgreSQL on another port.
2. Press **Enter** for administrator username `postgres` unless yours is different.
3. Type your PostgreSQL password. Nothing appears while you type; press **Enter**. This is the password chosen during PostgreSQL installation, not your Windows password.

The setup connects to your local PostgreSQL server, creates a separate `fintrust_local_app` login, and creates two databases:

| Database | Purpose |
|---|---|
| `fintrust_local` | Your practice data and API demonstration |
| `fintrust_local_test` | Disposable data for automated database tests |

It loads the schema, 200 synthetic transactions, account-summary view and stored function into the practice database. The test database is prepared when you run database tests. It saves the generated application password in ignored `.env`; it does not save the administrator password. You do not need to edit or copy `.env.example` first.

Expected first setup result:

```text
Setup complete. App credentials saved in ignored .env; administrator password was not saved.
Practice database: fintrust_local; separate test database: fintrust_local_test.
Connected: fintrust_local as fintrust_local_app
Transactions: 200; accounts with transactions: 5
```

An existing `.env` for a different setup is left unchanged. An existing database owned by another login is also left unchanged. Do not delete an existing configuration or database just to make this command succeed; check what it belongs to first.

Repeatable connection check:

```powershell
py tools/local.py check
```

This reads the saved connection details and prints counts, not passwords. Connection setup is complete only when this command succeeds on your machine.

### D. Run the real database checks

```powershell
py tools/local.py test --database
```

Expected for the current suite: **40 passed**, with no skipped database checks. This total includes the seven new local-workflow checks. The database checks prove that negative amounts, invalid currencies and broken relationships are rejected. They also check risk-report duplicate handling and a running balance of `100 - 25 - 10 = 65`.

The helper always uses `fintrust_local_test`. It keeps your practice ledger separate from test data.

### E. Follow the sample CSV into the database

Open `samples/transactions_day2.csv`. There are four rows: two valid, one negative amount, and one unsupported currency.

```powershell
py tools/local.py ingest
```

Expected counts:

```json
{
  "rows_received": 4,
  "rows_valid": 2,
  "rows_quarantined": 2,
  "quarantine_rate_percent": 50.0
}
```

Open `output/local/quarantine.jsonl` to read the rejected rows and reasons. PostgreSQL is real; S3 is simulated in this exercise. The helper copies the simulated quarantine file to disk so you can inspect it.

Run `py tools/local.py check`: a fresh database should now have **202 transactions**. Run `ingest` again, then `check` again: it should remain **202**. The same source identity produces the same transaction IDs, so replay does not create more rows. `rows_valid` means accepted rows, not newly inserted rows.

Keep the supplied sample unchanged during this exercise. Changing its contents while reusing the same practice source identity would test different behavior.

### F. See API responses in your browser

```powershell
py tools/local.py serve
```

Keep that terminal open. It runs Flask on `127.0.0.1:5000`. PostgreSQL remains real; DynamoDB runs as an in-memory simulation with a preloaded score of 45. The score is a teaching fixture, not a calculated risk assessment. The simulation disappears when you stop the command.

Open these addresses in your browser:

| Address | Expected result |
|---|---|
| `http://127.0.0.1:5000/v1/health` | `{"status":"ok","db":"ok"}` (field order may differ) |
| `http://127.0.0.1:5000/v1/transactions?account_id=20000000-0000-4000-8000-000000000001&limit=2` | Two rows; `meta.count` 2, `limit` 2, `offset` 0 |
| `http://127.0.0.1:5000/v1/transactions?account_id=20000000-0000-4000-8000-000000000001&limit=2&offset=2` | Next two rows |
| `http://127.0.0.1:5000/v1/transactions` | Missing `account_id` error |
| `http://127.0.0.1:5000/v1/insights?account_id=20000000-0000-4000-8000-000000000001` | Preloaded score; `risk_score` is serialized as `"45"`; no TTL field |
| `http://127.0.0.1:5000/v1/insights?account_id=20000000-0000-4000-8000-000000000005` | No score found |

To see status codes too, open a second PowerShell terminal:

```powershell
curl.exe -i 'http://127.0.0.1:5000/v1/health'
curl.exe -i 'http://127.0.0.1:5000/v1/transactions'
curl.exe -i 'http://127.0.0.1:5000/v1/insights?account_id=20000000-0000-4000-8000-000000000005'
```

Expect **200**, **400**, and **404**, respectively. The missing-score response is a successful test of the not-found behavior. Stop Flask with **Ctrl+C** in its original terminal.

### G. Look inside PostgreSQL using pgAdmin

Use the existing local server connection in pgAdmin, then expand **Databases > fintrust_local > Schemas > public > Tables**. Right-click `fintrust_local`, choose **Query Tool**, and run:

```sql
SELECT COUNT(*) FROM transactions;

SELECT tx_id, account_id, amount, currency, tx_date, raw_file
FROM transactions
ORDER BY tx_date DESC, tx_id DESC
LIMIT 10;

SELECT * FROM v_account_summary ORDER BY account_id;

SELECT COUNT(*) FROM transactions
WHERE raw_file = 'raw/transactions_day2.csv';
```

The last query should return **2** after the ingestion exercise, including after replay. If creating a pgAdmin server connection, use host `127.0.0.1`, your local port, and your existing PostgreSQL login. Never share a screenshot showing a password or connection string.

### Troubleshooting

| Problem | What to check |
|---|---|
| `python` cannot run or opens the Store | Use `py` or the full interpreter path in section A |
| `ModuleNotFoundError` | Install `requirements.txt` using the same interpreter used for the helper |
| Database connection failed | Check Windows Services for PostgreSQL, port 5432 and your PostgreSQL password |
| You do not remember the password | Check your installation notes or existing pgAdmin login; do not guess repeatedly or change authentication to trust |
| `.env` belongs to another setup | Review it locally; preserve it before choosing another setup |
| Database command fails with code `42501` | Setup needs a PostgreSQL administrator allowed to create a role/database |
| `/health` returns 503 | Run `check`; resolve the database connection first |
| `WinError 5` mentions `pytest-of-Nompilo` | Run tests through `py tools/local.py test --database`; the updated helper uses a fresh temporary folder per run |
| Database tests skip | Use `test --database` after `setup` succeeds |
| Port 5000 already in use | Stop the earlier Flask terminal with Ctrl+C, then retry |
| Insights return 404 | Use the first sample account and today's date; the fixture is created on each `serve` start |

### Record your progress

Add your own dated entry to [daily progress](daily_log.md): command, expected result, actual result and one sentence explaining what you learned. Do not mark the persistent database connection as complete until you personally see `Connected: fintrust_local`.

## Understand what you just ran


Think of FinTrust as a teacher checking a pile of worksheets. A CSV is the pile. Each row is one worksheet. We check each one, put good ones in the correct folder, and put bad ones aside with a note explaining the problem.

## 1. The data comes first

A **customer** is a person. An **account** belongs to a customer. A **transaction** belongs to an account. PostgreSQL keeps these links, like labelled folders inside a filing cabinet.

A primary key is a record's unique name tag. A foreign key points to another record's name tag. That is why a transaction cannot belong to an account that does not exist. A UUID is the long identifier on the tag; it is not a password.

Open `sql/schema.sql`. The five tables are customers, accounts, transactions, risk_events and alerts. The last two have storage definitions already, but automated scoring and alert delivery are future work. `NOT NULL` means a value is required. `CHECK` means a value must obey a rule. `NUMERIC(15,2)` stores money with two decimal places.

## 2. Day 1: prepare the receiving area

**Amazon S3** is the file cupboard. A bucket is the cupboard; `raw/` and `quarantine/` are labels at the start of filenames, called prefixes. **Versioning** keeps earlier versions when a file is replaced. **IAM** is the permission list: which worker may open which cupboard? **SSM Parameter Store** holds configuration, including the protected database password. **KMS** manages encryption keys; the required customer-managed setup is still missing.

The scripts in `infrastructure/` describe how to set up services. Owning the instructions does not mean the services exist. We have not verified this stack in AWS.

**Lambda** is a worker called when an event arrives. For this build, the event says: 'A CSV was uploaded to this bucket under this key.' The worker reads the file. It does not receive the file contents directly in the event.

## 3. Day 2: follow one good row

Example: account `20000000-0000-4000-8000-000000000001`, amount `250.00`, date `2026-09-28`, type `debit`, currency `ZAR`.

1. `lambda_handler` visits every S3 event record. `_process_record` reads the requested object version.
2. `process_csv` reads the column names, then turns each row into a dictionary: a set of names and values.
3. `validate_row` checks required values, a positive finite amount, allowed currency/type, date and account-ID format.
4. `transform_row` turns the amount into `Decimal`, the date into a timestamp, and country into a cross-border flag. Without a timezone, the code assumes UTC.
5. The worker gives the row a repeatable ID based on the file version and row number. Seeing the same file version again produces the same ID.
6. `_load_rows` inserts it into PostgreSQL. `ON CONFLICT DO NOTHING` means an existing ID is not inserted twice.
7. A log reports how many rows were accepted or quarantined and how long processing took.

This duplicate protection covers retries of the same source version. Uploading the same business transaction in a new file can still create a new row. A future source transaction ID is needed for business-level deduplication.

## 4. Follow one bad row

Change the amount to `-5`. Validation returns a reason. The row goes to a JSON Lines file under `quarantine/`; valid rows continue. Short rows and rows with extra values are also isolated. Each source version has its own quarantine filename.

If the account looks like a UUID but does not exist, PostgreSQL rejects it. The worker uses a **savepoint**, like a bookmark, to undo that row's failed insert while keeping other good rows. A **commit** saves changes. A **rollback** undoes unfinished changes.

## 5. Day 3: distinguish a bad worksheet from a broken cupboard

A bad row can be put aside. An unreachable database means the worker cannot do the job. The code raises the error so AWS can retry after deployment. The setup script configures two asynchronous retries and a **dead-letter queue (DLQ)** to hold failed event messages for investigation.

The DLQ holds the event describing the source file, not a replacement copy of the file. Fix the database or permissions first, then replay the event. The source file version must still exist. CloudWatch logs explain what happened; alarms call attention to failures. Those AWS behaviors still need live evidence.

## 6. The API is the question counter

An API lets another program ask a precise question. A route is the address for one kind of question.

| Request | Plain-language meaning | Result |
|---|---|---|
| `GET /v1/health` | Can you reach the filing cabinet? | 200 if PostgreSQL responds; 503 if unavailable |
| `GET /v1/transactions?account_id=...` | Show this account's transactions | PostgreSQL rows; missing/invalid account ID gives 400 |
| `GET /v1/insights?account_id=...&date=2026-09-28` | Show this account's score for that date | DynamoDB item; missing score gives 404 |

`limit=10&offset=0` asks for the first ten rows. `limit=10&offset=10` skips those and asks for the next ten. Rows sort by date and ID. If records are added between requests, offset pages can shift; a future cursor can improve that.

DynamoDB is a lookup cabinet: give it the account and date, and it retrieves that item. The API can read a score, but the automated worker that creates scores is not connected yet. A preloaded score demonstrates reading only.

## 7. What a test proves

A unit test checks a small behavior with pretend database/AWS responses. Moto imitates AWS. PostgreSQL integration tests need a real disposable database. A deployed end-to-end test must upload a real file and check the resulting storage, API, logs and alerts. Passing the first kind does not prove the last kind.

Try explaining these aloud: Why quarantine one row? Why retry a database outage? Why does an account need to exist first? Why can the API return 404 even when it works correctly? What have we tested locally, and what still needs AWS proof?

## 8. Explore the dashboard and test it yourself

Run `py tools/local.py serve`, then open `http://127.0.0.1:5000/` in your browser. Leave that terminal running. If a practice server is already running, stop it with Ctrl+C before starting another.

The cards count transactions and active accounts. The graph counts transactions per day. Money is grouped by currency because adding dollars and rand without conversion gives a misleading total. Choose an account, change the dates and use the page buttons to inspect the ledger.

The insight is a preloaded example, like a labelled practice answer. Uploading a CSV does not calculate a new risk score yet. S3 and DynamoDB are pretend AWS services in this local exercise; PostgreSQL is your real local database.

The upload accepts other CSV files when they follow the required column names and use existing account IDs. Start with a copy of a supplied sample. Each file can contain at most 5,000 rows and 1 MiB of UTF-8 text. Choose up to five files per selection; they run one after another. Invalid rows appear with reasons. The same bytes uploaded again, even under a different filename, receive the same source identity. Editing the file changes that identity; business-level deduplication is future work.

In another terminal, run:

```powershell
py tools/local.py test --database
py tools/smoke.py
```

The full suite currently expects **52 passed**. Without `--database`, nine database tests are skipped. The smoke command checks the running server and prints actual response codes and a small timing sample. Its report is saved in ignored `output/local/smoke.json`. It reads data without adding transactions.

Try a missing account parameter, an unknown route and a POST to the health route. The expected codes are 400, 404 and 405. A healthy connection returns 200. These are meaningful outcomes: an error code can prove that a guardrail is working.

`.env.example` is the blank settings recipe shared in Git. `.env` is your private filled-in copy. Both have a purpose; `.env` stays ignored and must not be committed.

CI is the automatic test station after a GitHub push or pull request. CD is the delivery path into AWS. The repository has a manual API delivery workflow, but AWS identity, protected environments and deployment evidence remain to be configured. A workflow file alone does not prove that deployment works.

The formal reference is [the system design](../docs/system_design.md), with a [PDF edition](../output/pdf/fintrust_system_documentation.pdf). The diagrams explain the storage relationships, processing decisions, users and upload conversation.

## Component reference

| Component | What it does | Current status |
|---|---|---|
| `config.py` | Loads local `.env` values and AWS settings. For database values not supplied through environment variables, reads SSM Parameter Store with decryption; caches settings during a warm Lambda runtime. | Implemented; AWS parameters/profile not configured here. |
| `db.py` | Opens a PostgreSQL connection, executes parameterized reads, converts rows to dictionaries, rolls back query exceptions, and closes the connection. | Implemented; opens a new connection per call, no pool/RDS Proxy yet. |
| `dynamo.py` | Creates a reusable module-level DynamoDB resource and provides put/get/query helpers. | Implemented; score writer is not integrated. |
| `models.py` | Defines `Transaction` and `RiskScore` dataclasses for typed data representations and conversion. | Matches SQL and daily DynamoDB fields; current ingest/API path uses dictionaries and tuples. |
| `validators.py` | Contains shared CSV validation and prototype risk-score calculation/classification. | Ingest imports this validator; risk scoring is not called during ingest. |
| `ingest.py` | Reads the S3 event/object, checks CSV fields and values, transforms rows, writes valid transactions to RDS, quarantines invalid/constraint-failing rows, logs counts, and re-raises infrastructure failures. | Main implemented processing path; not deployed. Direct-to-RDS, not FIFO. |
| `score.py` | Calculates a risk score and returns approve/hold metadata. | Pure prototype only; Lambda handler raises NotImplementedError until FIFO/persistence exists. |
| `alert.py` | Represents the intended compliance alert behavior. | Raises NotImplementedError; does not call SES. |
| `query.py` | Builds parameterized transaction SQL and looks up a risk-score item by account/date. | Implemented data-access functions. |
| `api.py` | Exposes `/v1/health`, `/v1/transactions`, and `/v1/insights`; validates inputs and serializes responses. | Implemented locally with Flask/aws-wsgi. API Gateway routes/auth are not deployed. |
| `report.py` | Represents monthly reporting entry point. | Raises NotImplementedError; no report output or schedule yet. |


## Rehearse your explanation

1. Explain the problem: transaction exports need consistent checking and a clear record of rejected rows.
2. Show the ERD: each account belongs to a customer and each transaction belongs to an account.
3. Show the four-row CSV, two accepted rows and two quarantine reasons.
4. Query health, transactions and the preloaded insight; explain what 200, 400 and 404 mean.
5. Describe retries and the DLQ as an AWS deployment requirement still to be demonstrated.
6. Name what remains: connected scoring, alerts, reports and secure AWS deployment.

Business explanation: validation reduces manual checking, database relationships protect consistency, and source references help trace records. Benefits such as savings or fraud reduction still require measurement. Risk signals support human review; they do not move money or certify compliance.

Project target recorded in earlier planning: 15 October 2026; the supplied brief specifies end of Week 14 with presentations in Week 16. Use your facilitator's confirmed deadline.

## 9. Open the PDF documents

The files in `output/pdf` are normal PDFs. Text such as `%PDF`, `obj`, `stream` or `/Type/Page` means the editor is displaying the file format instead of rendering the document.

1. In VS Code, right-click the PDF in Explorer and choose **Reveal in File Explorer**.
2. In Windows File Explorer, right-click the file and choose **Open with > Microsoft Edge** (or an installed PDF reader).
3. If a PDF preview extension is already installed in VS Code, **Reopen Editor With** can select that viewer. A text editor cannot display PDF pages by itself.

Both PDFs were opened and every page rendered during verification: 16 system-document pages and three architecture/ERD pages. Neither required parser repair. Avoid editing the internal PDF text; content changes belong in the Markdown/design source and generators.

## 10. AWS implementation order

The current target is the Day 1-3 foundation, not every service in the final-capstone diagram. Local tests simulate AWS; they do not establish that these resources exist in an AWS account.

| Order | Implementation | Simple explanation | Evidence before moving on |
|---|---|---|---|
| 1 | Account plan, credit expiry/balance, region, MFA, scoped deployment identity and budget notifications | Check the spending arrangement and who can make changes | Account/region confirmed; estimated costs reviewed; credentials kept private |
| 2 | VPC, private subnets, database/Lambda security groups and service-access routes | Put the database behind locked doors | Database is not publicly accessible; PostgreSQL accepts traffic only from the intended application security group |
| 3 | S3 intake bucket, separate access-log bucket, versioning, public-access block, retention and required customer-managed KMS configuration | Store original files safely and record access | Bucket policies, encryption, logging and lifecycle settings verified |
| 4 | RDS PostgreSQL, schema, synthetic seed data, restricted SQL roles and SSM SecureString configuration | Create the cloud transaction ledger and protected settings | Connection and SQL checks succeed through an approved private access path |
| 5 | DynamoDB risk_scores, account/date keys and TTL | Create the fast daily-score lookup | A labelled test item can be written and read; TTL configuration is enabled |
| 6 | Ingestion Lambda, scoped role and S3 raw/*.csv notification | Check incoming files and separate invalid rows | Mixed-validity file produces accepted rows and quarantine records; replay does not duplicate the same source version |
| 7 | SQS ingestion DLQ, retry configuration and CloudWatch logs/metrics/alarms | Keep failed work visible and recoverable | Controlled dependency failure reaches the DLQ; alarm and replay demonstrated |
| 8 | Flask API Lambda and API Gateway read routes with authorization | Give the dashboard a controlled way to request data | Health, transaction pagination, insights, denied access and error responses verified; latency measured |

Private Lambda access to S3 and DynamoDB can use gateway endpoints. SSM and any other SDK calls need their own reviewed connectivity path; S3/DynamoDB endpoints alone do not provide general AWS API access. NAT gateways and interface endpoints can add costs. The current provisioning scripts do not yet close all encryption, logging and network gaps and are not a complete one-command deployment.

The first cloud demonstration should follow one file: upload to S3, inspect Lambda logs, verify accepted rows in RDS, inspect rejected rows in quarantine, and retrieve transactions through the authorized API. The DynamoDB insight remains a labelled test item until the score writer is connected.

After that foundation, implement the final FIFO/scoring pipeline, score persistence, SES alerts, EventBridge monthly reporting, production upload/flag/resolve endpoints, frontend hosting with real sign-in, tracing and deployed CI/CD evidence. Replace direct ingestion deliberately when introducing the FIFO writer; avoid two independent writers processing the same file.

The private RDS deployment also needs an approved way to apply SQL and troubleshoot connections. Opening PostgreSQL to the public internet is not the solution. A temporary controlled access method must be included in the network and cost review.

Customer-managed KMS keys have a recurring charge; credits may cover eligible usage but do not make a service inherently free. Account eligibility and service availability need confirmation before provisioning. Current references: [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/), [KMS pricing](https://aws.amazon.com/kms/pricing/) and [VPC pricing](https://aws.amazon.com/vpc/pricing/).

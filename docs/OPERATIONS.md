# FinTrust operations

This guide describes repository behavior and operating procedures. AWS resources have not been inspected or deployed in this phase. The current boundary is local preparation; repository creation, remote configuration, push and AWS inventory require separate approval.

## Local development

Install `requirements.txt` in your Python environment. On Windows, run these commands individually from the repository root:

```powershell
py tools/local.py test
py tools/local.py setup
py tools/local.py check
py tools/local.py test --database
py tools/local.py ingest
py tools/local.py serve
```

Setup prompts for the PostgreSQL administrator password without storing it. Application settings are saved in ignored `.env`. Practice uses `fintrust_local`; database tests use `fintrust_local_test`. AWS exercises use mocks. The local upload helper writes directly to SQL and does not demonstrate the cloud FIFO/Streams path. Keep local serving on loopback.

## Linux package gate

The [prepared CI procedure](../infrastructure/LINUX_CI_GATE.md) is the detailed runbook. After separate push approval, the first push to `main` triggers the workflow. Manual execution is also available when the workflow is on the default branch; avoid a duplicate run.

Ubuntu 24.04 x64 selects Python 3.12, installs approved dependencies and starts disposable PostgreSQL 16. It runs the complete test suite, downloads the public RDS CA bundle, builds the Linux archive and executes:

```sh
python3.12 tools/verify_lambda_linux.py build/fintrust.zip
```

Success requires exit zero and `All five archived handlers imported on Linux CPython 3.12.` The matching manifest must record `linux_execution_verified: true`. The evidence step requires a nonempty JUnit report with no failures, errors or skips and prints `Linux execution verified: TRUE`.

The verifier checks archive integrity, digest, manifest, handlers, native psycopg, bundled SQL and CA loading. Its import subprocess rejects DNS/socket operations through a Python audit hook; this is not an OS network sandbox. Ubuntu verification does not establish Amazon Linux 2023 compatibility or AWS integration.

Download the successful `fintrust-linux-verified` artifact before its seven-day expiry. Keep the ZIP, manifest, verifier log, CI evidence, commit SHA and run URL together. Rebuilding invalidates previous package evidence. The workflow has no AWS authentication, deployment or Lambda upload. Private GitHub runner usage and artifact storage remain subject to the repository plan.

## Inventory and deployment boundaries

After a successful Linux gate, request separate read-only inventory authorization. Use the [inventory runbook](../infrastructure/READ_ONLY_INVENTORY.md) and [parameter worksheet](../infrastructure/OPERATOR_PARAMETERS.md). An AccessDenied result means unknown, not absent. Do not retrieve secret values or application records for an infrastructure inventory. Cost Explorer queries require separate cost approval.

Reconcile account, Cape Town opt-in, ownership, names, IAM, database engine/TLS/users, SES identities, existing storage and budget before choosing reuse, import, update or creation. Never substitute another region automatically. The foundation creates no database instance. Existing names cannot be passed blindly to create-only templates.

Deployment requires its own reviewed changes and authorization. Consumers default to disabled; the report schedule is disabled. Before enabling traffic, verify database service roles, API identity, alarms and recipients, recovery procedures and cloud integration. Active X-Ray tracing is outstanding.

## Failure handling

| Failure | Repository behavior | Operator response after authorization |
|---|---|---|
| Invalid CSV row | Quarantine with reason and limited source fields; valid rows can continue | Correct source data and preserve the rejection record. Quarantine is still sensitive. |
| Unknown account during scoring | Quarantine before acknowledging the message | Reconcile the account/source; do not create a customer implicitly. |
| SQL or projection write failure | Retry; committed SQL result is reused by fingerprint | Fix dependency/policy failure. Preserve the original transaction ID and payload. |
| FIFO batch failure | Stop at first failure and return that message plus unprocessed IDs | Preserve per-account ordering during replay. |
| Exhausted transaction retries | FIFO transaction DLQ | Investigate before a separately approved redrive; new traffic can affect replay ordering. |
| Stream alert failure | Bounded retries, then alert failure queue | Recover from the immutable projection; failure metadata is not a permanent copy of all source data. |
| Uncertain SES outcome | `SENDING` or `UNKNOWN` prevents blind resending | Reconcile provider outcome before deciding to retry. Exactly-once email is not guaranteed. |
| Report failure | Async execution/delivery failure handling | Distinguish EventBridge delivery failure from Lambda execution failure. Re-run the intended month after diagnosis. |

Configured transaction queue retention is four days, visibility is 720 seconds and the redrive threshold is five receives. Failure queues retain messages for fourteen days. Stream retries are limited to five and record age to six hours. Retention is finite: investigate before evidence expires. The older replay helper is for S3 ingest events, not a generic FIFO or stream recovery tool. Invocation acceptance does not establish processing completion.

## Reports and retention

The monthly report uses the scheduled event's previous UTC month, or an explicit validated month. Results separate accounts and currencies and include historical context for movement calculations. It writes CSV and JSON under `monthly/YYYY-MM/transactions` with format extensions. These writes are not atomic as a pair; reruns reuse keys and versioned storage can retain earlier objects.

A monthly summary is not a complete ledger export. The intended lifecycle is twelve months of ledger data, then complete closed-period exports in S3 Standard for three years and Glacier Flexible Retrieval for seven years. The archival job and ledger deletion are not implemented. The current reports bucket transition applies only to `archive/` after 1,095 days, not `monthly/`.

Do not delete ledger rows until full exports, counts, checksums, reconciliation, dependent records, retention approval and restore tests are resolved. Preserve idempotency records. There is no DynamoDB TTL or quarantine expiry in the current foundation.

## Cost and monitoring

No NAT gateway is proposed. S3 and DynamoDB gateway endpoints avoid endpoint hourly charges; their underlying services remain billable. Existing RDS capacity, storage/backups, the proposed customer-managed key, retained S3 versions, logs and service usage all need a budget. A budget alarm is not a spending cap. No zero-cost or credit-coverage claim is made.

Processing templates retain logs for fourteen days. Alarm thresholds, notification recipients and operational response need validation before traffic. Review queue age/depth, DLQs, Lambda errors/throttles, API failures, database health and uncertain alert states. Never delete unrelated resources as cleanup.

## Evidence

The [evidence register](EVIDENCE/README.md) separates local results, prepared procedures and missing execution proof. Update it with real outputs only. See [architecture](architecture.md) for service placement and [security](SECURITY.md) for access boundaries.


### Local transaction-identity hardening checkpoint

[Identity, batch audit and duplicate-charge handling](IDEMPOTENCY.md)
records the new local implementation, additive migration and review/release gates.
Duplicate data is prevented/audited; distinct suspicious charges remain in the
ledger. No AWS migration or permission update was performed. New runtime source
requires a new Linux-verified artifact; the earlier uploaded ZIP remains evidence
for its previous source only. Stage 5 tagging recovery and deployment remain
separate, unexecuted approval checkpoints. Do not run older Stage 5 commands as a
release procedure for the new source.

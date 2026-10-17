# Cloud workbench preparation

149 focused tests passed on disposable PostgreSQL 16.15 and two Cognito PKCE
browser checks passed. No failures, errors or skips. AWS transport was mocked;
the preserved local ledger was not used. This is not live cloud E2E evidence.

The application now reads active workforce metadata from the existing account
scope table, supports cloud Analyst claims/notes/decisions without a local token
file, and admits uploads asynchronously through versioned S3. Financial SQL
writes remain in the FIFO worker. A fixed EventBridge tick drains bounded
authorized correction/projection work. Local governance retains its file lock.

The integrated template remains disabled by default. Runtime permission
supplements and S3 gateway prefix listing still require validated installation.
Cloud Cognito identity administration remains an operator workflow; the cloud
workforce page displays active scoped users and does not expose the local editor.

The database initialization packet separately passed its Linux package checks
and full isolated SQL/service-login rehearsal. Live base initialization has
succeeded, but subsequent migrations and complete cloud delivery remain pending.

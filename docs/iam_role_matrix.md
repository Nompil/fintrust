> Historical reference retained in place. Some implementation/status descriptions are superseded. Use the [current canonical guide](SECURITY.md) and [documentation inventory](../README.md) for current behavior and proposed disposition. No archive or deletion has occurred.

# IAM Role Matrix

## 1. Role Design

The scripts define separate execution roles. This matrix describes code, not verified deployed permissions. KMS permissions/key policies and Lambda VPC permissions are still missing.

| Lambda Function | Purpose | Current script permissions | Notes |
|---|---|---|---|
| Ingest Lambda | Read, validate, and persist CSV rows | S3 `GetObject`/`GetObjectVersion` on `raw/*`; S3 `PutObject` on `quarantine/*`; SSM `GetParameter` on the four DB parameters; SQS `SendMessage` on the ingest DLQ; scoped CloudWatch Logs writes | The current Day 3 implementation writes directly to RDS. The SQS FIFO scoring path is a later phase. |
| Score Lambda | Evaluate transaction risk | SQS receive/delete/attributes on the configured scoring queue; DynamoDB read/write on `risk_scores`; scoped SSM and Logs | The scoring function is not yet implemented. |
| Alert Lambda | Email compliance users | SES send actions on account SES identities; scoped Logs | SES sandbox and verified recipients still need setup. |
| Query Lambda | Read transactions and insights | DynamoDB `GetItem`/`Query`; scoped SSM and Logs | The local API is read-only. PostgreSQL access is currently credential-based; least-privilege SQL grants and deployed API Gateway AWS_IAM policies still need verification. |
| Report Lambda | Generate executive summaries | S3 `PutObject` on the report prefix; scoped SSM and Logs | Reporting code and schedule remain to be implemented. |

## 2. Security Principles

- No wildcard * actions in production roles.
- S3, SQS, DynamoDB, SSM, SES, and log permissions are scoped to named resources where supported.
- Bucket-specific and table-specific access is enforced.
- Deployment requirement: the database must not be public.

The current SSM design uses a shared application database credential. Separate read/write PostgreSQL roles should be created and granted only the SQL privileges each Lambda needs before production-style deployment. IAM permissions alone do not make a PostgreSQL user read-only.

## 3. Why this matters

This supports the core cloud architecture requirement: the platform must demonstrate least-privilege access, an AWS-aligned design, and a clear security boundary between processing roles.

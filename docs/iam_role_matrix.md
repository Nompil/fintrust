# IAM Role Matrix

## 1. Role Design

The system uses least-privilege execution roles for each Lambda function. This keeps the solution safer and easier to defend during architecture review.

| Lambda Function | Purpose | Permissions | Notes |
|---|---|---|---|
| Ingest Lambda | Validate and ingest files | S3 read access to raw bucket, SQS send access, RDS insert access | Reads uploaded CSVs and sends work to the queue |
| Score Lambda | Evaluate transaction risk | SQS receive access, DynamoDB put access, RDS update access | Applies scoring logic and writes risk output |
| Alert Lambda | Email compliance users | SES send access | Sends operational alerts on high-risk events |
| Query Lambda | Read transactions and insights | RDS read access, DynamoDB read access | Exposes customer-facing API functions |
| Report Lambda | Generate executive summaries | S3 write access, RDS read access | Produces monthly reporting output |

## 2. Security Principles

- No wildcard * actions in production roles.
- Each role is scoped to the minimum resource set it needs.
- Bucket-specific and table-specific access is enforced.
- The database is not public.

## 3. Why this matters

This supports the core cloud architecture requirement: the platform must demonstrate least-privilege access, an AWS-aligned design, and a clear security boundary between processing roles.

# Deployment parameter worksheet

Leave entries blank until the owner supplies them and authorized inventory confirms
them. This worksheet is nonsecret. Never paste credentials, tokens or passwords.
No values here authorize resource creation or deployment.

| Parameter | Confirmed value | Required check |
|---|---|---|
| AWS account ID / read-only profile | | Confirm identity and owner |
| Deployment region | | Must be af-south-1; enabled in account |
| Environment / stage | | Match naming and SSM paths |
| VPC ID | | Owner, DNS attributes, existing stack |
| Application private subnet IDs / AZs | | At least two AZs; approved routes |
| Database subnet IDs / AZs | | Existing DB subnet group; current template shares app subnets |
| Route table IDs / associations | | Include main/inherited routes; no NAT dependency |
| Lambda / database security group IDs | | DB 5432 only from app SG; reviewed egress |
| S3 / DynamoDB endpoint IDs and prefix lists | | Same region/VPC; approved policies and associations |
| RDS identifier / resource ID / ARN | | Preserve instance; rds-db ARN uses resource ID |
| RDS endpoint / port / engine version | | Private, TLS verify-full, PostgreSQL-compatible group |
| Database name | | Existing schema and owner |
| Scoring / API / report IAM database usernames | | Distinct least-privilege grants and rds_iam |
| RDS subnet / parameter group names | | Compare engine family before association |
| Raw bucket name / ARN / CSV prefix | | Existing notifications and ownership |
| Quarantine bucket name / ARN | | Restricted access and retention owner |
| Reports bucket name / ARN / prefixes | | Monthly versus ledger archive separation |
| DynamoDB table name / ARN / stream ARN | | Key schema, NEW_IMAGE stream, immutable state |
| Ingest FIFO URL / ARN | | Region, visibility and concurrency |
| Ingest FIFO DLQ URL / ARN | | Retention, maxReceiveCount, redrive permission |
| Stream failure standard queue URL / ARN | | Distinct from FIFO DLQ |
| KMS key ARN / alias | | One approved regional symmetric CMK; policy and existing ciphertext |
| Five execution role names / ARNs | | Ownership, trust, boundaries and scoped policies |
| Three database-service SSM paths | | Nonsecret host/name/user; no private runtime SSM calls |
| SES sender identity / sender address | | Verified in target region |
| SES recipient / sandbox status | | Verified recipient in sandbox; owner approval |
| API ID / stage / alias | | Regional REST API; AWS_IAM data methods |
| Frontend origin / authenticated access method | | Exact origin; signing/authentication decision |
| Report schedule / reserved concurrency | | Initially disabled; approved volume |
| Monitoring recipients / thresholds | | Backlog, errors, DLQ and held sends |
| Budget amount / currency / owner / thresholds | | Standing costs, alert recipients, teardown plan |
| Package bucket / object key / checksum | | Verified Linux archive; upload separately authorized |
| Data retention / backup / restore owner | | No ledger deletion without verified archive and restore |

Record missing values as unresolved. Placeholder values must not reach a deployment.

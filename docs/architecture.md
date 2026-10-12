# FinTrust architecture

FinTrust checks transaction exports and produces reviewable risk signals. It does
not move money or decide that a customer has committed fraud. The current cloud
handler path is implemented in the repository; AWS Integration remains In Progress.
Stages 1-4 and the disabled Stage 5 ingest deployment are recorded as verified;
the hardened release and private database migration have not been deployed.

Current diagrams and presentation wording: [presentation pack](presentation/FinTrust_Project_Planning_and_Design_Evidence.pdf). The full ERD and frozen local operating model take precedence over earlier milestone descriptions below. The final application release and live SQL bootstrap remain pending.

## Processing and storage

S3 raw CSV -> ingest -> SQS FIFO -> scoring -> PostgreSQL ledger -> DynamoDB
transaction projection -> DynamoDB Streams -> alert -> SES.

Ingest validates CSV structure and row values, writes rejected rows to quarantine,
and publishes valid jobs. Files are bounded to 1 MiB and 5,000 rows. FIFO messages
are grouped by account. Scoring checks account existence and serializes ledger
work per account. An unknown account is quarantined; a database outage is retried.

File hashing and durable batch audit precede row admission. Completed identical
uploads are audited rather than republished; repeated reliable row identities
are recorded as duplicates without a new ledger entry; identity conflicts are quarantined with structured reasons. Similar events without reliable identity
remain separate. See [identity and duplicate handling](IDEMPOTENCY.md) for the
exact source-reference scope, publication/retry boundaries and deployment gates.

Scoring commits the transaction, risk event and frozen result together in
PostgreSQL. `processed_transactions` records the transaction fingerprint and
original result. A replay reuses that result under the canonical UUID; a conflicting
UUID or upstream source identity fails. Distinct possible double charges stay in
the ledger and receive a configurable risk signal.
DynamoDB publication follows the SQL commit. If publication fails, a queue retry
can complete it without creating another ledger row or changing the score.

The DynamoDB key is `account_id` plus `score_date`. Despite its name, `score_date`
is `TX#<transaction UUID>` for current score projections and
`ALERT#<transaction UUID>` for delivery claims. Legacy daily summaries use a date
key; the current scorer does not generate those summaries. Alert processes only
high-risk transaction projections, verifies the stored score, then claims delivery
conditionally. Delivery-state updates do not trigger another email.

PostgreSQL owns relational ledger history and the saved scoring result. DynamoDB
provides a transaction lookup and operational delivery state. It does not replace
the ledger. The [ERD](erd.md) includes the replay table and legacy SQL alert fields.

## Five functions and their connections

| Function / handler | Runtime dependencies | Defined placement |
|---|---|---|
| Ingest / `fintrust.ingest` | S3 raw reads and quarantine writes; SQS publish | Outside the customer VPC |
| Scoring / `fintrust.score` | PostgreSQL; DynamoDB projection; S3 unknown-account quarantine | Private subnets |
| Alert / `fintrust.alert_delivery` | DynamoDB score/claim reads and writes; SES API | Outside the customer VPC |
| API / `fintrust.api` | PostgreSQL reads; DynamoDB point lookup | Private subnets |
| Report / `fintrust.report` | PostgreSQL analysis; S3 CSV/JSON writes | Private subnets |

The Stage 1-only [network renderer](../infrastructure/network.py) defines two
private application subnets and two private database subnets across two AZs,
with separate route tables. Only application routes use the S3/DynamoDB gateway
endpoints. SGs permit PostgreSQL only from the application group. No NAT, IGW or
interface endpoint is required. The older combined foundation is not the Stage 1
deployment entry point. The [cost plan](../infrastructure/DEPLOYMENT_BOOTSTRAP.md)
records the corrected `db.t4g.micro`, Single-AZ, 20 GiB gp3 PostgreSQL deployment.
Stages 1–4 were reported verified in AWS; the new identity hardening is local only.
Private functions use PostgreSQL and gateway-supported S3/DynamoDB APIs; they do
not call SSM, SES, SQS or Lambda APIs at runtime in the configured cloud path.
Nonsecret database settings are resolved at deployment. IAM tokens are signed
locally; Lambda manages queue/stream polling and log delivery.

Ingest originally used SQL account validation, and alert used SQL delivery state.
Moving account validation into scoring and delivery claims into DynamoDB lets
ingest and alert stay outside the customer VPC. No NAT Gateway or interface
endpoints are selected. The migration-path inventory verifies route associations
and security groups; runtime endpoint permissions and a live DB handshake still
require their own checks. Outside the customer VPC does not
mean that a function has an unauthenticated public application endpoint.

## Proposed private database maintenance path

The [private RDS migration plan](../infrastructure/PRIVATE_RDS_MIGRATION_PLAN.md)
selects a separate temporary Lambda in one existing application subnet, using
the existing app SG plus a temporary HTTPS client SG.
Read-only inventory confirms private PostgreSQL 16.15, forced TLS, no existing
VPC Lambda/EC2 runner, and only S3/DynamoDB gateway endpoints. The revised bootstrap
proposal adds one temporary Secrets Manager interface endpoint and two restricted
SGs so the runner fetches its secret directly. No secret is passed in invocation
payloads or configuration; no DB ingress change or NAT is proposed. Endpoint cost,
IAM and redaction checks require approval; later DDL uses a temporary IAM database login
with narrowly scoped ownership membership. Ingest remains outside the VPC and disabled.
The migration and runner have local tests; the [temporary runner](../infrastructure/PRIVATE_RDS_RUNNER.md)
passed Linux/Python 3.12 and PostgreSQL 16 verification in CI 37931518056
(451 passed, no failures/skips), including the fixed index helper and cleanup.
Next is business-rule/schema freeze. The runner is not deployed; live SQL
schema/grants/migration and RDS IAM authentication remain unverified. The Linux application release is verified
by CI run 37850256137 (385 passed, no failures/skips), not yet uploaded or deployed.

## Queries and reports

The API Gateway definition protects data methods with `AWS_IAM`. The Lambda Flask
adapter serves account, transaction, overview and insight reads. Transaction
pagination uses a cursor by default; explicit offset pagination remains for
compatibility. Transaction insights accept a transaction UUID. See the
[API contract](api_design.md).

The browser does not sign SigV4 requests. Local dashboard use works through the
loopback practice server; authenticated cloud dashboard access is unresolved.
A local signing proxy or managed browser identity is a future decision, not an
implemented feature.

The report handler runs the bundled monthly SQL and writes CSV and JSON under
`monthly/<month>/transactions`. It uses UTC month boundaries and stable output
keys. The EventBridge definition runs on the first day of the month at 02:00 UTC,
with the schedule disabled initially. Monthly reports are not full ledger archives.

## Why these services

| Choice | Project reason |
|---|---|
| S3 | Preserve source exports, rejected-row evidence and reports as separate objects |
| Lambda | Separate short event handlers without maintaining application servers |
| SQS FIFO | Buffer work and keep processing ordered per account; SQL still guards replay |
| RDS PostgreSQL | Foreign keys, financial constraints, transactions and SQL reporting |
| DynamoDB and Streams | Retrieve saved transaction scores and decouple email delivery from scoring |
| SES | Deliver review notifications through its API |
| API Gateway | Provide the defined authenticated service-client boundary |
| EventBridge | Invoke the monthly report on a schedule |
| IAM, KMS, CloudWatch | Define permissions, bucket-key controls and operational visibility |

The region is `af-south-1`. The Stage 3 database renderer owns the private RDS
instance; live SQL ownership/grants still require the migration preflight. Avoiding
NAT and interface endpoints reduces standing-cost exposure. One customer-managed KMS key is a
paid design choice for the data buckets. Existing RDS, retained objects/backups,
logs and requests can still cost money. Account credits and Free Tier eligibility
are unknown; the design is not a zero-cost promise.

## Implementation and evidence

[Processing definitions](../infrastructure/processing.py),
[foundation](../infrastructure/foundation.py) and the handler code define the
cloud path above. The local CSV loader and `fintrust.alert` retain direct SQL
teaching paths; they are not the selected cloud ingest/alert deployment path.

The hardened Linux release passed 385 tests with zero failures/skips in CI run
37850256137, including native imports. This verifies the artifact, not live end-to-end
AWS integration or the unimplemented private migration runner. Live SQL migration
and recovery execution remain unverified. Use the
[evidence register](EVIDENCE/README.md) for acceptance gates and the
[diagram register](diagrams/README.md) for export status. Existing PDF/SVG exports
still contain earlier architecture and must not be presented as current cloud
implementation evidence.

Connection pooling/reuse, approved scoring weights, production identity,
monitoring completion and archive automation remain open. The scoring rules are
explainable teaching rules, not a validated fraud model.


## Duplicate-data admission and payment risk

[Authoritative AWS architecture](presentation/diagrams/FinTrust_AWS_Architecture.pdf)

Possible duplicate charges follow the valid branch: both distinct financial
transactions remain, with `POSSIBLE_DUPLICATE_CHARGE` as a review signal.
Implemented/local-tested, live-unverified and future controls are separated in
[IDEMPOTENCY.md](IDEMPOTENCY.md). Historical diagrams/exported PDFs are not updated
execution evidence.

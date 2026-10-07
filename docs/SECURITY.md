# FinTrust security

Application deployment remains unverified. Read-only inventory and Stage 0 IAM/
budget checks have completed; [the deployment identity design](../infrastructure/iam/DEPLOYER_DESIGN.md)
records the exact evidence and limitations. `fintrust_deployer` has MFA and no
access keys, and can assume the MFA-constrained `fintrust-deployer-role` through
its reviewed identity policy. That role has no infrastructure policies attached.
The Stage 1 JSON is proposed only, not an effective grant.

The [Free Tier-first RDS plan](../infrastructure/DEPLOYMENT_BOOTSTRAP.md#b-rds-recommendation)
uses a private encrypted Single-AZ micro candidate with IAM and verified TLS.
AWS-managed RDS encryption is proposed to avoid an unnecessary customer-managed
key; the existing S3 CMK controls are unchanged pending their separate review.

## Function permissions and database access

The [IAM renderer](../infrastructure/iam/create_roles.py) defines an execution
role for each function. Runtime permissions follow the function's task:

| Function | Required access in the configured cloud path |
|---|---|
| Ingest | Read raw S3 versions, write quarantine, publish FIFO jobs, write logs |
| Scoring | Consume FIFO jobs, connect as its IAM database user, write/read saved DynamoDB projections, write account quarantine, VPC attachment and logs |
| Alert | Read projections and conditionally update delivery claims, process the stream, send SES email, write failure records and logs |
| API | IAM database connection with read grants, DynamoDB reads, VPC attachment and logs |
| Report | IAM database connection with read grants, write report objects, VPC attachment, failure destination and logs |

S3 KMS grants are scoped to the intended key, service and encryption context.
Service-managed polling and failure destinations still require execution-role
permissions. Resource ARNs, trust relationships and the resulting policies must
be checked against the actual account before use. This is not proof that a live
role is least-privileged.

Cloud database users are `fintrust_scoring_<stage>`, `fintrust_api_<stage>` and
`fintrust_report_<stage>`. They require matching `rds-db:connect` grants, database
role membership and RDS IAM authentication. [permissions.sql](../infrastructure/rds/permissions.sql)
contains service-specific SQL grants. IAM permission to connect does not grant SQL
permission to read or write a table. The ingest and alert SQL roles remain for
legacy local exercises; the selected cloud handlers do not access PostgreSQL.

Cloud connections require IAM authentication and certificate-verified TLS using
the bundled RDS CA. Local practice uses a generated password in ignored `.env`.
SSM String parameters contain only host/name/user configuration and are resolved
into the private functions' environment at deployment. Runtime SSM fallback is
not used in that path. No database password belongs in Git, a diagram or browser
JavaScript. The template `.env.example` contains placeholders.

## Network and storage controls

The [foundation](../infrastructure/foundation.py) defines two private subnets,
a Lambda security group, a database security group and a database subnet group.
Database ingress is TCP 5432 from the Lambda group. Gateway endpoints provide
S3/DynamoDB access, with scoped endpoint policies and regional prefix-list egress.
There is no NAT Gateway or separate database subnet tier. The existing RDS
instance must be inspected for private placement, TLS, engine and IAM settings;
the foundation does not create or automatically secure that instance.

Raw, quarantine and report buckets are defined with Block Public Access,
versioning, retention on stack deletion and SSE-KMS using one customer-managed
key. Bucket policies reject insecure transport and conflicting encryption/key
headers. Requests without encryption headers use the bucket default. These are
template controls; no live object encryption or public-access test is recorded.

The DynamoDB definition uses AWS-owned encryption and no TTL. SQS definitions use
SQS-managed encryption. Do not describe every service as using the bucket CMK.
S3 access logging, CloudTrail evidence and account-level audit arrangements remain
unverified; older scripts are not evidence that these controls are active.

## API and browser boundary

The [REST definition](../infrastructure/api/gateway.json) sets `AWS_IAM` on data
methods. Clients need signed requests and appropriate IAM permissions. The
health route is an operational check. API keys and CORS do not replace identity.
The Flask application itself does not implement a user login system.

The local server binds to loopback. Local CSV upload is gated by
`FINTRUST_LOCAL_DEMO=1`; it is not an authenticated production intake route.
The existing dashboard's fetch calls do not sign requests. A signed service-client
demo or a separately implemented browser identity path is required before a
cloud stakeholder demonstration.

## Data handling and review

Customer names and identity numbers are direct identifiers. Account IDs and
transaction details are linkable financial data. Examples and local practice use
synthetic records. Quarantine deliberately limits copied fields, but still holds
account and transaction information and needs restricted access.

These controls are relevant to protecting personal information; they do not
establish POPIA compliance. An owner must approve access, retention, disposal,
incident handling and backup treatment. Do not publish credentials, raw customer
records, message bodies or sensitive log events as portfolio evidence. Keep
[evidence](EVIDENCE/README.md) limited to reviewed, redacted proof.

Before deployment, verify live IAM/trust policies, gateway routes, security groups,
RDS logins/TLS, bucket encryption, SES identities and API authorization. Before
normal traffic, exercise alarm delivery and recovery. No deletion or replay is
authorized by this documentation.

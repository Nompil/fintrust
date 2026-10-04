# Infrastructure preparation

The current design and deployment gates are in [BUDGET_FIRST.md](BUDGET_FIRST.md). Preparation is local. No AWS resources have been inspected, created or changed during this phase.

## Offline entry points

- `python -m infrastructure.foundation --output build/foundation.json` renders private networking, gateway endpoints, encrypted storage and the stream-enabled risk table.
- `python infrastructure/processing.py --output build/processing.json` renders five functions, queues, event mappings, an API alias and a disabled report schedule. Supply existing resource identifiers at deployment; consumers default to disabled.
- `python infrastructure/iam/create_roles.py --help` lists inputs for service-specific policy rendering. Use the actual RDS resource ID, separate bucket names, queue ARNs, CMK ARN and verified SES identities.
- `python infrastructure/ssm/put_parameters.py` renders nonsecret settings from FINTRUST_SERVICE, FINTRUST_STAGE, FINTRUST_DB_HOST and FINTRUST_DB_NAME. Only scoring, api and report need database settings. The explicit `--apply` flag writes to AWS and must not be used during preparation.
- `infrastructure/api/gateway.json` defines the API boundary. Authenticated methods use AWS_IAM.
- `infrastructure/rds/permissions.sql` defines database grants; an administrator must review and apply these separately after approval.

Build the shared runtime with `python tools/package_lambda.py --ca-bundle build/global-bundle.pem`. Obtain the bundle from the official RDS trust store. The archive includes all five handlers and targets Python 3.12 on Linux x86_64. On that platform run `python tools/verify_lambda_linux.py build/fintrust.zip`. The manual GitHub workflow performs package verification only; it has no AWS credentials or deployment step.

## Existing resources and legacy utilities

Do not blindly create resources with names already in the account. Inventory, import or adapt templates through a reviewed change set after separate approval. The foundation deliberately excludes an RDS instance; its engine family, private subnet placement, IAM authentication and parameter group must be reconciled with the existing database.

Older standalone S3 and DynamoDB provisioning scripts are not the current deployment path. Their encryption, retention and TTL defaults must not be mixed with the foundation template. The old SQL-backed alert helper and direct CSV loader remain for local exercises; the deployed handlers are selected explicitly in processing.py.

The earlier DEPLOYMENT_READINESS.md is the audit that preceded the budget-first design. Its five-database-client assumptions are superseded by BUDGET_FIRST.md. No live deployment claims should be inferred from either document.

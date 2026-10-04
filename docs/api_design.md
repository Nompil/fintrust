# FinTrust API Design

## Overview

The API implementation is a Flask application in `fintrust/api.py`, with data access in `fintrust/query.py`. It can run locally and is adapted for Lambda/API Gateway by `aws-wsgi`. Routes are versioned under `/v1`.

## Routes

| Method and path | Configured authentication at API Gateway (unverified) | Purpose |
|---|---|---|
| `GET /v1/health` | No authorizer; operational check only | Checks PostgreSQL connectivity and returns `200`/`503`. It exposes no transaction data. |
| `GET /v1/transactions` | `AWS_IAM` | Reads recent transactions for the required account ID, with optional date range and bounded result count. |
| `GET /v1/insights` | `AWS_IAM` | Reads an immutable transaction projection or a legacy account/date item from DynamoDB. |

### `GET /v1/transactions`

Query parameters:

- `account_id` (required UUID)
- `from` (optional ISO-8601 date or timestamp)
- `to` (optional ISO-8601 date or timestamp)
- `limit` (optional integer; defaults to 50, clamped to 1-500)
- `cursor` (optional opaque continuation token). Default pagination returns `count`, `page`, `total`, `limit` and `next_cursor` (null at the end); reuse the same account and filters when continuing.
- `offset` (optional non-negative integer) selects legacy offset pagination. Do not combine it with `cursor`. Concurrent inserts can shift offset pages.

Ordering is `tx_date DESC, tx_id DESC`. Monetary values are serialized without losing decimal precision.

Missing/invalid account IDs, malformed timestamps, or an invalid limit return `400`. Database failures return a JSON `503` response.

### `GET /v1/insights`

Query parameters:

- `account_id` (required UUID)
- `transaction_id` (optional UUID): retrieves `score_date=TX#<transaction_id>`; cannot be combined with `date`.
- `date` (optional `YYYY-MM-DD`; defaults to the runtime's current date)

The current writer creates transaction projections, not daily summaries. Date lookup remains a legacy compatibility path. The DynamoDB key is `{account_id, score_date}`. The response omits the internal TTL attribute. Missing scores return `404`; DynamoDB service failures return `503`.

## Dashboard and local intake

| Method and path | Result |
|---|---|
| `GET /` | Analyst dashboard and same-origin static assets |
| `GET /v1/accounts` | Account identifiers, types and statuses without customer names |
| `GET /v1/overview` | Counts, daily activity and totals grouped by currency |
| `POST /v1/upload` | Local practice only: multipart `file`, synchronous ingestion, `200` with accepted/rejected counts |
| `OPTIONS /v1/*` | Allowed browser preflight returns `204`; rejected origin/method/header returns `403` |

Upload requires `FINTRUST_LOCAL_DEMO=1`, set by the practice helper. Otherwise the route returns `404`. CSV content is limited to 1 MiB and 5,000 rows. File validation errors return `400`; request-body overflow returns `413`. Partial row rejection is represented by result counts and reasons, not a false all-success status. Production upload authorization and asynchronous job tracking are future work.

The default dashboard uses the same origin as Flask. Explicit alternate browser origins can be listed in `CORS_ALLOWED_ORIGINS`; wildcard origins and credentialed CORS are not enabled. CORS is a browser access policy, not authentication. Response headers include a request ID, content-type protection and a same-origin content security policy. Request logs include method, path, status and elapsed time.

## Security

- API Gateway authorization is required for all account-data routes before deployment. `AWS_IAM` is the proposed service-client method; an analyst browser requires an appropriate identity flow and route integration. The Flask app itself does not implement authentication; local development is loopback-only.
- `/v1/health` contains status information only.
- The API Lambda role should have read-only database and DynamoDB permissions. It must not receive `dynamodb:PutItem` or database write privileges.
- Local database credentials come from ignored environment settings. Cloud database clients generate IAM authentication tokens and use TLS verification. Nonsecret SSM configuration is resolved during deployment, not fetched by private functions at runtime.

The API is implemented locally; API Gateway routes, authorizers, and deployed Lambda integration still need AWS configuration and evidence.

DynamoDB decimal values are returned as strings to preserve precision. Date-only transaction filters mean midnight UTC; timestamp bounds are interpreted by the query parser. The account-data API remains read-only; the local demonstration adds a bounded upload adapter. Later deployed write routes are tracked in the requirements review.

The browser does not sign requests with SigV4. An authenticated browser integration remains a deployment blocker. See [security](SECURITY.md) and [architecture](architecture.md).

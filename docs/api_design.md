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


## Proposed Release 1 workflow contract

[Release 1 business process](RELEASE1_BUSINESS_PROCESS.md) defines minimal analyst
review, manual quarantine correction, reconciliation and Admin/Analyst/Auditor
access. Existing routes above are unchanged. New list/detail and state-changing
routes are designed, not implemented; require verified actor/role, expected review
version and durable request idempotency. No frontend button may imply working
review/reprocessing until those backend contracts are implemented and tested.


## Release1 local implemented contract (2026-10-10)

All `/v1` data/mutations require `Authorization: Bearer <local opaque token>`;
only `/v1/health` and static pages are public. Token registry is server-controlled,
hash-only, ignored, and assigns subject/role/account scope. No X-Role/X-Subject or
JSON actor values confer authority. Cloud federation is deferred, not deployed.
Errors return safe messages/status/request IDs; malformed exact-field mutations400,
unauthenticated401, denied403, inaccessible transaction404, stale/reused request409.
All SQL filters are bound; duplicate/unsupported parameters fail400.

| Endpoint | Permission / contract |
|---|---|
| GET /v1/session | Authenticated own subject/role/scopes |
| GET /v1/accounts, /v1/overview | Assigned accounts only, no customer PII |
| GET /v1/workflows/{transactions,risk-events,reviews,quarantine,batches,audit} | Bounded limit1..100, offset0..100000, validated status/account; audit Admin/Auditor only |
| GET /v1/transactions/{UUID} | Assigned account financial facts, frozen score, review audit and separate SQL/cloud alert claims |
| GET /v1/quarantine/{UUID} | Scoped exact versioned safe candidate/source and correction history (max100); unassigned case Admin only |
| POST /v1/reviews/{event}/transition | Admin/Analyst: exact request_id UUID, expected_version integer>0, status, notes<=2000, resolution_code; backend actor/assignment/version enforced |
| POST /v1/quarantine/{UUID}/corrections | Admin/Analyst: exact request_id, action RESUBMIT/REJECT, notes, candidate; no mass assignment or direct ledger approval |
| GET /v1/reports | Assigned-account totals/net movement grouped by currency, not balances/FX |
| GET /v1/metrics | Admin/Auditor scoped financial/review/projection counts; global feed health Admin only |

Allowed review graph: OPEN->UNDER_REVIEW->CLEARED/CONFIRMED_RISK/ESCALATED;
ESCALATED->UNDER_REVIEW. Reopening CLEARED/CONFIRMED is Admin-only. Terminal codes
VALID_ACTIVITY/CONFIRMED_SUSPICIOUS/SPECIALIST_REVIEW must match. Client sends no
reviewer identity or reviewed timestamp. Versioned trigger history cannot be
rewritten, and request replay must match the original actor/object/content digest.

Corrections preserve original evidence, create a safe versioned replacement and
new occurrence with durable worker outbox, then rerun strict validation, trusted
identity checks and scoring. A repeated invalid correction quarantines again;
a replay against existing financial identity resolves DUPLICATE. Infrastructure
failure remains PENDING for safe worker retry. The local callable drain path and
future private-worker invocation gate are described in RELEASE1_OPERATIONS.md.

UI is `/release1`: local Login, Dashboard, Transactions/Detail, Risk Events, Review
Queue, Quarantine, Ingestion Batches, Reports, Account History, Admin/Audit. Loading
clears stale values; later responses cannot overwrite a newer page/detail request.
Role-based button hiding complements backend checks. Pagination is bounded; each
page is a current snapshot and refresh is required after a409 version conflict.
Ledger amount/date/account cannot be changed through any workflow endpoint.
The old public page is a teaching shell; it does not bypass API authentication.

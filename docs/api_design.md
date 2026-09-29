# FinTrust API Design

## Overview

The Week 13 Day 3 API implementation is a Flask application in `fintrust/api.py`, with data access in `fintrust/query.py`. It can run locally and is adapted for Lambda/API Gateway by `aws-wsgi`. Routes are versioned under `/v1`.

## Routes

| Method and path | Authentication at API Gateway | Purpose |
|---|---|---|
| `GET /v1/health` | No authorizer; operational check only | Checks PostgreSQL connectivity and returns `200`/`503`. It exposes no transaction data. |
| `GET /v1/transactions` | `AWS_IAM` | Reads recent transactions for the required account ID, with optional date range and bounded result count. |
| `GET /v1/insights` | `AWS_IAM` | Reads the account/date risk-score item from DynamoDB. |

### `GET /v1/transactions`

Query parameters:

- `account_id` (required UUID)
- `from` (optional ISO-8601 date or timestamp)
- `to` (optional ISO-8601 date or timestamp)
- `limit` (optional integer; defaults to 50 and is capped at 500)

Example response:

```json
{
  "status": "ok",
  "data": [
    {
      "tx_id": "a6e7b46f-cd0c-5cfc-9bdc-9de0ff391f7a",
      "account_id": "20000000-0000-4000-8000-000000000001",
      "amount": "250.00",
      "currency": "ZAR",
      "tx_date": "2026-09-28T09:15:00+00:00",
      "tx_type": "debit"
    }
  ],
  "meta": {"count": 1, "limit": 50}
}
```

Missing/invalid account IDs, malformed timestamps, or an invalid limit return `400`. Database failures return a JSON `503` response.

### `GET /v1/insights`

Query parameters:

- `account_id` (required UUID)
- `date` (optional `YYYY-MM-DD`; defaults to today)

The DynamoDB key is `{account_id, score_date}`. The response omits the internal TTL attribute. Missing scores return `404`; DynamoDB service failures return `503`.

## Security

- Configure API Gateway methods with the `AWS_IAM` authorizer for transaction and insight data. The Flask app itself does not implement authentication; local development must not be exposed publicly.
- Keep `/v1/health` limited to status information.
- The API Lambda role should have read-only database and DynamoDB permissions. It must not receive `dynamodb:PutItem` or database write privileges.
- Database credentials are loaded from local environment settings during development and SSM Parameter Store in Lambda.

The API is implemented locally; API Gateway routes, authorizers, and deployed Lambda integration still need AWS configuration and evidence.

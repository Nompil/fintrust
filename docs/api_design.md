# FinTrust API Design

## 1. Overview

The API exposes transaction and insight endpoints for compliance and fraud analysts. It is intentionally small, secure, and aligned with the capstone's operational model.

## 2. Endpoints

### GET /transactions
Purpose: return recent transaction data for one account or for the system overall.

Parameters:
- account_id (optional)
- limit (optional, default 50)

Example response:
```json
{
  "transactions": [
    {
      "transaction_id": "TXN-001",
      "account_id": "ACC-1001",
      "amount": "25000.00",
      "transaction_type": "debit",
      "risk_score": 65,
      "channel": "mobile"
    }
  ]
}
```

### GET /insights
Purpose: return risk summaries and trends by account.

Parameters:
- account_id (optional)

Example response:
```json
{
  "insights": [
    {
      "account_id": "ACC-1001",
      "total_transactions": 25,
      "avg_risk": 42.3
    }
  ]
}
```

### POST /upload
Purpose: accept an upload event for processing.

Request body:
```json
{
  "bucket": "fintrust-raw",
  "key": "transactions/2026-09.csv"
}
```

Response:
```json
{
  "status": "accepted",
  "message": "upload queued for processing"
}
```

### POST /flag
Purpose: manually flag a high-risk account or transaction for investigation.

### POST /resolve
Purpose: mark a risk as reviewed or resolved.

## 3. Authentication and Security

- API key-based authentication is used.
- Access should be restricted to authorised fraud and compliance users.
- Sensitive fields should not be exposed broadly without role-based constraints.

## 4. Response Patterns

- Use JSON responses for all API operations.
- Return explicit status and error messages.
- Ensure all requests are logged for auditability.

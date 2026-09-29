# FinTrust Capstone Submission Checklist

## 1. Build and portfolio deliverables

The following items should be present in the repository before Week 14 submission:

- Cloud architecture diagram
- ERD in third normal form
- API design document
- IAM role matrix
- Data governance and compliance statement
- SQL artefacts: schema, seed, risk report, monthly summary, views, procedure
- Python package with required modules
- Tests using pytest and moto-style patterns
- CI GitHub Actions workflow
- README with deployment and business overview
- Screenshots and evidence from AWS / Postman / CI

## 2. Minimum technical coverage

### Cloud Architecture
- S3 ingestion bucket
- Lambda ingest function
- SQS FIFO queue
- Score Lambda
- RDS PostgreSQL ledger
- DynamoDB event store
- API Gateway
- SES alerting
- EventBridge scheduling
- S3 reporting bucket

### SQL
- schema.sql with constraints and indexes
- seed.sql with realistic multi-account transactions
- risk_report.sql with CTE logic
- monthly_summary.sql with running balance window function
- views.sql with compliance abstraction
- stored procedure or function for flagging risk

### Python
- config.py
- db.py
- dynamo.py
- models.py
- validators.py
- ingest.py
- score.py
- alert.py
- query.py
- report.py

### Testing and CI
- pytest suite across validation and risk logic
- GitHub Actions pipeline triggered on push
- Integration tests scoped appropriately

## 3. Presentation readiness

Before the live demo, ensure you can explain:

1. Business problem and stakeholder value
2. Why each AWS service was selected
3. How the queue protects reliability
4. The difference between ledger data and event data
5. How the system enforces security and governance
6. How the monthly report adds executive value

## 4. Suggested evidence pack

Collect these screenshots before submission:
- Lambda list
- RDS instance summary
- API Gateway stage
- CloudWatch dashboard or log view
- GitHub Actions green run
- Postman or curl result for GET /transactions and POST /upload

## 5. Final presentation note

The system is not only a technical build; it is a business control platform. The key to a strong presentation is to explain the system in terms of risk reduction, compliance, and operational trust, not only code and infrastructure.

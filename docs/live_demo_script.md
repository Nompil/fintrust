# FinTrust Live Demo Script and Panel Q&A Guide

## 1. 3-Minute Live Demo Script

### Opening line
"Good afternoon. Today I’m presenting the FinTrust transaction insights and risk monitoring system. This solution is designed to ingest financial transaction data, validate it, risk-score it, and provide operational insights to the compliance and executive teams."

### Step 1: Business problem
"FinTrust processes high volumes of financial transactions and needs to spot risk quickly without relying on manual review alone. The challenge is to detect suspicious activity early while keeping the system secure, auditable, and cost-conscious."

### Step 2: Architecture summary
"The architecture is serverless and event-driven. We upload raw transaction files to Amazon S3. The ingest Lambda validates the file and prepares the data. The data is pushed into an SQS FIFO queue so processing remains ordered by account and resilient to failure. The score Lambda reads the queue, applies risk logic, and stores the result in both the PostgreSQL ledger and DynamoDB event store."

### Step 3: Security and compliance
"The design is intentionally aligned to least privilege. Lambda roles are scoped for specific actions, the database is not public, and the system stores sensitive financial data with governance in mind. That matters because this is not generic app data; it is regulated financial information in a banking context."

### Step 4: Monitoring and dashboard narrative
"From an operational perspective, we also monitor the flow with CloudWatch. This gives us visibility into ingestion volume, processing errors, high-risk transaction counts, queue activity, and API usage. The dashboard is important because it tells us whether the system is healthy, whether bad records are being rejected, and whether a risk event is trending upward."

### Step 5: Business value
"The business value is straightforward: faster risk detection, better compliance visibility, a lower manual review burden, and a clearer picture for management. Instead of reacting after an issue has already escalated, the system provides early signal and evidence-based monitoring."

### Closing line
"In short, this is a complete operational control layer for FinTrust: ingest, validate, score, alert, monitor, report, and govern."

---

## 2. AWS Dashboard Explanation

When presenting the CloudWatch dashboard, explain it in this order:

### A. Ingestion metrics
- Show the number of transaction files processed
- Explain that this confirms the upload-to-ingest path is working

### B. Error rate and failures
- Show the Lambda error count or failed invocations
- Explain that these metrics tell us whether validation, queueing, or scoring is failing

### C. High-risk transaction counts
- Show the custom metric for high-risk events
- Explain that this is the operational trigger for investigation and alerting

### D. API traffic
- Show request volume and error rates
- Explain that the compliance team can query transactions and insights securely through API Gateway

### E. Queue activity
- Show backlog or retry behavior
- Explain that this protects the system from sudden spikes and operational failure

### Presenter language
"The dashboard does not just show that the system runs. It shows that it is operationally healthy and that risk events are being surfaced before they become more serious issues."

---

## 3. What to Say About the Data Flow

### The standard explanation
"Transaction data enters the system through S3, is validated before storage, moved to the queue for ordered processing, scored for risk, persisted in the ledger and event store, and then surfaced to the compliance team and executives."

### Why this matters
- It preserves data quality
- It improves resilience
- It keeps the design cost-aware
- It reflects how real banking systems separate operational and analytical concerns

---

## 4. Likely Panel Questions and Strong Answers

### Q1: Why use both RDS and DynamoDB?
"RDS is used for the core transaction ledger because the data is relational and needs normalised reporting and audit-friendly structure. DynamoDB is used for event and operational metadata because it supports fast, scalable lookup patterns and complements the ledger with a lighter-weight event store. In other words, one supports the financial record and the other supports the operational event layer."

### Q2: Why is SQS used in the middle of the architecture?
"SQS decouples ingestion from processing. It prevents the ingest Lambda from being tightly coupled to the scoring Lambda and gives us retry, ordering by account, and a safety buffer during spikes or temporary failures. That is a more resilient design than point-to-point processing."

### Q3: What happens if a transaction fails validation?
"The record is rejected or quarantined before it enters the core transaction ledger. That protects data quality and prevents bad or malformed records from corrupting the downstream reporting and risk analysis."

### Q4: How do you keep the system within Free Tier and cost-conscious?
"The design avoids expensive services such as NAT Gateway and keeps the architecture serverless. The services selected are specifically chosen to fit the Free Tier constraints while still demonstrating real engineering patterns. Cost is part of the design, not an afterthought. We deliberately use services that scale only when needed, avoid unnecessary network components, and keep the system lean enough for a fintech environment where cost control matters as much as functionality. If we were not limited by Free Tier constraints, I would likely use a more fully managed and always-on operational setup, such as a larger VPC design with stronger redundancy, additional monitoring, and more persistent compute capacity. However, the current design is intentionally efficient because it proves we can achieve the required outcome without unnecessary spend."

### Q5: Why is CloudWatch important in a banking context?
"Because monitoring is part of operational control. We need visibility into error rate, queue health, and high-risk activity. In a real financial environment, you cannot rely on a working deployment alone; you need evidence that the system is healthy and alerting when something deviates."

### Q6: Why does compliance matter here?
"The system handles transaction-level financial data that can contain personal and sensitive information. A strong design has to include governance, access boundaries, retention thinking, and validation. If the bank cannot trust the data and the process, the system is not complete."

### Q7: How do you justify the architecture to the business?
"The architecture reduces operational risk, improves fraud detection, reduces manual workload, and strengthens compliance posture. It also makes the data easier to report on for executive decisions and regulatory review."

---

## 5. Short Closing Statement for the End

"This project demonstrates a practical banking control system: it ingests transaction data, validates it, scores it for risk, exposes insights to decision-makers, and monitors the health of the pipeline in real time. The result is a secure, scalable, and governance-aware platform that matches the needs of FinTrust Bank SA."

---

## 6. Quick Rehearsal Tips

- Speak in business terms first, then technical detail.
- Do not read the script word-for-word; use it as a guide.
- Point to the flow: S3 → Lambda → SQS → Score → RDS + DynamoDB → API → CloudWatch.
- Always tie each technical step back to business value.
- If asked a difficult question, answer with structure: problem, mechanism, benefit.

---

## 7. One-Line Summary

"This is a serverless, fraud-monitoring and compliance platform for FinTrust, built to detect risk early, monitor reliability, and support operational and executive decision-making."

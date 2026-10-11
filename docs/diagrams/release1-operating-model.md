# Current Release 1 presentation diagrams

These views distinguish implemented local behavior from the AWS target. Existing historical SVG/PDF exports are not proof of live integration. The local UI uses real isolated PostgreSQL with mocked S3/DynamoDB; it does not run the cloud FIFO/Streams/SES chain.

## Architecture: AWS target, integration incomplete

```mermaid
flowchart LR
  S3["S3 source file"] --> I["Ingest Lambda"] --> Q["SQS FIFO"] --> S["Scoring Lambda"]
  S --> PG["Private PostgreSQL ledger and workflows"]
  S --> D["DynamoDB projections"] --> ST["DynamoDB Streams"] --> A["Alert Lambda / SES"]
  PG --> API["API / Reports"] --> UI["Internal operations UI"]
```

Infrastructure stages 1–4 were verified previously. This local audit does not claim the complete application chain is live; live public schema bootstrap remains pending after read-only preflight.

## Actual local data decisions

```mermaid
flowchart TD
  U["Analyst admits bounded CSV"] --> F{"File contract valid?"}
  F -->|No| X["Reject file; safe receipt; no financial work"]
  F -->|Yes| R{"Row contract and identity valid?"}
  R -->|No| QC["Quarantine safe original and reasons"]
  R -->|Yes| DU{"Duplicate identity?"}
  DU -->|Same identity and facts| DP["Record duplicate occurrence; no extra ledger entry"]
  DU -->|Distinct valid transaction| SC["Process / evaluate frozen rules"]
  SC --> L["Immutable accepted ledger + assessment"]
  L --> HR{"Review / alert thresholds met?"}
  HR -->|Yes| RV["Review event / alert evidence"]
  QC --> C["Analyst correction"] --> R
```

High risk is an accepted valid transaction with an assessment, not invalid data. Review and alert thresholds follow current rules; do not claim that every Low/Medium event is an alert.

## Failure and recovery

```mermaid
flowchart LR
  PF["Technical processing failure"] --> RT["Retry; do not acknowledge as accepted"] --> DLQ["Approved DLQ after exhausted cloud retries"]
  DLQ --> INV["Maintainer investigates"] --> CR["Bounded controlled redrive with receipt"] --> RT
  SQL["Committed SQL; projection failure"] --> OUT["Pending outbox"] --> PR["Controlled projection retry"] --> RC["Reconcile completion"]
```

Cloud DLQ/provider delivery is a separately approved integration. Local tests inject failures and verify pending work, retries and receipts; a queued recovery request is not a success claim.

## Users and separation of duties

```mermaid
flowchart TD
  BO["Controlled first Admin and token provisioning"] --> AD["Admin: local user records / roles / status / oversight"]
  AD --> AN["Analysts: scoped review and correction"]
  AD --> AU["Auditors: evidence reads only"]
  AD --> MA["Maintainers: technical recovery only"]
  AN --> EV["Named actor + original evidence + audit trail"]
  MA --> EV
  AD --> EV
  AU --> EV
```

Arrows to roles represent access governance, not permission inheritance. Admin cannot make routine risk decisions; Maintainer cannot bypass quarantine; Auditor cannot mutate. Multiple people may hold each role. Local records are not enterprise SSO.

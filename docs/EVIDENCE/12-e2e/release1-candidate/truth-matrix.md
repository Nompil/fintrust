# Release 1 final capability truth matrix

Local/CI scope, exact source d648dd0a77b6906daa94ec7ade7b2ff3e3158ed0. Synthetic services are explicitly mocked; SQL is real PostgreSQL16. No local result is promoted to a live AWS claim.

| Capability | Status | Exact scope / limitation |
|---|---|---|
| ingestion | IMPLEMENTED + VERIFIED | Real SQL worker plus versioned mocked S3/FIFO locally; cloud wiring remains gated. |
| file admission | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| validation | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| duplicate protection | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| cross-file dedupe | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| duplicate identity conflict | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| possible double charge | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| risk scoring | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| quarantine | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| correction | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| reconciliation | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| review | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| alerts | IMPLEMENTED + VERIFIED | Definite rejection retry and logical idempotency verified; ambiguous delivery stops for reconciliation. |
| DLQ/redrive | IMPLEMENTED + VERIFIED | Bounded exact FIFO/DLQ pair verified with Moto; cloud controller separately gated. |
| RDS/DynamoDB recovery | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| API | IMPLEMENTED + VERIFIED | Authenticated scoped local bearer registry; cloud identity provisioning remains DESIGNED. |
| frontend | IMPLEMENTED + VERIFIED | Required pages and review verified in Chrome; cloud frontend/auth deployment not performed. |
| Admin | IMPLEMENTED + VERIFIED | Assigned-account upload, review and operations; HTTP user/role management remains DESIGNED. |
| Analyst | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| Auditor | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| Maintainer | IMPLEMENTED + VERIFIED | Backend rejects compliance/financial writes; audited technical requests verified. |
| reporting | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| audit | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| observability | IMPLEMENTED + VERIFIED | Bounded queue/batch/alert/receipt/release/migration views; operational cloud integration not verified. |
| migrations | IMPLEMENTED + VERIFIED | 001/002 ordering, source/catalog drift, PG16 grants verified locally/CI; live002 path BLOCKED. |
| CI | IMPLEMENTED + VERIFIED | Synthetic local/CI proof in scenario-evidence.json and pytest.xml; no live AWS verification claimed. |
| release artifact | IMPLEMENTED + VERIFIED | All five handlers and production modules/native imports verified in Linux3.12; exact source/frontend/hash bound. |
| AWS integration | IMPLEMENTED + NOT VERIFIED | Existing infrastructure is previously verified; current Release1 runtime/migrations/auth/triggers are not live. |
| E2E | BLOCKED | Constructed scenarios passed; actual external CSV A/B not supplied. |
| Cloud API identity provisioning | DESIGNED | Local hash registry is not a deployed federation or automatically provisioned AWS identity. |
| Live002 runner | BLOCKED | Existing private runner implements001 only; do not pass002 to it. |
| Cloud operations controller | DESIGNED | Private API has no public SQS route; no NAT/endpoint was added. |
| HTTP user/role management | DESIGNED | Administration page truthfully reports status; no fake management controls. |
| Refunds/reversals/chargebacks, advanced profiling, impossible travel, ML, enterprise case management, production DR, massive-file architecture, enterprise federation | DEFERRED | Outside frozen Release1 scope. |

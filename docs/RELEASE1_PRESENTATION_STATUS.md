# Release1 presentation truth matrix

This table describes the local prototype, not AWS deployment. PostgreSQL16 and exact-source Linux verification are recorded separately in final CI evidence. Actual external CSV A/B import is pending; constructed scenarios are tested.

| Capability | Status | Verification boundary |
|---|---|---|
| Ingestion | IMPLEMENTED + VERIFIED | Strict CSV -> queued worker; synthetic inputs |
| Validation | IMPLEMENTED + VERIFIED | Multi-error, amount/time/account/country/currency cases |
| Idempotency | IMPLEMENTED + VERIFIED | Frozen replay and concurrent delivery tests |
| Cross-file duplicate protection | IMPLEMENTED + VERIFIED | Source identity and content fingerprint tests |
| Risk scoring | IMPLEMENTED + VERIFIED | >5 in closed 5min, amount, country, similar charge, combined rules |
| Quarantine | IMPLEMENTED + VERIFIED | SQL case + versioned safe evidence; mocked S3 |
| Correction/reprocessing | IMPLEMENTED + VERIFIED | Real SQL outbox, revalidation, deduplication; mocked S3 |
| Analyst review | IMPLEMENTED + VERIFIED | Optimistic state transitions, immutable history, browser |
| Alerting | IMPLEMENTED + VERIFIED | Mocked SES idempotency/ambiguity; live sending not activated |
| Reconciliation | IMPLEMENTED + VERIFIED | Disjoint row outcomes and batch status |
| API | IMPLEMENTED + VERIFIED | Local real SQL endpoints, bounded pagination |
| Frontend | IMPLEMENTED + VERIFIED | Loopback browser pages, review action, auditor read-only |
| RBAC | IMPLEMENTED + VERIFIED | Server-side token registry and account scope; PG16 service-role CI pending |
| Reporting | IMPLEMENTED + VERIFIED | Account/currency net movement from zero; no balance/FX claim |
| Observability | IMPLEMENTED + VERIFIED | Local request IDs, safe logs and operational metrics |
| Migrations | IMPLEMENTED + NOT VERIFIED | PG18 ordered001/002 verified; exact PG16 gate pending |
| CI | IMPLEMENTED + NOT VERIFIED | Approved focused push/run pending |
| AWS integration | IMPLEMENTED + NOT VERIFIED | Earlier foundation verified; new Release1 workflows not deployed |
| Cloud identity federation | DESIGNED | Separate deployment approval required |
| Hourly velocity/refund accounting/FX | DEFERRED | Outside Release1 freeze |

Launch and presentation order: [RELEASE1_MONDAY_DEMO.md](RELEASE1_MONDAY_DEMO.md). Gap scope: [RELEASE1_GAP_REGISTER.md](RELEASE1_GAP_REGISTER.md). No live migrations, AWS access, trigger wiring, concurrency or deployed code changes were performed.

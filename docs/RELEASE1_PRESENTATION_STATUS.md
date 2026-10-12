> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Release1 presentation truth matrix

This table describes the local prototype, not AWS deployment. PostgreSQL 16.15 and exact-source Linux CPython 3.12.15 x86_64 verification passed in CI run 38050661063 (543 passed, zero skips/failures). Actual external CSV A/B import is pending; constructed scenarios are tested.

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
| RBAC | IMPLEMENTED + VERIFIED | Server-side token registry and account scope; PG16 service-role privileges verified |
| Reporting | IMPLEMENTED + VERIFIED | Account/currency net movement from zero; no balance/FX claim |
| Observability | IMPLEMENTED + VERIFIED | Local request IDs, safe logs and operational metrics |
| Migrations | IMPLEMENTED + VERIFIED | Fresh/legacy001/002, drift/rerun/rollback and service-role checks on PG16.15 |
| CI | IMPLEMENTED + VERIFIED | Run38050661063:543 passed, zero skipped/failed; native imports and checksum passed |
| AWS integration | IMPLEMENTED + NOT VERIFIED | Earlier foundation verified; new Release1 workflows not deployed |
| Cloud identity federation | DESIGNED | Separate deployment approval required |
| Hourly velocity/refund accounting/FX | DEFERRED | Outside Release1 freeze |

Launch and presentation order: [RELEASE1_MONDAY_DEMO.md](RELEASE1_MONDAY_DEMO.md). Gap scope: [RELEASE1_GAP_REGISTER.md](RELEASE1_GAP_REGISTER.md). No live migrations, AWS access, trigger wiring, concurrency or deployed code changes were performed.

Verified source/pushed commit: `4d91c3d30cece5192db1afc22f71fb42e3e00413`. Final documentation/evidence commit remains local. [CI run](https://github.com/Nompil/fintrust/actions/runs/38050661063). Downloaded new ZIP SHA256: `e134f98d1d01447ecbaa79c433deaad3c40ea78e9b74868d16fdd063125a1c4d`. It is retained separately under `build/release1-ci/38050661063/release/`; historical ZIP remains unchanged. The downloaded new package has not been uploaded to AWS.

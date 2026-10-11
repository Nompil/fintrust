# Release 1 local system assurance

This continues the frozen presentation release and the subsequent UX and base-schema review; it does not restart the project audit. No AWS calls, live SQL, deployment, package upload or Git push were performed. All 157 pre-existing unrelated worktree files and historical artifacts are preserved.

## Component map and scope

`docs/EVIDENCE/12-e2e/system-assurance/component-map.json` inventories 27 HTTP method/route registrations: 24 API registrations (including public health) and three public frontend/assets registrations. HEAD/OPTIONS are framework-generated and excluded from that count. The workflows route is a dispatcher; its supported kinds also have existing functional tests.

The flow is authenticated local UI → CSV admission → file/row identity → validation/quarantine → SQL ledger/scoring → projection outbox → mocked DynamoDB/alerts → review/correction/audit → SQL reports and eight charts. Real isolated PostgreSQL is used; S3/SQS/DynamoDB/SES are mocked with unmocked AWS transport prohibited by the test harness.

Four mutation handlers now check authorization before parsing JSON: review transition, quarantine correction, technical retry and local user governance. Unauthorized malformed requests return 403 instead of 400. Existing authorization remains in the service layer. This fixes error ordering, not a demonstrated unauthorized-write exploit. No business thresholds, data model or features changed.

## Assurance matrix

| Capability | Status | Evidence / limitation |
|---|---|---|
| Authentication and every protected API registration | PASS | All 23 protected registrations reject missing identity; structured JSON, request ID, no-store and nosniff checked. |
| Backend RBAC and object scope | PASS | All five mutation registrations reject unauthorized roles before malformed JSON; Maintainer financial/governance scope denied. Existing account-scope and user disable/reactivate tests retained. |
| Upload and CSV-only admission | PASS | Existing rejection/size/row/header/encoding tests, actual browser upload and derived A/B datasets. |
| Whole-file replay by different users | PASS | Named analyst01/analyst02 each audited; one ledger entry. |
| Row duplicate, conflict and possible duplicate charge | PASS | Existing real SQL identity and concurrency tests; fingerprint is not a uniqueness constraint. |
| Validation, quarantine and correction | PASS | Missing/invalid values quarantined, valid rows continue; corrections revalidate and rededuplicate while preserving original evidence. |
| Reconciliation and partial-write recovery | PASS | Real SQL counters, projection outbox retry and technical failure tests. No false completion. |
| Risk and threshold boundaries | PASS | Amount >50,000; velocity >5 accepted within closed five-minute window; cross-border is a signal, not a fraud verdict. Hour-long velocity proposal remains deferred. |
| Review lifecycle | PASS | Analyst transitions, stale version, replay, terminal state and immutable ledger tests. |
| Logical alerts and idempotency | PASS | Mocked SES/projection tests cover retry and ambiguous outcome; no claim of live email delivery. |
| Session notifications | PARTIAL | Browser verifies acknowledgement, navigation persistence and role-session isolation; not a cross-device durable inbox. |
| Audit accountability | PARTIAL | Upload/replay, governance, review, correction and technical retry audit tested. Login, client-side download and notification acknowledgement are not claimed as audited actions. |
| Reports and eight insights | PASS | Scoped SQL totals and date-filter tests; all eight browser tables and CSV/JSON values compared with their actual API data. Reports export current authorized account/page, not a date-period or all-pages report. No FX conversion or current-balance claim. |
| Operations and DLQ | PASS | Mock queue redrive, replay and failures tested; technical DLQ is distinct from business quarantine. |
| Database constraints and migrations locally | PASS | Fresh PostgreSQL 16.15 base -> 001 -> 002 -> approved synthetic seed, reruns and drift/rollback checks verified. |
| PostgreSQL 16 service-role/bootstrap integrity | PASS | Disposable administrator catalogue: 17 tables, 2 views, 85 validated constraints, 36 indexes, zero unexplained violations; service/migration role rehearsals and eight actual runtime DDL denials. |
| Smoke and frontend roles | PASS | Compact real-SQL smoke plus actual browser navigation, review/correction and downloads; four roles exercised across suites. |
| Clean start with fresh dependencies / PG16 | PASS | Git archive of 8b86, newly created Windows Python 3.14.7 venv, fresh dependency installation, empty PostgreSQL 16.15 cluster, smoke/browser/full gates. Host prerequisites are explicit below. |
| Performance sanity | PASS / DEFERRED | Eight representative SQL plans at 200/1,000/10,000 synthetic transactions. Query sanity verified; production load/capacity, throughput and memory testing deferred. |
| Secret scan | PARTIAL | Pattern scan of tracked and relevant untracked text; markers, localhost disposable credentials and placeholders classified. No matched values emitted. Pattern scanning is not proof against every secret or personal-data format. |
| Cleanup and preservation | PASS | 102 verified ordinary bytecode files removed individually; 36 reparse points deliberately untouched. No recursive traversal/deletion; historical packages/evidence and unrelated files preserved. |
| Live AWS end-to-end chain | BLOCKED | Pending approved base bootstrap/migrations, a current Linux artifact, application deployment, event wiring and live E2E. |
| Enterprise identity, durable notification inbox, hour-velocity rule | DEFERRED | Outside frozen Release 1 scope. |

## API verification map

The component JSON is the exhaustive method/route inventory with handlers and source line numbers. `tests/test_system_assurance.py` derives its protected-route cases from Flask's actual URL map, so a new protected registration cannot silently escape that gate. Authentication failures return 401, role failures 403, malformed authorized requests 400/415, missing objects 404, state/idempotency conflicts 409, and service failures sanitized 500/503 as appropriate. Existing tests cover route-specific success, pagination/filter validation, replay, malformed body, stale version and scoped-object behavior. The new gate does not claim every possible combination on every route.

The public routes are `/`, `/release1`, `/assets/<path:name>` and `/v1/health`. User-governance changes remain local-only and do not issue credentials. Reports/insights/transactions are assigned-account scoped; feed-health oversight is deliberately Admin-only. Maintainer access is technical operations, never financial workflow authority.

## Cleanup and release discipline

`cleanup-proposal.json` classifies bytecode-only candidates. `cleanup-result.json` records the safe refusal. Build history is not disposable merely because it is ignored: failed AWS attempts, pinned packages and release manifests stay. `preserved-files.json` stores hashes of the 157 unrelated files; final verification must compare every hash. No broad delete, reset, move, archive or staging of unrelated files is permitted.

No broken migration reference should be inferred from a convenience filename: the authoritative ordered chain is the base prefix in `sql/schema.sql`, then `001_transaction_identity.sql`, then `002_operational_workflows.sql`. The source review and base manifest remain unmodified. Historical presentation ZIPs remain historical; the API fix requires a newly verified Linux package before any future deployment.

## Historical commands and original local gates

With already configured dedicated loopback test database credentials (never print them):

```powershell
python tools/run_release1_tests.py tests/test_system_assurance.py
python tools/run_release1_tests.py
```

Browser verification uses the existing Node, Playwright and Chrome paths through `FINTRUST_NODE` and `FINTRUST_PLAYWRIGHT_MODULE`, then `python tools/run_release1_browser.py`. All evidence stays under the existing `docs/EVIDENCE/12-e2e/` hierarchy.

For a genuine clean start, use a fresh source checkout, a fresh Python 3.12 virtual environment with `pip install -r requirements.txt`, a disposable PostgreSQL 16 administrator service, and the existing PostgreSQL 16 role/bootstrap checks and full suite. Create only dedicated loopback test databases; local synthetic seed must never be applied to live RDS. `python tools/local.py setup` prompts for local database administration without persisting administrator credentials. Launch the isolated mock-cloud application with `python tools/serve_release1.py --role Admin --username admin01 --seed-scenarios`; token provisioning is controlled local setup, not enterprise login. This sequence is documented but not claimed executed in a new environment.

That was the next work at the historical checkpoint; it is now completed below. AWS execution remains separately gated. Live writes still need their separate approval. No frozen commit was amended, no artifacts rebuilt and no push performed.

## Historical results at 8b86 (superseded local blockers)

- Full suite: **704 passed, 1 expected skip, 0 failures/errors**, 385.69 seconds. The service-role skip requires a disposable database administrator; it remains an unresolved gate.
- Focused authorization/UX/readiness suite: **74 passed**. Final whole-route/security/smoke/two-user replay suite: **55 passed**. These counts overlap and must not be added together as unique scenarios.
- Browser E2E: **1 passed**, 52.31 seconds; real downloads and all eight chart tables compared to API responses.
- Bounded real-SQL processing check: **1 passed**; 1 row 0.5565 seconds, 100 rows 31.8885 seconds, local PostgreSQL 18.6, mocked cloud. Parser-only 1/100/1,000/5,000 measurements are separately recorded.
- Initial new regression run: 45 passed / 9 failed; all nine malformed-request authorization-order cases are now fixed and passing. The initial result is retained for traceability.
- API: **24 method/route registrations** including health, **23 protected registrations** tested for missing authentication; 27 total HTTP registrations inventoried. All final API security cases pass. This is registration coverage, not a claim of every input/state combination.
- E2E scenario evidence: derived A → B → exact A replay; named two-user same-file replay; concurrent identical delivery; source identity conflict; validation/quarantine; correction revalidation; review stale/replay; risk boundaries; partial SQL/projection/alert failure recovery; role switching; scoped reports/insights and error/empty UI states.
- Cleanup: **0 files deleted, 0 archived**. All 157 unrelated hashes match. Recursive cache cleanup stopped safely at a Windows reparse point. Historical packages, manifests, evidence and runner scripts remain intact.
- Existing source/requirements/migration references checked; no new broken references in that bounded check. Historical evidence links were not rewritten.

Evidence: `docs/EVIDENCE/12-e2e/system-assurance/verification.json`, XML results, component map, preservation hashes, cleanup proposal/refusal, sanitized scan and parser/SQL measurements; browser screenshots and actual exports are in its `browser/` subdirectory.

The preceding results and cleanup refusal are historical evidence, not the current local status. See the closure below.


## Local assurance closure (2026-10-11)

### Verified locally

The new proof uses PostgreSQL **16.15**, Windows x86_64, a disposable loopback-only SCRAM cluster on port 55416 and random in-memory administrator credentials. The server is stopped after verification. The installed PostgreSQL 18 service and live RDS are untouched. Catalogue evidence includes object owners, exact relation ACLs, role flags, functions, migration history, PK/FK/unique/CHECK/NOT NULL checks and the partial unique identity index. All 85 constraints are validated; all enforced relationship, identity and state checks return **zero unexplained integrity violations**. Actor strings without enforced foreign keys are explicitly excluded from a directory-integrity claim.

The authoritative base prefix in `sql/schema.sql` is checked against the existing manifest, followed by migrations 001 and 002 and the approved 200-row synthetic seed. Reruns are no-ops. Existing PostgreSQL 16 service-role and migration rehearsals prove required DDL/data operations, owner/bootstrap separation, temporary privilege removal, row preservation, partial-state refusal and rollback. Runtime scoring/workflow roles are denied CREATE TABLE, DROP TABLE, ALTER TABLE and arbitrary function creation (eight actual denials). This verifies PostgreSQL grants, not live RDS IAM authentication.

### Reproducibility verified

Application source came from a clean Git archive of `8b86b699f7a9c2a492eb159b58fb35bf22c3fdcf`; no existing venv, bytecode, database or generated runtime state was copied. The supplemental verification-only changes are explicit local-disposable opt-in on the two existing PG16 rehearsal gates, the catalogue/benchmark checker, the clean-run orchestrator and a launcher test targeting its configured disposable database instead of host defaults. No production source, schema or business rule changed.

A fresh **Windows CPython 3.14.7** venv installed project-pinned dependencies with no global/user site packages or pip-cache reuse; `pip check` passes. All 31 production modules and the API handler import. Production pins remain separate in `requirements-runtime.txt`; `requirements-verification-lock.txt` records every resolved installed package version for this Windows verification. It was captured from the successful fresh install and checked against it, rather than claiming a second independent install from that newly generated lock. Linux CPython 3.12 Lambda artifact verification remains a separate deployment gate.

Fresh Playwright/playwright-core 1.62.1 packages were downloaded from the npm registry and their SHA512 metadata integrity checked. Existing Node and installed Chrome are declared host prerequisites. Windows AMD64, Python, Node, Chrome and a compatible Visual C++ runtime are required; this is not a claim that a bare machine needs no setup. Parent `.env` discovery and user/global Python packages are disabled. Cloud services are mocked and unmocked AWS transport is blocked by the test harness.

Portable PostgreSQL binaries came from the official PostgreSQL-linked EDB Windows 16.15 archive (`https://sbp.enterprisedb.com/getfile.jsp?fileid=1260623`), SHA256 `43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281`. Only `pgsql/bin`, `pgsql/lib` and `pgsql/share` were extracted under ignored build storage; no system installation/service was created.

To reproduce after providing those host prerequisites:

1. Create `build/assurance-clean-start/source` from `git archive 8b86b699f7a9c2a492eb159b58fb35bf22c3fdcf`; copy this closure's three verification scripts (`check_migration_roles_pg16.py`, `check_workflows_pg16.py`, `check_local_pg16_assurance.py`) and corrected `tests/test_presentation_readiness.py` into that source tree.
2. Create `build/assurance-clean-env` with Python 3.14, then install `requirements-verification-lock.txt` with its Python and `--no-cache-dir`. The original observed install used `requirements.txt`; the exact resolved versions are now pinned in the verification lock.
3. Extract the verified PostgreSQL archive so binaries are in `build/assurance-pg16/pgsql/bin`. Install fresh Playwright 1.62.1 into `build/assurance-clean-start/browser-tools` (for example, `npm install --prefix build/assurance-clean-start/browser-tools --no-save --ignore-scripts playwright@1.62.1` on a host with npm).
4. Set `FINTRUST_NODE` to the installed Node executable and run `build/assurance-clean-env/Scripts/python.exe tools/run_clean_release1_assurance.py` from the repository. Port 55416 must be free. The helper refuses reused cluster state, bootstraps a new database, runs the gates and stops only its owned server in `finally`.

Two full-suite failures exposed harness isolation assumptions: committed benchmark rows exceeded a pagination test's bounded fixture, and the launcher test used host-specific role/database constants. Benchmark additions now roll back before regression tests; the launcher test uses its explicit disposable fixture target. No application behavior was weakened. Initial diagnostic results are retained alongside the corrected run.

### Performance boundary and safe cleanup

Eight SQL operations were measured with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` at 200, 1,000 and 10,000 synthetic transactions (24 plans). Direct synthetic inserts measure SQL query sanity, not ingestion throughput. The trusted duplicate lookup uses an index scan. Small-table sequential scans and full-ledger aggregates are expected; no new index was justified by these single-run observations. Listing/history use bounded ordered queries; report/metrics/Insights source inspection found fixed joins/aggregate queries and bounded page processing, not a SQL query per returned transaction. This is a bounded source review, not comprehensive query-count instrumentation.

Performance sanity verified at tested synthetic scale; **production load/capacity testing remains deferred**. No SLA, p95 latency, concurrent load, memory limit or million-row guarantee is claimed. The earlier parser and worker timings remain separate historical evidence.

Cleanup inventoried ordinary files/directories and reparse points without following links. Exactly **102 ordinary bytecode files** were deleted with literal file paths after checking their parents and repository containment. **36 reparse points remain untouched**; ignored extraction/database folders and historical ZIPs/manifests/forensic evidence remain. An empty cache directory is not a release requirement. Subsequent tests may regenerate disposable bytecode.

### Live AWS pending

No AWS call, live RDS connection, policy change, snapshot, migration, application deployment, artifact rebuild/upload or Git push occurred in this closure. Live base-schema bootstrap, approved migrations, a current verified Linux release artifact, application deployment/event wiring and live end-to-end verification still need their controlled approval sequence. Enterprise identity, durable cross-device notifications and hour-based velocity exploration remain deferred as already frozen.

Evidence is in `docs/EVIDENCE/05-rds/local-pg16-assurance/` and `docs/EVIDENCE/12-e2e/clean-start/`; existing historical evidence is preserved.


### Final closure results

- focused-smoke: **100 passed, 0 skipped, 0 failures, 0 errors**, 73.6 seconds. Counts overlap; do not add them as unique cases.
- fresh-browser: **1 passed, 0 skipped, 0 failures, 0 errors**, 45.34 seconds. Counts overlap; do not add them as unique cases.
- fresh-full: **705 passed, 0 skipped, 0 failures, 0 errors**, 229.74 seconds. Counts overlap; do not add them as unique cases.
- Fresh dependencies: 34 resolved package versions match the verification lock; `pip check` and 31 production-module/handler imports pass.
- All 157 unrelated file hashes still match; owned disposable PostgreSQL is stopped and port 55416 has no server response. No local blockers remain.

Single-run 10,000-row SQL execution times (milliseconds):

| Operation | ms |
|---|---:|
| transactions | 0.025 |
| history | 0.022 |
| risk_events | 0.210 |
| reviews | 0.240 |
| monthly_summary | 4.466 |
| risk_report | 1.310 |
| duplicate_lookup | 0.017 |
| dashboard | 2.514 |

These are local EXPLAIN ANALYZE execution measurements, not full HTTP latency or production throughput. XML, source provenance, dependency versions, catalogue/ACL proof and query plans are retained in the existing evidence folders.

**FINTRUST LOCAL RELEASE 1 SYSTEM ASSURANCE PASSED — LIVE AWS E2E REMAINS**

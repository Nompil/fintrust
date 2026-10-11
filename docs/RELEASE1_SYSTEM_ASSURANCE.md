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
| Database constraints and migrations locally | PARTIAL | Isolated empty-schema chain, rerun, drift, row preservation and constraints tested on local PostgreSQL 18.6. |
| PostgreSQL 16 service-role/bootstrap integrity | BLOCKED | No available disposable PostgreSQL 16 administrator environment. PostgreSQL 18 does not prove PostgreSQL 16 membership/ownership behavior; expected service-role test skip remains visible. |
| Smoke and frontend roles | PASS | Compact real-SQL smoke plus actual browser navigation, review/correction and downloads; four roles exercised across suites. |
| Clean start with fresh dependencies / PG16 | BLOCKED | Existing installed Python dependencies and local database reused. Isolated schemas are fresh, but a fresh checkout + clean dependency installation + PostgreSQL 16 is not yet demonstrated. |
| Performance sanity | PARTIAL | Parser measured at 1/100/1,000/5,000 rows; real SQL worker measured at 1/100. No 1,000/5,000-row SQL, N+1, memory or production capacity claim. |
| Secret scan | PARTIAL | Pattern scan of tracked and relevant untracked text; markers, localhost disposable credentials and placeholders classified. No matched values emitted. Pattern scanning is not proof against every secret or personal-data format. |
| Cleanup and preservation | BLOCKED | Proposal recorded; recursive deletion refused a Windows reparse-point child. No files deleted or archived; ignored caches remain. ZIPs, manifests, runner packages and forensic evidence intentionally retained. |
| Live AWS end-to-end chain | BLOCKED | Pending approved base bootstrap/migrations, a current Linux artifact, application deployment, event wiring and live E2E. |
| Enterprise identity, durable notification inbox, hour-velocity rule | DEFERRED | Outside frozen Release 1 scope. |

## API verification map

The component JSON is the exhaustive method/route inventory with handlers and source line numbers. `tests/test_system_assurance.py` derives its protected-route cases from Flask's actual URL map, so a new protected registration cannot silently escape that gate. Authentication failures return 401, role failures 403, malformed authorized requests 400/415, missing objects 404, state/idempotency conflicts 409, and service failures sanitized 500/503 as appropriate. Existing tests cover route-specific success, pagination/filter validation, replay, malformed body, stale version and scoped-object behavior. The new gate does not claim every possible combination on every route.

The public routes are `/`, `/release1`, `/assets/<path:name>` and `/v1/health`. User-governance changes remain local-only and do not issue credentials. Reports/insights/transactions are assigned-account scoped; feed-health oversight is deliberately Admin-only. Maintainer access is technical operations, never financial workflow authority.

## Cleanup and release discipline

`cleanup-proposal.json` classifies bytecode-only candidates. `cleanup-result.json` records the safe refusal. Build history is not disposable merely because it is ignored: failed AWS attempts, pinned packages and release manifests stay. `preserved-files.json` stores hashes of the 157 unrelated files; final verification must compare every hash. No broad delete, reset, move, archive or staging of unrelated files is permitted.

No broken migration reference should be inferred from a convenience filename: the authoritative ordered chain is the base prefix in `sql/schema.sql`, then `001_transaction_identity.sql`, then `002_operational_workflows.sql`. The source review and base manifest remain unmodified. Historical presentation ZIPs remain historical; the API fix requires a newly verified Linux package before any future deployment.

## Reproducible commands and remaining local gates

With already configured dedicated loopback test database credentials (never print them):

```powershell
python tools/run_release1_tests.py tests/test_system_assurance.py
python tools/run_release1_tests.py
```

Browser verification uses the existing Node, Playwright and Chrome paths through `FINTRUST_NODE` and `FINTRUST_PLAYWRIGHT_MODULE`, then `python tools/run_release1_browser.py`. All evidence stays under the existing `docs/EVIDENCE/12-e2e/` hierarchy.

For a genuine clean start, use a fresh source checkout, a fresh Python 3.12 virtual environment with `pip install -r requirements.txt`, a disposable PostgreSQL 16 administrator service, and the existing PostgreSQL 16 role/bootstrap checks and full suite. Create only dedicated loopback test databases; local synthetic seed must never be applied to live RDS. `python tools/local.py setup` prompts for local database administration without persisting administrator credentials. Launch the isolated mock-cloud application with `python tools/serve_release1.py --role Admin --username admin01 --seed-scenarios`; token provisioning is controlled local setup, not enterprise login. This sequence is documented but not claimed executed in a new environment.

Next work is local PostgreSQL 16/clean-start proof and safe cache handling, not AWS execution. Live writes still need their separate approval. No frozen commit was amended, no artifacts rebuilt and no push performed.

## Final observed results

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

**FINTRUST SYSTEM ASSURANCE BLOCKED — PostgreSQL 16 administrator integrity proof, fresh dependency clean-start proof and safe Windows cache cleanup remain incomplete. Full-scale SQL performance remains unverified.**

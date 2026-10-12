# Release 1 local presentation and operating model

Current presentation diagrams and speaker notes: [Release 1 presentation pack](presentation/FinTrust_Project_Planning_and_Design_Evidence.pdf). Earlier milestone references below remain historical unless reconciled in that pack.

This checkpoint verifies a local internal operations application, not a completed live AWS application deployment. Existing cloud stacks are preserved. No AWS request, secret retrieval, database migration, cloud package rebuild, deployment or push was performed in this pass. Financial amounts, duplicate identities and the frozen >5 accepted transactions within 5 minutes velocity rule are unchanged.

## Analyst workspace correction (2026-10-12)

The root URL `/`, `/index.html` and `/release1` now serve the same current workspace. The former root learning page did not send the authenticated Release 1 bearer token; its blank metrics and upload 401 were an entry-point defect. Earlier application freezes and cloud artifacts remain historical and do not include this local correction.

Use the existing loopback launcher with `--role Analyst`, open `http://127.0.0.1:5001/`, and sign in with the same privately entered operator-issued token. The token stays in browser memory; reload requires sign-in. Backend identity, assigned accounts and role checks remain authoritative. Revoked/invalid sessions return to **Session expired / Sign in again to continue**, including failed uploads. No authentication bypass or token embedded in frontend source was introduced.

Analyst lands on Overview with real scoped metrics, risk/activity charts and attention items. **Upload Transactions** exposes the CSV contract from the validator: required columns, alternate source-identity columns, optional columns, one UTF-8 CSV, 1 MiB and 5,000 rows. The button is **Validate and process file**. Results show recorded row totals, pending work and follow-up links; rejected files show the safe reason and that no rows were processed. Exact file replays link to the original batch without processing twice.

Existing account restrictions are preserved. An Analyst cannot read full mixed-batch details containing unknown/unassigned-account rows. For a just-submitted file, the batch link can show the already-authorized **Submission receipt**, explicitly a snapshot rather than refreshed batch state. It reveals no new row data; scoped quarantine/transaction links remain available. Administrator oversight is required for restricted row detail. Receipts are session-local and clear on sign-out.

Reads time out after 15 seconds; writes after 120 seconds. An uncertain upload outcome directs the user to check batch history before retrying. Failed dashboard reads display **Unavailable**, never fabricated zeros. Chart values remain available in expandable tables. Auditor still has no upload, correction or review-mutation controls, and backend denials remain enforced.

Validation and sanitized screenshots: `docs/EVIDENCE/12-e2e/analyst-workspace/`. All verification uses the dedicated local PostgreSQL database and mocked AWS services; unmocked AWS transport is blocked. No AWS mutation, live RDS connection, artifact rebuild/upload or push is part of this correction. Previously frozen cloud ZIPs must not be represented as containing these new frontend/API changes.

## Human operating model

| Identity | Responsibility | Allowed local actions | Boundary |
|---|---|---|---|
| admin01 | Platform governance and audit oversight | Local user records/roles/status, authorized reads and audit oversight | No CSV upload, technical retry, routine review decisions or quarantine correction |
| analyst01, analyst02 | Risk/compliance decisions | Upload CSVs; start/resolve assigned reviews; correct/reject assigned quarantine cases | Corrections revalidate and deduplicate; no direct ledger acceptance, user governance or technical recovery |
| auditor01 | Independent oversight | Scoped financial, report and audit reads | No financial or operational mutations; acknowledgment changes browser session notices only |
| maintainer01 | Technical operations | Inspect pending work/receipts, bounded recovery requests | No financial detail, user governance or compliance decisions |

Roles are permissions, not people. Multiple identities can share a role. The first Admin is provisioned by controlled local setup. The launcher creates five synthetic metadata records if absent. Each identity requires a distinct operator-issued token; blank-hash user records cannot authenticate. Tokens are hidden at provisioning, stored only as hashes in the ignored registry, and held in browser memory during a session. Creating a local user record is not credential issuance. Existing account assignments cannot be widened through the user form. Role/status changes take effect on the next authenticated backend request. Disable preserves identity and historical records; there is no hard-delete endpoint. Current and last provisioned Admin protection prevents accidental lockout.

Added in this pass: minimal local-only user lifecycle endpoints, explicit identity/responsibility labels, Admin/Analyst separation, backend Insights aggregates and eight chart panels, current-page CSV/JSON exports, account-history links, clearer headers and identifier labels, removal of empty Action columns, upload actor-role metadata and user-governance audit receipts. Existing features: hashed-token authentication, account-scoped financial reads, optimistic/idempotent review and correction, immutable ledger, batch reconciliation, technical recovery receipts and four authorization roles.

## Functional truth matrix

All READY classifications below concern the local presentation environment and actual backend contracts. They do not claim cloud integration.

| Feature | Role | UI / backend | Verification | Presentation status | Limits |
|---|---|---|---|---|---|
| Login and named local identity | All | Hidden-token sign-in / hashed registry | Authentication and browser role switches | READY | Operator provisioning; no corporate SSO or password recovery |
| Admin workspace | Admin | Governance, attention and authorized reads | Backend denied review mutation; browser no decision controls | READY | Admin is not the routine financial decision maker |
| Analyst workspace | Analysts | Reviews and quarantine correction | PostgreSQL API and browser review/correction | READY | Assigned accounts; unknown/unassigned-account correction requires a future assignment workflow |
| Auditor workspace | Auditor | Financial/report/audit reads | API denial and hidden mutation controls | READY — READ ONLY | Session notice acknowledgment is not a financial mutation |
| Maintainer workspace | Maintainer | Technical health/pending work/receipts | Backend restrictions and browser Operations | READY | Local mocks are not live CloudWatch/SQS metrics |
| Transactions / detail | Financial roles | Ledger / immutable facts / assessment and timeline | Scope, filters, actual PostgreSQL reads, browser | READY — READ ONLY | Historical seeds are explicitly unscored |
| Risk events | Financial roles | Detection history / transaction navigation | Actual assessments and browser | READY — READ ONLY | Detection is not a human verdict |
| Review queue | Analyst writes; Admin/Auditor reads | OPEN → UNDER_REVIEW → CLEARED/CONFIRMED_RISK/ESCALATED | Version conflict, replay/audit, browser | READY | Terminal reopening deferred; cannot reassign another analyst's review routinely |
| Quarantine / correction | Analyst writes; financial roles read | Original safe payload/history; correction/rejection | Revalidation, deduplication, row preservation, browser | PARTIAL | Unknown-account cases can be visible to Admin but no bypass is provided |
| CSV admission | Analyst | File contract and bounded upload | Constructed fixtures A/B and browser | READY | Synthetic local admission; no live S3 trigger claim |
| Rejected files | Financial reads / Analyst admission | Persistent mock receipt separate from batch | Invalid-file test and browser | READY | Mock S3 persistence ends when local server stops |
| Duplicate classification | Financial reads | Same-row, cross-file, exact-file replay, possible charge | Regression and browser | READY | Similar accepted charge is a risk flag, not silently deduplicated |
| Ingestion batches / reconciliation | Financial reads; Maintainer diagnosis | Received, accepted, quarantine, duplicate, failure, pending | PostgreSQL reconciliation and browser | READY | Boundaries/unknown counts labelled; no silent disappearance |
| Notifications | All appropriate sessions | Open related page / acknowledge | Browser persistence and acknowledgment | PARTIAL | Session-only; no durable inbox, live SES or login/logout audit claim |
| Reports / CSV / JSON | Financial reads | Actual currency/account aggregates and current-page downloads | Backend report regression; browser CSV and JSON downloads | READY | Both CSV and JSON browser verified against current authorized rows. No bank balances, FX consolidation, scheduling or PDF contract |
| Accounts / account history | Financial roles | Exact assigned accounts / scoped ledger | API scope and navigation | READY — READ ONLY | No customer/account administration |
| Audit | Admin/Auditor | Reviews, row dispositions, correction, governance, recovery receipts | Database and mock receipts / browser | READY — READ ONLY | Bounded sources; older actor roles shown as Not captured, never inferred retrospectively |
| Operations | Admin/Maintainer | Pending corrections/projections and receipts; only Maintainer requests retries | Existing operational regression and browser | READY | Queued request is not claimed as completed repair; real cloud recovery still separate |
| User lifecycle | Admin | Create metadata, change role, disable/reactivate | Live auth reload, validation, Admin-only, browser creation | READY | Local single-server registry only; no credential recovery, SSO, dual approval or distributed directory |
| Migration/version visibility | Admin/Maintainer | Contract/source and operational state | Existing operational reads | PARTIAL | Live public schema remains unbootstrapped; this pass performs no migration |
| User login/logout/failed-login ledger | — | No durable session event service | Explicitly absent | DEFERRED | Do not invent historical events |
| Enterprise authentication / durable user directory | — | Not implemented | Explicitly absent | DEFERRED | Production hardening requires a separately reviewed identity design |

## Insights and diagrams

| View | Data / scope | Status | Interpretation |
|---|---|---|---|
| Transaction activity | PostgreSQL transaction UTC date/count | READY | 7/30/90/all period; actual date spacing, no forecast |
| Risk distribution | processed_transactions joined to authorized ledger | READY | Unscored seeds excluded; counts, not fabricated percentages |
| Rules triggered | Actual stored assessment rules | READY | A transaction may trigger multiple rules; totals need not equal transaction count |
| Account activity | Assigned ledger transaction counts | READY | Counts avoid invalid currency consolidation |
| Domestic / cross-border | Actual transaction flag | READY | Cross-border is a factor, not proof of fraud |
| Data quality | Primary reason per authorized quarantine case | READY | Latest 100 bounded cases; not the number of every validation error |
| Review outcomes | Current review state joined to ledger | READY | Current state, not transitions over time |
| Batch outcomes / reconciliation | Actual reconciliation view | READY | Admin all-account oversight includes unknown cases; filtered/non-Admin charts include only wholly authorized batches |
| Architecture, decisions, recovery, role diagrams | [Seven authoritative diagrams](presentation/FinTrust_Project_Planning_and_Design_Evidence.pdf) | READY | Local implementation and AWS target distinguished; historical graphic exports remain historical |

Financial charts enforce assigned accounts and reject foreign account IDs. Admin unfiltered batch/quarantine oversight follows the existing authorized oversight scope and is labelled separately. Selecting one account narrows to wholly authorized batches, excluding mixed/unassigned batches; therefore those totals may differ from Admin's unfiltered oversight. Batch timestamps use received_at, quarantine uses quarantined_at, financial charts use tx_date. Exact numbers are supplied below each chart, with empty states and bounded-data warnings. A filtered transaction period is not automatically a report-export period: Reports currently supports account/pagination only.

## Audit and evidence truth

User lifecycle receipts include actor, role, target, UTC timestamp, result, safe before/after metadata and mandatory reason. New upload receipts include actor role. Existing PostgreSQL review/correction records already capture the named acting subject; their historical role was not stored, so it is displayed as Not captured. System row dispositions are marked SYSTEM. Governance writes a REQUESTED receipt before changing the registry, then SUCCESS; if a final receipt update fails, the prior REQUESTED record remains for investigation. Mock S3 receipts are versioned, not a production immutable compliance archive. Do not run multiple local server processes writing the same registry.

Browser evidence: docs/EVIDENCE/12-e2e/presentation-readiness/browser/ (screenshots, browser-result.json and report-current-page.csv). Test evidence is recorded in verification.json beside it after the final run. Browser source_commit identifies the baseline; source files have local uncommitted refinements. It does not represent a newly frozen release artifact.

## Launch and reset

Run in PowerShell from C:\Users\Nompilo\Desktop\fintrust. Existing local PostgreSQL setup must be available; commands reject remote database hosts and use only fintrust_local_test.

```powershell
py -3.14 tools/serve_release1.py --role Admin --username admin01 --seed-scenarios
```

Enter a distinct random token (32–256 characters) at the hidden prompt, then open http://127.0.0.1:5001/release1 and enter that token to sign in. It is never printed. Ctrl+C stops the server; mock cloud receipts end with that process. Before presentation, provision the other four identities once by launching/stopping each with its distinct token:

```powershell
py -3.14 tools/serve_release1.py --role Analyst --username analyst01
py -3.14 tools/serve_release1.py --role Analyst --username analyst02
py -3.14 tools/serve_release1.py --role Auditor --username auditor01
py -3.14 tools/serve_release1.py --role Maintainer --username maintainer01
```

Then run Admin mode again; all provisioned identities can sign in on that one server. Changing browser identity does not change backend authority. Do not use the deterministic test tokens in a presentation server.

For an intentional clean synthetic reset only:

```powershell
py -3.14 tools/serve_release1.py --role Admin --username admin01 --reset --seed-scenarios
```

Reset checks the exact candidate schema owner and identifying comment, then recreates only fintrust_release1_candidate in the dedicated loopback test database. It does not reset the auth registry, unrelated local schemas, evidence files or AWS. Do not repeatedly use --seed-scenarios without reset: each invocation deliberately adds a new labelled constructed input. For a clean five-minute presentation reset once, then upload the repository-defined fixtures if needed. They are constructed Release 1 fixtures, not the missing external ChatGPT CSVs:

- tests/fixtures/e2e/release1/fintrust_release1_transactions_A.csv
- tests/fixtures/e2e/release1/fintrust_release1_transactions_B.csv

## Five-minute presentation path

1. **0:00–0:45 Admin:** show identity, local environment and responsibilities, Overview attention links, and Administration (records, credential-provisioned distinction). Explain governance versus financial decisions.
2. **0:45–1:45 Analyst:** sign in as analyst01 and admit constructed A, inspect accepted/quarantine/duplicate batch counts, upload B, replay A. Open the rejection/duplicate evidence; no extra ledger entries appear on exact replay.
3. **1:45–2:30 Financial reads:** Insights risk/rule charts, high-risk accepted transaction and possible duplicate-charge detail. Explain valid high risk versus invalid quarantined data, and unscored historical rows.
4. **2:30–3:45 Analyst:** sign out/in as analyst01; OPEN → UNDER_REVIEW → CLEARED with reason. Correct a numeric quarantine case; the worker revalidates and deduplicates rather than approving directly into the ledger. Original evidence remains.
5. **3:45–4:30 Auditor:** sign in as auditor01; view review/audit/report and download a current-page CSV. Point out missing mutation controls and backend enforcement.
6. **4:30–5:00 Maintainer:** sign in as maintainer01; show pending technical work/receipts. Explain technical recovery authority cannot clear a financial risk. Finish with what is local verified and what is still a separate live-release gate.

The application sources changed in this pass. The previously frozen ZIP is unchanged and does not contain these changes. Any later cloud release must rebuild and repeat the Linux verification gate under a separate approved release task. No cloud artifact was rebuilt here.

## Correction after the original freeze

The separately approved role/workflow correction makes Analyst the only upload role and Maintainer the only technical retry role; Admin retains read-only operations oversight. Analyst lands in Review Queue, Admin/Auditor in Overview, Maintainer in Operations. Upload, result and history are ordered accordingly. Structured rejection details identify missing CSV columns without showing request IDs. See `docs/RELEASE1_ROLE_WORKFLOW_UX.md`. The results below describe the original frozen checkpoint; current correction evidence is separate.

## Original freeze verification

- Full local regression: **641 passed, 0 failed, 1 expected environment skip, 0 unexpected skipped**.
- Focused readiness checks: **14 passed, 0 failed, 0 skipped**, including actual named-user launcher/reset protection.
- Final browser gate: **1 passed, 0 failed, 0 skipped**; four roles, 8 charts, CSV/JSON downloads, account-history navigation, actual review/correction and user creation. Screenshots visually inspected at 1440-pixel presentation width.
- The expected full-suite skip is `tests.data_quality.test_processing.test_database_roles_can_execute_pipeline_without_owner_privileges`: the local test account is not a disposable database administrator. This is not reported as a newly verified SQL-service-role execution test.
- JavaScript syntax and focused Git whitespace checks passed. Source fingerprints and sanitized XML are in `docs/EVIDENCE/12-e2e/presentation-readiness/verification.json`.
- No AWS actions, cloud artifact rebuild or push. This verified application state is frozen in one focused local commit; existing unrelated infrastructure-document/evidence changes are intentionally excluded and preserved. See `docs/EVIDENCE/12-e2e/presentation-readiness/freeze-report.md` for the final checks and file inventory.

FINTRUST RELEASE 1 PRESENTATION READINESS VERIFIED


## Final presentation UX freeze (continues 37da9d4)

This is a presentation-only correction of the locally verified application. Schema, primary keys, foreign keys, API identity, deduplication, thresholds, review states, migration semantics, report calculations and chart calculations are unchanged. Backend read adapters add the sum of existing scoped batch technical-failure counters and the stored processing result on risk-event reads (using the same one-to-one join already used by reviews). Risk levels/rules come from that stored result; historical levels are never calculated from old scores. Verification uses a disposable PostgreSQL 16.15 database and mocked cloud services; it is not live AWS proof.

### Display references and historical data

The five approved synthetic accounts display `ACC-0001` through `ACC-0005`; selectors add the actual account type while option values remain UUIDs. Existing numeric risk-event IDs display as zero-padded `RISK-0091` without changing their numeric API/SQL identity. Other accounts and transactions/batches use deterministic typed aliases (`ACC-`, `TX-`, `BATCH-`, `RISK-`) with a 13-character base36 FNV-1a 64-bit suffix derived from the normalized UUID. Aliases remain stable across sorting, pagination and sessions; they are display aids, not financial account numbers, authorization handles or guaranteed globally unique primary keys. A 10,000-alias test checks the tested input set for collisions. Full UUIDs remain in Details, Audit/Operations and the primary-cell Internal ID tooltip/data attribute. Report downloads retain authoritative UUIDs for traceability. Optional advanced filters explicitly request internal IDs; aliases are never sent to a UUID API.

Transactions without Release 1 scoring evidence show **Not assessed**, not Low. Missing historical source references show **Not recorded**. Batch detail connects File -> Batch -> Rows -> Transactions and labels accepted transactions separately from quarantined rows, duplicates and technical failures. Upload/current work precedes history; active notices precede acknowledged notices. Short page descriptions replace generic explanations. Primary tables use horizontal scrolling with unbroken headers.

### Analyst demo route

Open `/release1`, sign in as `analyst01` with its separately provisioned token. Review Queue is the landing page; the header says “Review risk, upload transactions and correct data issues.” Show Overview attention counts -> Ingestion Batches upload/latest receipt/history -> Batch detail -> Transactions and historical Not assessed -> Quarantine correction -> Risk Events/Review Queue -> Insights (all eight API-backed charts) -> Reports -> Notifications. Acknowledge notices only after reviewing the linked outcome. `analyst02` is a distinct identity with the same role, not a second role.

### Auditor demo route

Sign out, then sign in as `auditor01`. Overview emphasizes audit/report access and “Review transaction, risk and audit evidence. Changes are disabled.” Show Transactions -> Risk Events/Review Queue evidence -> Insights -> current-authorized-page CSV/JSON reports -> Audit. Upload, correction and review mutation controls are absent; direct requests remain backend-denied. Admin retains governance/read oversight; Maintainer retains technical Operations only.

### Safe local role switching

The chosen safe fallback is the existing **Sign out -> operator-issued token -> Sign in** mechanism. There is no frontend role flag, token-issuing endpoint or automatic impersonation dropdown. Registry entries contain only hashes, so the UI cannot derive another user's credential safely. Before a presentation, the operator must provision each named identity separately using the verified launcher, entering distinct tokens via its hidden prompt (never Git, logs or evidence):

```powershell
python tools/serve_release1.py --role Admin --username admin01
python tools/serve_release1.py --role Analyst --username analyst01
python tools/serve_release1.py --role Analyst --username analyst02
python tools/serve_release1.py --role Auditor --username auditor01
python tools/serve_release1.py --role Maintainer --username maintainer01
```

Run one at a time and stop it before provisioning the next; restart the final server afterward. The ignored hashed registry retains the provisioned identities. Browser sign-in establishes actual backend identity and scope. Sign-out clears tokens, notices, filters and pending UI context; the existing stale-response guard prevents old-role results leaking into a new session. Production identity remains a separate gate. The test harness uses controlled synthetic tokens for browser verification and never records their values in evidence.

### Insights, metrics and notifications

The verified source uses `/v1/release1/insights` with only `days` and optional `account_id`, not the generic workflow route. `/` still loads the older single-score learning interface; it now links explicitly to `/release1`. No reproducible 404 exists on the current Release 1 route. The screenshots' original upstream 404 cause cannot be established without their URL/request or matching historical runtime. What is proven from source is that the previous generic error handler displayed raw `body.error/detail` (including “Not Found”) and cleared failed content. The corrected adapter gives a contextual recovery message and a useful notice title without exception/route/request details. Versioned asset URLs refresh this release's HTML/JS/CSS combination. A forced-404 browser case must show the friendly message and recover to all eight charts after refresh; no hidden fallback or hardcoded chart values are used.

Overview counters use backend values, including scoped technical failures. Missing values or an API failure show **Unavailable**, never an invented zero; Refresh retries the actual request. Normal notices contain a title, outcome, timestamp and next action/link, with active notices ordered before acknowledged history. Severity remains an internal CSS/state field, rather than the displayed title “ERROR.” No claim that technical support was automatically notified is made.

### Verification boundary

The extended browser gate compares all eight chart tables with their actual API values separately for Analyst and Auditor, checks readable references with UUID transport, historical missing values, role changes, Auditor mutation denial, metric failure versus zero, forced Insights failure/recovery, normal notice sanitization and existing report/download/review/correction/security behavior. Node is an explicit prerequisite for the display-adapter test (`FINTRUST_NODE`, or a Node executable on PATH). PostgreSQL schema/service-role assurance and the full suite are repeated against the source overlay of this checkpoint.

Final results and source hashes are recorded under `docs/EVIDENCE/12-e2e/presentation-ux-freeze/`; PostgreSQL verification is under `docs/EVIDENCE/05-rds/presentation-ux-freeze/`. Earlier freezes and evidence remain historical. The existing Linux artifact is unchanged and is stale relative to this UX source: rebuild and verify it from the final commit only in the next approved task. No AWS action or push occurs here.

### Final observed verification

- Focused UX/API/RBAC/report gate: **94 passed, 0 failures, 0 skips**.
- Extended browser gate: **1 passed, 0 failures, 0 skips**; four backend roles, all eight charts separately checked for Analyst/Auditor, historical labels, report downloads, actual review/correction flows, safe failure recovery and Auditor write denial. Screenshots visually reviewed.
- Full local regression against the final source overlay: **713 passed, 0 failures, 0 skips**.
- PostgreSQL 16.15 bootstrap -> 001 -> 002 -> seed and privilege checks passed unchanged: 17 tables, 2 views, 85 validated constraints, 36 indexes, 0 unexplained integrity violations. The disposable cluster was stopped afterward.
- The isolated dependency environment from the prior verified checkpoint was reused and checked; this is not a claim of a new installation or Linux-runtime artifact verification.
- All 157 unrelated files preserved. No AWS, live DB write, package rebuild or Git push. Application UX is frozen after this local commit; no remaining presentation blocker found in the tested scope.

FINTRUST USER EXPERIENCE VERIFIED — ANALYST AND AUDITOR DEMO READY

### Running-server entry compatibility (2026-10-12)

The user's existing port-5001 process was still serving `frontend/index.html` from the previous Python route, while `/release1` served the current authenticated workspace. A running server does not reload Python route changes automatically. The legacy HTML now redirects to `/release1`, with an accessible sign-in link as a fallback. This fixes the already-running process without stopping it, resetting synthetic data, replacing tokens, or bypassing authentication. The local HTTP check confirmed the redirect and the user's in-app browser reached the current sign-in screen. Authenticated data still requires the existing privately entered operator-issued token; no token was retrieved or provisioned for this correction.

# Release 1 local presentation and operating model

This checkpoint verifies a local internal operations application, not a completed live AWS application deployment. Existing cloud stacks are preserved. No AWS request, secret retrieval, database migration, cloud package rebuild, deployment or push was performed in this pass. Financial amounts, duplicate identities and the frozen >5 accepted transactions within 5 minutes velocity rule are unchanged.

## Human operating model

| Identity | Responsibility | Allowed local actions | Boundary |
|---|---|---|---|
| admin01 | Platform governance and audit oversight | CSV admission, local user records/roles/status, technical recovery | No routine review decisions or quarantine correction |
| analyst01, analyst02 | Risk/compliance decisions | Start/resolve assigned reviews; correct/reject assigned quarantine cases | Corrections revalidate and deduplicate; no direct ledger acceptance, user governance or technical recovery |
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
| CSV admission | Admin | File contract and bounded upload | Constructed fixtures A/B and browser | READY | Synthetic local admission; no live S3 trigger claim |
| Rejected files | Financial reads / Admin admission | Persistent mock receipt separate from batch | Invalid-file test and browser | READY | Mock S3 persistence ends when local server stops |
| Duplicate classification | Financial reads | Same-row, cross-file, exact-file replay, possible charge | Regression and browser | READY | Similar accepted charge is a risk flag, not silently deduplicated |
| Ingestion batches / reconciliation | Financial reads; Maintainer diagnosis | Received, accepted, quarantine, duplicate, failure, pending | PostgreSQL reconciliation and browser | READY | Boundaries/unknown counts labelled; no silent disappearance |
| Notifications | All appropriate sessions | Open related page / acknowledge | Browser persistence and acknowledgment | PARTIAL | Session-only; no durable inbox, live SES or login/logout audit claim |
| Reports / CSV / JSON | Financial reads | Actual currency/account aggregates and current-page downloads | Backend report regression; browser CSV and JSON downloads | READY | Both CSV and JSON browser verified against current authorized rows. No bank balances, FX consolidation, scheduling or PDF contract |
| Accounts / account history | Financial roles | Exact assigned accounts / scoped ledger | API scope and navigation | READY — READ ONLY | No customer/account administration |
| Audit | Admin/Auditor | Reviews, row dispositions, correction, governance, recovery receipts | Database and mock receipts / browser | READY — READ ONLY | Bounded sources; older actor roles shown as Not captured, never inferred retrospectively |
| Operations | Admin/Maintainer | Pending corrections/projections, receipts and controlled retries | Existing operational regression and browser | READY | Queued request is not claimed as completed repair; real cloud recovery still separate |
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
| Architecture, decisions, recovery, role diagrams | [Current operating-model diagrams](diagrams/release1-operating-model.md) | READY | Local implementation and AWS target distinguished; historical graphic exports remain historical |

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
2. **0:45–1:45 Admin:** admit constructed A, inspect accepted/quarantine/duplicate batch counts, upload B, replay A. Open the rejection/duplicate evidence; no extra ledger entries appear on exact replay.
3. **1:45–2:30 Financial reads:** Insights risk/rule charts, high-risk accepted transaction and possible duplicate-charge detail. Explain valid high risk versus invalid quarantined data, and unscored historical rows.
4. **2:30–3:45 Analyst:** sign out/in as analyst01; OPEN → UNDER_REVIEW → CLEARED with reason. Correct a numeric quarantine case; the worker revalidates and deduplicates rather than approving directly into the ledger. Original evidence remains.
5. **3:45–4:30 Auditor:** sign in as auditor01; view review/audit/report and download a current-page CSV. Point out missing mutation controls and backend enforcement.
6. **4:30–5:00 Maintainer:** sign in as maintainer01; show pending technical work/receipts. Explain technical recovery authority cannot clear a financial risk. Finish with what is local verified and what is still a separate live-release gate.

The application sources changed in this pass. The previously frozen ZIP is unchanged and does not contain these changes. Any later cloud release must rebuild and repeat the Linux verification gate under a separate approved release task. No cloud artifact was rebuilt here.

## Final verification

- Full local regression: **641 passed, 0 failed, 1 expected environment skip, 0 unexpected skipped**.
- Focused readiness checks: **14 passed, 0 failed, 0 skipped**, including actual named-user launcher/reset protection.
- Final browser gate: **1 passed, 0 failed, 0 skipped**; four roles, 8 charts, CSV/JSON downloads, account-history navigation, actual review/correction and user creation. Screenshots visually inspected at 1440-pixel presentation width.
- The expected full-suite skip is `tests.data_quality.test_processing.test_database_roles_can_execute_pipeline_without_owner_privileges`: the local test account is not a disposable database administrator. This is not reported as a newly verified SQL-service-role execution test.
- JavaScript syntax and focused Git whitespace checks passed. Source fingerprints and sanitized XML are in `docs/EVIDENCE/12-e2e/presentation-readiness/verification.json`.
- No AWS actions, cloud artifact rebuild or push. This verified application state is frozen in one focused local commit; existing unrelated infrastructure-document/evidence changes are intentionally excluded and preserved. See `docs/EVIDENCE/12-e2e/presentation-readiness/freeze-report.md` for the final checks and file inventory.

FINTRUST RELEASE 1 PRESENTATION READINESS VERIFIED

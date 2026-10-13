> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Release 1 role and workflow correction

Separate correction after the immutable presentation parent `5b5bb50f4bf02bca518940675f9b476bd8750a67`. Application source changed; the historical Linux artifact remains unchanged and a new source-bound build is still required before cloud deployment. No AWS, live SQL, seed changes, scoring changes or deployment occurred.

## Findings and behavior

The exact screenshot file was not supplied. The old `samples/transactions_day2.csv` and original external fixtures use the legacy schema: Release 1 requires `source_system` plus either `source_transaction_id` or `source_reference`. A .csv extension alone cannot satisfy this contract. Missing columns now appear in safe rejection details. Duplicate headers, unsupported columns, encoding, empty/header-only files and malformed structure have specific bounded messages. Invalid amounts, types and timestamps within admitted rows continue to follow the existing quarantine rules rather than rejecting otherwise valid rows.

Uploads now require Analyst on both the HTTP boundary and the upload adapter. Admin, Auditor and Maintainer cannot upload. Technical retries/redrive require Maintainer; Admin retains read-only operations visibility and user governance. Analyst has review/correction authority but cannot administer users or technical retries. Manual endpoint calls are covered by regression tests; hidden buttons alone are not the authority.

Analyst lands in Review Queue, Admin/Auditor in Overview and Maintainer in Operations. Upload form appears before latest notices and batch history; selected review/correction and technical actions appear before history. Active review/quarantine rows sort before closed history. Notifications remain session-private and persistent until acknowledged, with separate items rather than concatenated messages. Main errors omit correlation UUIDs and hide server failures; technical/audit records retain their correlation IDs. Table headers no longer split words.

Eight backend-driven charts, report downloads, identity/deduplication, financial validation, risk thresholds and immutable evidence are preserved. Reports continue to export the current authorized account/page, not an invented date-period selection.

## Known scope limits

At this historical freeze, non-Admin batch views excluded unknown/unassigned outcomes. That limitation is superseded only for genuinely unknown rows in the original authenticated uploader's batch by the explicit approval below. Batches containing known unassigned accounts remain inaccessible. Historical rule: unknown-account correction was deferred at this freeze. The explicitly approved continuation now permits an active Analyst to view and correct genuinely unknown/missing-account rows from their original authenticated local upload only. The first-admission receipt is immutable and versioned; duplicate re-upload does not transfer ownership. Corrected accounts must exist and be assigned. Historical batches without ownership evidence and cloud intake without trusted admission remain blocked. Known unassigned accounts remain inaccessible. The browser exercises scoped Analyst review/correction and Admin batch reconciliation separately. Notifications clear on sign-out to prevent another user seeing the uploading user's session history.

## Verification

Results and separate screenshots are under `docs/EVIDENCE/12-e2e/role-workflow-ux/`. Existing focused regression passed 122 checks; six new role/error checks and two offline bootstrap composition checks passed. The final four-role browser gate passed after verifying action-before-history layout, upload actor, separate notices and concealed Admin mutations. Full regression outcome is recorded in verification.json. The original freeze evidence is not overwritten.

FINTRUST ROLE AND WORKFLOW UX VERIFIED


## 13 October 2026 — recorded score and monitoring dashboard refinement

Transactions and Account History show the existing recorded rule score out of 100 alongside severity. A recorded zero is shown as 0/100; absent historical assessment remains Not assessed. No rescoring, scoring thresholds, API or schema changes. Score is not a probability of fraud. Column sorting covers the displayed page, with missing scores last.

The Overview uses a compact light workspace, dark FinTrust navigation, six real metrics, activity/count chart, assessed-risk distribution, rule/review charts and the existing investigation queue/drawer. Dense tables scroll within their panels on narrow screens; transaction dates/identifiers remain compact. Assigned accounts and all recorded dates are explicit; the existing scoped analytical filters are reached through Insights, not a cosmetic filter that changes no data.

DECISION | SOURCE | WHY IT APPLIES | HOW FINTRUST USES IT: Compact monitoring/investigation workspace | https://www.datadoghq.com/ and user-supplied monitoring screenshots | Operators need counts, evidence and next actions in a readable workspace | Adapt interaction density, tables and adjacent investigation; keep FinTrust identity and original brief. No external logo, copied icons or proprietary layout assets.

Verification: 29 focused local SQL/browser tests passed; final mobile row-height polish passed the workbench browser separately. Evidence: docs/EVIDENCE/12-e2e/monitoring-score-ui/. The earlier 847/1 full regression remains its original checkpoint, not a new full-suite claim. No AWS, user credential or persisted financial changes; the user-requested local port-5001 server remains stopped.


## 13 October 2026 — console-5 operational overhaul

The user rejected the previous refinement and requested a major structural overhaul. The new console replaces the layered stylesheet with one theme, an icon-led FinTrust sidebar, compact top bar, breadcrumb and a role-scoped workspace finder (Ctrl+K). Mobile navigation has an explicit toggle. The workspace finder only lists navigation permitted for the current role; API authorization remains authoritative.

Overview now puts the active review queue beside next actions, with real metrics above and transaction/risk/scenario/review charts below. Transactions use a dedicated filter rail and a dense ledger with recorded scores. Risk Events and Review Queue use a facet rail, matching counts and the existing ownership filters. Sorting table headers covers the displayed page; investigation Sort uses the existing backend ordering.

Investigation opens alongside the list. A transaction/severity/recorded-score header leads into WHAT HAPPENED and WHY IS IT RISKY, with WHEN, WHERE, account context, related activity and recorded history retained. Evidence tabs focus the same returned evidence. NEXT STEPS has a distinct action column with claim/assignment, notes and outcome controls according to the existing backend permissions. Outcome buttons select an action; saving still requires notes and the existing version/idempotency contract. HIGH remains an accepted ledger entry, not invalid data or an automatic fraud decision.

Quarantine uses original evidence and correction history beside a separate recovery/action column. Missing original evidence still blocks correction. Own unknown-account correction still requires original upload ownership and an existing assigned target account. Admin user governance and Maintainer recovery remain separate.

| DECISION | SOURCE | WHY IT APPLIES | HOW FINTRUST USES IT |
| --- | --- | --- | --- |
| Dense operational explorer with adjacent evidence and next actions | https://www.datadoghq.com/ and user-supplied Datadog screenshots | Investigations need context and action without losing the work queue | Adapt filter rails, readable tables and a distinct investigation action column; use FinTrust colors, labels and original SVG icons. No copied branding/assets and no expanded domain scope. |

Verification: 111 affected regression tests passed using real isolated PostgreSQL, AWS mocks and browser network isolation. After the final evidence/action ordering adjustment, all four browser scenarios passed again. The four role workspaces, role-scoped finder, mobile navigation, evidence tabs, scores (including zero/missing), partial/full errors, claim/notes/clear, correction/worker acceptance and missing-evidence restriction were exercised. This is an affected-suite checkpoint, not a new full-regression or live AWS claim.

Screenshots and source hashes: `docs/EVIDENCE/12-e2e/console-overhaul/`. Screenshots use synthetic isolated test data. The requested local server is running on `http://127.0.0.1:5001/release1`; existing credentials and persisted user workspace data were preserved.

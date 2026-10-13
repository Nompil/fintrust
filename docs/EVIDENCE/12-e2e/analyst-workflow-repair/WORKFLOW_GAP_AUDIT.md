# Analyst workflow repair - gap audit

Baseline application: `38e2f2fc2f58eca50875b4f22bbc07841036fe54` (904/904 Linux verified).
This repair creates a new candidate. Its exact-source Linux gate is required before AWS deployment.
Verification uses a fresh disposable PostgreSQL 16.15 cluster, synthetic named users and mocked AWS boundaries. The preserved financial database and operator credentials are not test fixtures.

## Workflow findings and acceptance evidence

| Area | Previous behaviour | New behaviour | Evidence / test |
| --- | --- | --- | --- |
| Ingestion | Upload follow-up could lose the originating run and reveal accumulated quarantine history. | Processing result preserves internal batch identity, full reconciliation and links to run-scoped rows and processing details. | `test_analyst_journey_browser.py`; `test_analyst_experience_api.py`; existing dataset lifecycle checks. |
| Quarantine | Generic heading, unclear original run, correction/rejection and worker outcome separated across views. | Quarantined Rows shows file/run/row/issue/status/age; View issue leads to notes, correction or rejection and resulting row/transaction timeline. Show all clears the originating-run filter. | Journey scenarios D/E; API run-filter and scope tests; existing original-evidence/ownership/recovery tests. |
| Scoring | Numeric score and missing assessment labels could obscure the reason for admission versus risk. | Frozen score/components/measurements remain authoritative; LOW remains accepted, visible and auditable without routine review or alert. | Journey A/B/C; unchanged V2 tests; malformed/missing/legacy assessment tests. |
| Review creation | Medium/High reviews were already created transactionally, but missing review UI states were ambiguous. | Recorded review is explicit; LOW says No review required, genuinely legacy records say Historical - no review record, unsupported gaps say Not recorded. No review is invented from score alone. | Evidence model tests; existing V2 review eligibility/replay tests. |
| Assignment | Owner existed, but attribution/time was difficult to discover. | Current named owner, recorded assignment time/by identity and immutable assignment history appear with Mine/Unassigned/All visible queue choices. Existing claims/reassignment concurrency and permissions remain unchanged. | Model/history tests; multi-user operations; journey claims and cross-role denial assertions. |
| Investigation | Transaction and technical status fields were easier to find than an ordered investigation process. | Transaction -> measured components -> account context -> investigation notes -> permitted decision. Actions use existing owner/version/role controls. | Journey B/C; existing investigation, multi-user and V2 browser gates. |
| SLA | Optional single global deadline, with no explicit Medium/High/escalation policy. | Configurable Medium 24h, High 4h and Escalated 2h policy; due/overdue/due-soon derives from existing timestamps. SQL queue order/filter and aggregate counters share the same policy and clock. No automatic decision. | Model deadline boundaries/configuration/escalation tests; priority-before-pagination checks; journey G. |
| Decision | Existing notes/version/ownership controls worked; next action and result were less explicit. | Only the owning Analyst under review sees final outcomes. Required notes, resolution and immutable decision history remain enforced by the existing backend. | Existing clear/confirm/escalate and authorization tests; journey SQL/audit assertions. |
| Alerting | Raw delivery codes could be mistaken for a delivered email or a financial decision. | Display actual independent delivery evidence: pending/sent/failed/uncertain/not required/not recorded. High risk is investigation priority; it does not establish fraud or prove delivery. | Existing alert-failure-without-ledger-rollback tests; transaction lifecycle/API and HIGH journey checks. |
| Audit | Technical action labels and historical role gaps were hard to interpret. | Read-only action projection distinguishes creation/claim/reassignment/note/decision and exposes actor, supported human/system type, time, request and previous/new state. Stored evidence is unchanged. | Existing immutable-history/replay tests; API actor attribution and journey audit assertions. |
| Reporting | Insights charts were separate from underlying evidence. | Four question groups connect activity -> risk -> attention -> outcomes; filters and drill-down preserve account/date/risk/scenario/review/country/type scope. Risk rates exclude unscored history. Reports retain their existing account/currency/time/export contracts. | API filter/scope tests; browser drill-down and exact report exports; existing report regressions. |
| Historical records | Missing scores could become a generic Not assessed fallback. | Historical label requires explicit canonical bootstrap provenance without modern intake evidence. An old timestamp alone proves nothing. Recorded pending/failure state is distinct; insufficient evidence remains Not recorded with an explanation. | Model/API legacy versus modern/malformed tests; journey F and V2 legacy browser gate. |

## Schema and policy

No Migration 007 is needed. Existing `risk_reviews` and `risk_review_history` already preserve current owner, creation time, version, assignment changes, escalation transitions and human/system actors. SLA is a configured read projection over those records, not a competing transaction-state model.

Configuration: `FINTRUST_REVIEW_SLA_ENABLED`, `FINTRUST_REVIEW_MEDIUM_SLA_SECONDS` (86400), `FINTRUST_REVIEW_HIGH_SLA_SECONDS` (14400), `FINTRUST_REVIEW_ESCALATED_SLA_SECONDS` (7200), and `FINTRUST_REVIEW_SLA_DUE_SOON_SECONDS` (3600). Explicit disabling displays Not configured. The older single-target environment setting remains a compatibility override where a per-level value is absent. Completed decisions have no active deadline; reopening an existing review does not fabricate a new creation time. Escalation starts a target only when a recorded escalation transition exists.

Queue priority is calculated before pagination: overdue, active HIGH, due soon, escalated, active MEDIUM, then oldest remaining case. The sort does not alter severity, ownership, decisions or financial rows.

## Evidence boundaries retained

- Historical SQL human actions do not persist role-at-action. Their role is explicitly Not recorded; current registry roles are not substituted retrospectively. Human/system type is exposed where supported by the existing action/actor provenance. Trusted immutable upload/governance receipts retain their originally recorded roles. This repair does not claim retrospective role completeness.
- Partially processed runs still obey existing full-run account authorization. An already-authorized submission receipt can explain pending processing without exposing unassigned financial rows. It is labelled as a receipt snapshot, not refreshed row evidence.
- Processing completion display uses the latest recorded row-outcome timestamp, with that derivation disclosed. No new completion event or timestamp is invented.
- Technical retries, redrive, SES, cloud scheduling, live AWS wiring, capacity and production readiness remain separately gated. Automatic routing/load balancing, behavioural scoring, AI and regulatory filing are outside this repair.

## Mark as read

The former Acknowledge action sets the browser-session notification's `acknowledged` flag and dismisses its banner. It sends no financial mutation request and changes no transaction, processing outcome, review, correction or database audit record. The UI now says Mark as read and explains that boundary.

## SOP terminology and capture

Use Upload Transactions, Quarantined Rows, Processing History, Processing Details and Processing Run. Internally keep the original batch keys, UUIDs and API/database names. Retake the broken Processing Details screenshot and the unfiltered Quarantine screenshot after interactive validation. No final SOP, screenshot numbering or completed capture claim is created here.

## External-reference decisions

| Decision | Source | Why it applies | How FinTrust uses it |
| --- | --- | --- | --- |
| List-preserving investigation with ownership and visible triage | https://docs.datadoghq.com/security/application_security/threat_protection/security_signals/ | Analysts need context and actions together without losing queue position. | Existing FinTrust detail workspace and permitted actions; original branding and review outcomes retained. Datadog statuses are not imported. |
| Consolidated evidence, notes and resolution | https://docs.sumsub.com/docs/case-management | Avoid searching disconnected screens during one investigation. | Recorded transaction/component/account/history evidence together. No KYC/AML expansion, AI decisions, regulatory filings or automatic assignment. |
| Keep authorization at every server boundary | https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html | More navigation and filtering must not confer greater account or action access. | Reuse existing backend role/account/owner checks; test direct mutation denials and foreign-scope filters. |
| Preserve row locks/versioned updates | https://www.postgresql.org/docs/16/explicit-locking.html | Concurrent claims and decisions must preserve a single current owner and immutable history. | Existing mutation locking/version logic remains unchanged; read-only deadline and assignment projections reuse its history. |

Final local regression: **961 passed, zero failures, zero skips** (+57 cases). All eight in-suite browser gates and the separate four-role CI walkthrough passed. Nineteen refreshed desktop/mobile acceptance screenshots cover processing, quarantine, assessment, investigation, SLA and Insights. The three first-run verification failures were corrected and their five focused checks passed before the clean full regression.

Results, candidate-ref resolution, production fingerprints and preservation proof are recorded in `verification-summary.json`. All 18 preserved tables, including 206 ledger entries, remain identical; all eight pre-existing tracked edits and the credential/configuration files remain unchanged. No scoring, financial mutation or schema change occurred. Prior Linux proof remains valid only for its original source. Interactive SOP capture and exact-candidate Linux re-verification are the next gates; no final SOP, AWS action, deployment or push occurred here.

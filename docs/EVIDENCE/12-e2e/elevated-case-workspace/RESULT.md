# Elevated Analyst workspace — 14 October 2026

This phase completes the wider case workspace authorized in the conversation. The original FinTrust brief, frozen V2 scoring, role separation, existing review targets and financial records remain authoritative. Local proof does not establish live AWS integration.

## Delivered experience

| Area | Result | Evidence to inspect |
| --- | --- | --- |
| Overview | Five actionable My day counters; risk distribution, HIGH trend, account rankings, processing outcomes, SLA distribution and recent case/source activity | Overview desktop/mobile frames |
| My Work | My Work, Unassigned, Due today, Overdue, High priority, Specialist review, Recently completed and All visible; ownership, deadline, priority, score and next action | Work-view browser journey; API calendar boundary checks |
| Upload | Prepare → Submit → Review result; collapsed API requirements; assigned-account sample; file size/name; clear selection; visible processing state | Upload and result frames |
| Processing result | Actual row reconciliation, original submitter/time, recorded risk-event link; zero-outcome actions disabled; earlier unread warnings retained | A/B/exact replay role walkthrough |
| Insights | Four business questions; line/area trends, proportion rings, ranking bars, SLA ring, processing segments, exact-value tables and authorized drill-downs | Insights top/risk/attention frames |
| Investigation | Frozen risk components, current ownership, source file/system/uploader/run/row and vertical recorded journey, notes, decisions and requested referral | Investigation/referral frames and immutable-history checks |
| Quarantine/history | Existing scoped issue/correction/revalidation flow, source provenance and run reconciliation retained | Quarantine frame and existing recovery browser gates |

The Analyst workflow is **Overview → My Work → Case → Investigation → Decision → History**. Review Queue remains the wider visible case explorer. Role navigation still omits financial work for Maintainer and mutations for Auditor.

## Rules and exact boundaries

- Counters and work-view filters use the complete authorized matching SQL scope before pagination. A table preview is never a chart denominator.
- Due today is the current SAST calendar day, with a half-open midnight interval. It can overlap with Overdue. Work views are not additive.
- Recently completed means current CLEARED/CONFIRMED_RISK cases ordered by recorded decision time. No unapproved recency cutoff or SLA change is introduced.
- Existing SLA targets remain MEDIUM 24 hours, HIGH 4 hours and ESCALATED 2 hours. Administrator reassignment does not restart the referral deadline. No deadline makes an automatic financial decision.
- Analyst can claim an unassigned case for themselves. Administrator assigns/reassigns other Analysts. Auditor is read-only. Maintainer has no financial assignment or decision authority.
- **Refer for Specialist Review** records a requested destination and required investigation reason/notes. `SPECIALIST_REVIEW` is a controlled destination requiring Administrator routing. A named alternative is an active, provisioned, account-scoped Analyst, described as a requested reviewer; this does not assert specialist training or invent a team.
- Referral retains current ownership until an Administrator transfers it. The existing version check, registry lock, SQL row lock and idempotency identity remain in effect. No new migration is needed.
- Additive referral evidence is stored in the existing review-note/history fields. A server-owned envelope binds actor, original request digest and destination. Existing five-field requests remain compatible; JSON-looking legacy notes cannot become trusted metadata. Human copy is projected separately from the preserved technical envelope.
- First authenticated admission determines original submitter, filename, source object version and time. Renamed replay does not transfer provenance or create another ledger entry. Historical receipt-only filenames are explicitly distinguished from verified original admission evidence.
- Missing uploader/channel/history is Not recorded; a system worker does not prove automated intake. Source system is declared by the export. Current role is not invented as historical role-at-action.
- LOW with recorded assessment displays its score and No review required. Known historical seed entries remain unscored. Modern missing evidence remains Not recorded. Risk percentage is rule priority, not fraud probability.
- Trend charts show observed dates. A single date explicitly cannot establish a trend. Processing segments are recorded row outcomes; unknown totals cannot establish completeness.
- Manual CSV remains implemented. Scheduled secure feeds, API/event ingestion, configured reviewer groups and a non-authoritative Investigation Assistant remain roadmap items. An assistant must not score, clear, confirm, refer automatically or alter financial records.

## Research decisions within the brief

| DECISION | SOURCE | WHY IT APPLIES | HOW FINTRUST USES IT |
| --- | --- | --- | --- |
| Work views for ownership and deadlines | [Freshservice: assigned work](https://support.freshservice.com/support/solutions/articles/234432-viewing-tickets-assigned-to-you) | Analysts need their cases and due/overdue work to be obvious | Scoped SQL views, current SAST day and existing risk-review targets; IT service-desk assignment authority is not imported |
| Compact filters and investigation beside the queue | User-supplied Datadog screenshots; [Datadog signal investigation](https://docs.datadoghq.com/security/application_security/threat_protection/security_signals/) | Evidence and next actions belong together | FinTrust navy/teal identity, readable tables and separate evidence/action areas; no copied branding, icons or proprietary layout |
| Validate referral and scope on each request | [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) | Hidden controls cannot establish authorization | Existing live role/account/ownership checks remain; only current scoped owner can request a permitted destination |
| Preserve concurrent mutation controls | [PostgreSQL 16 locking](https://www.postgresql.org/docs/16/explicit-locking.html) | Claim/decision/reassignment must not lose competing changes | Reuse existing registry/row locks, expected version and replay identity; no new concurrency or schema model |

These sources validate implementation within the brief. They do not redefine FinTrust's financial rules. References belong in project evidence, never production UI. Existing edited project PDFs are preserved for the final documentation/SOP consolidation.

## Verification

**981 checks verified, zero unresolved failures/errors/skips.** Nine in-suite browser gates and the separate four-role walkthrough passed. All 24 laptop/mobile frames were visually inspected. One Windows temporary-file replacement failure passed on a fresh-folder retry; all seven setup-module checks passed. The original failure and precise aggregation are retained in `environment-retry.json`. Production source did not change during verification. Source manifest, preservation proof and visual review are recorded alongside this file. The previous reported local baseline was 961 passes. The candidate adds 18 feature checks plus two automatically parameterized endpoint authorization checks: 981 collected.

All scenario work uses disposable loopback PostgreSQL 16.15, synthetic users and mocked AWS transports. Existing local records and credentials are never seeded, reset or re-enrolled by these checks. Screenshots are synthetic acceptance evidence, not final SOP numbering.

**Exact new-source Linux Python 3.12 verification and live AWS E2E remain pending. No push, AWS mutation or deployment is part of this phase.**

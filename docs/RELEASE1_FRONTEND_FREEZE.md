> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# FinTrust Release 1 frontend and user workflows

> Current local presentation behavior (2026-10-11): see [Release 1 presentation readiness](RELEASE1_PRESENTATION_READINESS.md). Its human operating model supersedes earlier local permissions described below: Admin handles governance/oversight, Analyst handles routine review/correction, Auditor reads, Maintainer handles technical recovery. Terminal reopening and unassigned-account correction are not exposed in the current local UI/API. Local user-record governance is now implemented; token provisioning and enterprise authentication remain separate. Historical test counts and frozen cloud artifacts below retain their original source scope.


2026-10-10. Local verification only. AWS inventory remains the prior completed checkpoint; no AWS calls, live migration, endpoint, IAM, trigger, concurrency or deployment changes belong to this phase.

## Pages and authoritative roles

The existing vanilla HTML/CSS/JavaScript frontend remains at `/release1`. Navigation: Overview, Transactions, Risk Events, Review Queue, Quarantine, Ingestion Batches, Rejected Uploads, Notifications, Reports, Accounts, Account History, Audit, Operations and Administration. Transaction Detail, Batch Detail and Quarantine Detail open from their respective records rather than from a meaningless unselected navigation page.

| Role | Monitoring / reports / batches | Review / correction | Upload | Audit | Operations / retries | Administration |
| --- | --- | --- | --- | --- | --- | --- |
| Admin | Assigned-account reads; unresolved unknown-account quarantine | Yes, including controlled reopening | Local admission only | Yes | Yes | Governance metadata; operator-managed identity configuration |
| Risk/Compliance Analyst | Assigned-account reads | Yes; backend assignment/version/transition controls | No, preserving existing contract | Transaction-level review history; no global audit | No | No |
| Read-only/Auditor | Assigned-account reads | No | No | Yes | No | No |
| Maintainer | Technical reconciliation through Operations | No | No | Operational receipts through Operations | Yes, bounded and idempotent | No |

Notifications are accessible to each authenticated role and contain only that session's events. Backend authorization is authoritative. Hiding buttons is not the security boundary. Tokens remain in memory and are cleared on sign-out; no browser token persistence was added.

## Financial facts, risk and workflow

Transactions contain unique accepted ledger entries. Transaction Detail separates immutable facts, actual configured risk rule reasons/points, processing evidence and review history. Individual pipeline-step timestamps are not recorded by the backend; the UI states this and does not fabricate them. High risk remains accepted data, never quarantine. LOW/MEDIUM/HIGH and the existing `>5 accepted transactions in 5 minutes` rule are unchanged. Similar genuine charges preserve both entries; possible duplicate-charge risk remains a rule flag, not an ingestion duplicate.

Filters for transaction/source identity, assigned account, timezone-bearing date range, country, amount range, risk level and batch are applied in parameterized backend queries before pagination. Unsupported, repeated and malformed filters are rejected.

Review lifecycle remains OPEN → UNDER_REVIEW → CLEARED / CONFIRMED_RISK / ESCALATED, with backend notes, resolution, reviewer, immutable history and optimistic version checks. Auditor/Maintainer mutations remain denied. Correction is Correct → Revalidate → Deduplicate → Reprocess. Submission queues the existing worker outbox; the UI does not claim worker completion or directly approve into the ledger.

## Intake history and reconciliation

Bad files are rejected before any batch/row processing. Valid files retain valid rows while bad rows enter quarantine. Existing S3 audit storage now also holds safe local admission receipts under `quarantine/ui-events/<event UUID>.json`, written with `IfNoneMatch=*`. Receipts contain sanitized filename, actor, assigned-account scope, time, result/reason code and batch link; never CSV contents, credentials, raw parser/SQL/AWS errors or bearer tokens. Versioned bucket controls and append-only application behavior remain in place. This is an application receipt, not an S3 Object Lock compliance claim.

Rejected Uploads reads persistent receipts and displays zero rows processed, independently of accepted batches. Admission receipts are recorded only by the already gated local upload adapter. Cloud HTTP admission/history remains separately gated, and no claim of a deployed cloud upload workflow is made. Missing/multiple multipart files currently return an immediate INVALID_FILE_COUNT error; durable rejection receipts cover files that reach file admission. A cloud intake controller must reuse equivalent receipt semantics before cloud upload is enabled.

Batch history adds the filename and actor where the receipt exists; older non-HTTP batches show unavailable metadata rather than invented uploader names. Batch Detail includes every recorded row, paginated tabs for All Rows / Accepted / Quarantined / Duplicates / Failures, parsed/accepted/quarantined/duplicate/failure/pending totals, accounted-for total, hash, receipt clock and whole-file attempt history. Pending publication totals display AWAITING_RECONCILIATION. Inconsistent known totals display RECONCILIATION_FAILED. Neither can display completed.

Duplicate occurrences show source identity/row, canonical match, first acceptance time, occurrence time, SAME_FILE_DUPLICATE / CROSS_FILE_DUPLICATE and `No additional ledger entry created`. Whole-file replay is an attempt on the original batch. Identity conflicts retain their existing quarantine reason; possible double charges retain both transactions and their risk metadata. Duplicate and quarantine views remain separate.

## Overview, notices and operations

Overview uses actual scoped ledger totals, Release 1 accepted-entry count, active reviews, quarantined rows, duplicate occurrences, rejection history, partial/failed batches, real risk distribution, recent accepted transactions and attention queue. Workflow counters cover at most 100 listed batches/cases and display a bounded-count warning when necessary; this is not an unbounded aggregate claim. History pages are independently paginated. Synthetic A/B acceptance creates 36 new entries, 16 quarantine occurrences and 2 duplicates. The overview ledger total is scoped to assigned accounts; it is not the global seeded ledger count.

SUCCESS / INFO / WARNING / ERROR / ACTION_REQUIRED notices have semantic styling. Upload warnings/errors persist on navigation until acknowledged; the Notification Center retains individual session notices and object links. Review/correction/retry outcomes and API/session failures use the same framework. Reconciliation issues create an action-required notice. Session notices intentionally clear on sign-out; durable intake and immutable review/operational histories remain the historical evidence. No claim of cross-session notification acknowledgements or background cloud push delivery is made.

Maintainer sees successful current backend/database reads, source/contract/schema versions, batch technical failures and reconciliation, pending derived work, bounded queue health, alert claims and operational receipts/retries. Unconfigured queue measurements display NOT_CONFIGURED/unavailable. No AWS health metrics are invented locally. Governance endpoints remain operator controlled; administration displays the actual supported contract, not fake user-management controls.

Audit combines safe intake receipts with real scoped ingestion occurrences, correction history and review history. Admin also sees global technical receipts; Maintainer gets operational receipts only. Pagination and a 1,000-record per-SQL-source bound are declared. Configuration/admin events are not invented when no HTTP configuration mutation exists.

## Verification and release boundary

Browser gate uses real isolated PostgreSQL and the actual A/B fixtures, with S3/DynamoDB explicitly mocked and non-loopback browser traffic blocked. It exercises all pages, all four role boundaries, rejection history, A/B partial outcomes, exact A replay, batch tabs and duplicate evidence, safe quarantine detail, High risk, analyst review to CLEARED, correction submission, serious notices, loading/unavailable/empty states and server-side Maintainer mutation denial.

Focused and full regression results, source commit and screenshot manifest are recorded in `docs/EVIDENCE/12-e2e/release1-lifecycle/frontend-freeze-result.json` after the final gates. Screenshots remain in the existing `release1-lifecycle/browser/` evidence folder. No new evidence hierarchy is introduced.

Application/API code and packaged frontend changed. A NEW Linux CPython 3.12 x86_64 release ZIP and CI/import/content/role gates are required before any upload/deployment; the prior verified ZIP remains historical evidence and is not silently relabelled. No rebuild/upload/push is authorized by this frontend phase. Live migration 002/operator/Secrets Manager endpoint approval and deployment prerequisites remain separate from this local frontend freeze.

## Final local verification result

Source commit: `3234ba5139ed354943098ecbb81080802baad9f3`.

- Browser gate: PASSED on this source commit; all four roles, 25 synthetic screenshots, no page errors, no external/AWS transport. A delayed Admin financial response was discarded after Maintainer sign-in; duplicate-tab evidence waits for the filtered response.
- Focused frontend/workflow subset: 55 passed, 0 failed, 0 skipped within the final full run. The 11 new presentation contract tests also passed separately.
- Full local regression: 603 passed, 0 failed, 1 expected skip, 0 unexpected skips. The skipped test is `tests.data_quality.test_processing.test_database_roles_can_execute_pipeline_without_owner_privileges`: it requires a disposable database administrator, while this local test identity is deliberately not an administrator. This is not a claim of a newly executed PG16 administrator role proof; that remains part of the new Linux/CI release gate.
- Backend/test sources in the full run match this source commit; final frontend browser verification ran after the last JavaScript change.
- Detailed results and sanitized JUnit/output: `EVIDENCE/12-e2e/release1-lifecycle/frontend-freeze-result.json` and `frontend-freeze-{full-regression,focused,browser}.{xml,txt}`.
- Visual inspection: overview, batch reconciliation, possible duplicate-charge comparison and Maintainer operations reviewed. Presentation screenshots include upload warnings/replay, rejection history, duplicate occurrences, quarantine detail/resubmission, High risk, review to CLEARED, notifications, audit, Auditor and API-unavailable states.
- No frontend blockers remain for this local freeze. A new Linux package and separate deployment/security approvals remain required; this result is not authorization to mutate AWS.

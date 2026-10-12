# FinTrust local end-to-end scenario verification

Baseline: `3c14fb170b19c71b7b0924bee541064b139d1075` plus the focused tests named in the evidence. No AWS changes or push.

These scenarios combine real PostgreSQL integration assertions with authenticated UI API checks and four browser gates. Individual UI evidence is labeled below; shared browser coverage is not presented as an individual browser replay.

## 1. Normal LOW-risk transaction

**INPUT:** 10 ZAR, ZA, unique source reference

**EXPECTED FLOW:** Accept and score LOW; retain ledger without review

**DATABASE RESULT:** One immutable ledger entry, Low, NOT_REQUIRED

**UI RESULT:** Transactions/lifecycle API returns STORED and Low

**AUDIT RESULT:** System lifecycle records source, actor and timestamps

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_transaction_lifecycle::test_accepted_levels_stored_and_timeline_is_authoritative[10-ZA-Low-NOT_REQUIRED]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 2. MEDIUM-risk transaction

**INPUT:** 200000.01 ZAR, ZA

**EXPECTED FLOW:** Accept, score MEDIUM, open review

**DATABASE RESULT:** Ledger retained, Medium, OPEN

**UI RESULT:** Transaction lifecycle API returns Medium and OPEN

**AUDIT RESULT:** Frozen scoring evidence and ordered lifecycle

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_transaction_lifecycle::test_accepted_levels_stored_and_timeline_is_authoritative[200000.01-ZA-Medium-OPEN]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 3. HIGH_AMOUNT

**INPUT:** 50000.01 ZAR

**EXPECTED FLOW:** Trigger HIGH_AMOUNT; risk level remains combined score outcome

**DATABASE RESULT:** Frozen rule measurement and threshold; ledger retained

**UI RESULT:** Risk Event detail API exposes amount and threshold

**AUDIT RESULT:** Rule created_at and immutable source evidence

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_risk_investigation::test_signals_have_frozen_measurement_and_timestamp[values0-HIGH_AMOUNT]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`), `tests.test_risk_investigation::test_signals_have_frozen_measurement_and_timestamp[values1-CROSS_BORDER]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 4. HIGH_VELOCITY

**INPUT:** Six distinct accepted transactions in closed 300-second window

**EXPECTED FLOW:** First five do not trigger; sixth triggers; test boundary timing

**DATABASE RESULT:** HIGH_VELOCITY measured 6, threshold 5

**UI RESULT:** Risk detail evidence supplies measured count and threshold

**AUDIT RESULT:** Frozen signals identify actual transactions/time window

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_release1_end_to_end::test_velocity_closed_five_minute_time_boundary[300-True]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`), `tests.test_release1_end_to_end::test_velocity_closed_five_minute_time_boundary[300.000001-False]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 5. CROSS_BORDER

**INPUT:** Country US, valid amount/reference

**EXPECTED FLOW:** Accept foreign-country transaction and retain signal; not invalid data

**DATABASE RESULT:** CROSS_BORDER signal with frozen measurement

**UI RESULT:** Risk detail API exposes location, context and threshold

**AUDIT RESULT:** Signal created_at is present

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_risk_investigation::test_signals_have_frozen_measurement_and_timestamp[values0-HIGH_AMOUNT]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`), `tests.test_risk_investigation::test_signals_have_frozen_measurement_and_timestamp[values1-CROSS_BORDER]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 6. POSSIBLE_DUPLICATE_CHARGE

**INPUT:** Two unique references, same 123 ZAR merchant within 30 seconds

**EXPECTED FLOW:** Keep both genuine identities; flag similarity within 120 seconds

**DATABASE RESULT:** Rule records matching transaction IDs, threshold 120

**UI RESULT:** Risk detail uses frozen rule evidence

**AUDIT RESULT:** Source references and separate identities remain traceable

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_risk_investigation::test_velocity_closed_window_and_duplicate_charge_evidence` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 7. Invalid transaction to quarantine

**INPUT:** Amount bad

**EXPECTED FLOW:** Reject row from ledger; quarantine safe original

**DATABASE RESULT:** Original occurrence remains QUARANTINED

**UI RESULT:** Quarantine detail/API retains validation issue and source

**AUDIT RESULT:** RECEIVED, QUEUED, QUARANTINED system events

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_transaction_lifecycle::test_quarantine_correction_revalidates_new_occurrence_without_overwrite` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 8. Correct quarantine, revalidate, accepted

**INPUT:** Analyst submits numeric amount with reason

**EXPECTED FLOW:** Create correction occurrence; worker revalidates and scores

**DATABASE RESULT:** New occurrence STORED; original QUARANTINED; one ledger addition

**UI RESULT:** Quarantine recovery API links resulting transaction and attempts

**AUDIT RESULT:** Human CORRECTED plus system REVALIDATED; original history preserved

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_multi_user_operations::test_correction_failed_then_valid_or_duplicate_with_link_and_immutable_history[False]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`), `tests.test_multi_user_operations::test_correction_failed_then_valid_or_duplicate_with_link_and_immutable_history[True]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 9. HIGH, Risk Event, Alert, Review Queue

**INPUT:** 200000.01 ZAR, US; mocked successful mail provider

**EXPECTED FLOW:** Keep HIGH ledger, open review, send idempotent alert

**DATABASE RESULT:** SENT independently of OPEN review; one canonical ledger entry

**UI RESULT:** Investigation detail API shows SENT; queue remains OPEN

**AUDIT RESULT:** ALERTED only after durable SENT evidence

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_risk_investigation::test_successful_alert_remains_independent_of_review` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 10. Analyst claims review

**INPUT:** Active Analyst claims unassigned HIGH review

**EXPECTED FLOW:** OPEN to UNDER_REVIEW with single owner

**DATABASE RESULT:** Reviewer set; stale/wrong owner rejected

**UI RESULT:** Browser Claim Review reveals owned investigation actions

**AUDIT RESULT:** Assignment history attributes analyst01

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_multi_user_operations::test_claim_wrong_owner_complete_and_audit` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 11. Analyst clears review

**INPUT:** Owner selects Clear and supplies notes

**EXPECTED FLOW:** UNDER_REVIEW to CLEARED

**DATABASE RESULT:** CLEARED; ledger retained and identity unchanged

**UI RESULT:** Browser investigation drawer shows CLEARED

**AUDIT RESULT:** Owner and reviewed_at recorded; append-only history

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_scenario_outcomes::test_three_review_outcomes_browser_database_and_audit` (run `7796a569eb4a48f18b897ffb25a6ca7d`)

## 12. Analyst confirms risk

**INPUT:** Owner selects Confirm Risk and supplies notes

**EXPECTED FLOW:** UNDER_REVIEW to CONFIRMED_RISK

**DATABASE RESULT:** CONFIRMED_RISK; ledger retained

**UI RESULT:** Browser drawer shows CONFIRMED_RISK

**AUDIT RESULT:** Owner and timestamp recorded; prior history preserved

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_scenario_outcomes::test_three_review_outcomes_browser_database_and_audit` (run `7796a569eb4a48f18b897ffb25a6ca7d`)

## 13. Analyst escalates review

**INPUT:** Owner selects Escalate and supplies notes

**EXPECTED FLOW:** UNDER_REVIEW to ESCALATED

**DATABASE RESULT:** ESCALATED; ledger retained

**UI RESULT:** Browser drawer shows ESCALATED

**AUDIT RESULT:** Owner and timestamp recorded; escalation remains explicit

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_scenario_outcomes::test_three_review_outcomes_browser_database_and_audit` (run `7796a569eb4a48f18b897ffb25a6ca7d`)

## 14. Two Analysts claim same review

**INPUT:** Two simultaneous claim requests

**EXPECTED FLOW:** One succeeds, one conflicts; no second owner

**DATABASE RESULT:** HTTP 200/409 and exactly two review-history rows

**UI RESULT:** API conflict protects UI; wrong-owner browser is read-only

**AUDIT RESULT:** One authoritative owner change; no competing successful claim

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_multi_user_operations::test_two_simultaneous_claims_have_one_owner` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 15. Auditor mutation denied

**INPUT:** Auditor submits financial note/mutation

**EXPECTED FLOW:** Reject server-side regardless of UI

**DATABASE RESULT:** 403; no financial authority granted

**UI RESULT:** Auditor browser has no decision controls

**AUDIT RESULT:** Denied action is not a successful business event; API request status recorded

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_risk_investigation::test_no_nonanalyst_notes[admin01]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`), `tests.test_risk_investigation::test_no_nonanalyst_notes[auditor01]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`), `tests.test_risk_investigation::test_no_nonanalyst_notes[maintainer01]` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 16. Admin creates, disables, reactivates user

**INPUT:** Named local record with role/status and mandatory reason

**EXPECTED FLOW:** Create without credential; disable blocks sign-in; reactivate preserves identity

**DATABASE RESULT:** User registry governs access; not a SQL financial user table

**UI RESULT:** Admin browser creates/manages user; disabled session returns 401

**AUDIT RESULT:** USER_CREATED/USER_DISABLED governance receipts and actor

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_multi_user_operations::test_disable_reactivate_and_role_change_preserve_identity_and_audit` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 17. Admin reassigns to/from Maintainer

**INPUT:** Admin changes analyst02 to Maintainer then restores Analyst

**EXPECTED FLOW:** Identity remains stable; Maintainer cannot assign reviews or manage users

**DATABASE RESULT:** Stable user ID; Maintainer financial/admin requests return 403

**UI RESULT:** Session API immediately reflects new role; UI roles independently browser-tested

**AUDIT RESULT:** USER_ROLE_CHANGED summary plus before/after versioned governance receipt

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_scenario_outcomes::test_admin_reassigns_maintainer_role_without_inheriting_financial_authority` (run `7796a569eb4a48f18b897ffb25a6ca7d`)

## 18. Alert failure without transaction rollback

**INPUT:** Mocked SES rejection then ambiguous response

**EXPECTED FLOW:** FAILED, retry, UNKNOWN reconciliation; retain ledger/review

**DATABASE RESULT:** Exactly one transaction; review OPEN despite mail failure

**UI RESULT:** Investigation API returns FAILED/UNKNOWN and reconciliation_required

**AUDIT RESULT:** Delivery evidence remains separate; do not fabricate ALERTED

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_risk_investigation::test_alert_failed_retry_unknown_do_not_change_ledger_or_review` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 19. Technical failure and retry

**INPUT:** Inject projection failure after SQL commit, then restore publisher

**EXPECTED FLOW:** STORED, TECHNICAL_FAILURE, RETRY, RECOVERED; replay idempotent

**DATABASE RESULT:** One ledger addition; eight lifecycle events, no duplicated acceptance

**UI RESULT:** Lifecycle API/shared timeline render; failure branch checked in SQL, not a live AWS DLQ

**AUDIT RESULT:** Sanitized error type, system actor, retained retry/recovery history

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_transaction_lifecycle::test_technical_failure_retry_recovery_preserves_committed_ledger` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## 20. Report generation and visibility

**INPUT:** Authorized account transactions plus another account; page limits

**EXPECTED FLOW:** Aggregate authorized data; export current page CSV/JSON

**DATABASE RESULT:** Account-scoped report rows, valid pagination, no mixed-batch scope leak

**UI RESULT:** Browser downloads checked row-for-row against Reports API

**AUDIT RESULT:** Report read/export is not a financial mutation; existing lifecycle remains intact

**ACTUAL RESULT:** Named assertions passed in current local run; evidence scope below applies

**PASS / FAIL:** PASS

Test evidence: `tests.test_release1_end_to_end::test_report_pagination_and_no_mixed_batch_scope_leak` (run `ed1f7c8078a14bca84d4413e4a3d46c3`)

## Boundaries and presentation use

- Real isolated loopback PostgreSQL; S3/SQS/DynamoDB/SES are mocked. This is not live AWS E2E.
- UI RESULT explicitly identifies browser versus backend API evidence. Not every failure injection is separately replayed through a browser.
- Local user governance is a hashed-token registry with versioned audit receipts, not production federation.
- Reports exports cover the authorized current page; they are not complete ledger archives.
- Read/export and rejected mutations do not fabricate business audit transitions.
- Release 1 velocity remains >5 accepted transactions in the closed 300-second window.
- No new UI, backend, schema, AWS or business-rule changes were required.

Run the named tests through `tools/run_release1_tests.py` in the project environment. The disposable schema is cleaned afterward; evidence captures outcomes, not a persistent demo dataset. Use CSV A/B via the existing browser gate for the visible upload/reconciliation presentation.

Next: AWS Budgets review, exact-source Linux verification, separately approved AWS deployment/wiring and live E2E. AI remains planned.

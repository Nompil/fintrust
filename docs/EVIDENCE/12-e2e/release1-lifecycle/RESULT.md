# Release 1 dataset and ingestion lifecycle: VERIFIED

**Bad file: reject the file. Bad row in a good file: quarantine the row. Good row: continue processing.**

1. New files: `fintrust_release1_transactions_A.csv` and `fintrust_release1_transactions_B.csv` under tests/fixtures/e2e/release1. Original bytes and hashes remain unchanged.
2. SHA256 A: `02e72ce290842bed2b03088daec5bfc87a18f17fd858c6128d205714765c829e`; B: `c71d9a6862eed230cf4e0c72c961bbede3b5f36b4d8c3f3374532a1f1194f386`. Exact derivation is in MAPPING.md; all original rows are retained, with explicitly labelled additional coverage.
3. Rows: A 42; B 12.
4. Malformed CSV, wrong headers, empty file, binary renamed CSV and unsupported type: rejected before any row/batch/ledger/quarantine work. Original incompatible schemas remain intentionally rejected legacy evidence.
5. Row quarantine: A 12; B 4. Includes missing/unknown account, invalid/zero/negative amount, malformed/future/missing timestamp, invalid currency/country, missing upstream identity and identity conflict.
6. Valid-row continuation: A 29 and B 7 accepted despite invalid rows; all 54 expected-versus-actual outcomes matched. High-risk appended after invalid rows was still accepted.
7. Accepted risk outcomes: Low 30, Medium 4, High 2. Every accepted row has frozen risk metadata; six OPEN review entries before browser action. Only High qualifies for the actual alert consumer: two mocked sends, including stream replay and explicit repeated delivery, with no extra sends. No risk classification caused data quarantine.
8. Duplicates: one within A, one cross-file B, exact whole-file A replay adds no ledger/quarantine/review/alerts.
9. Materially changed TX-E2E-005 under the same trusted identity: DUPLICATE_IDENTITY_CONFLICT quarantine, not a benign duplicate.
10. Similar distinct TX-DOUBLE-001/002 and TX-E2E-005/TX-B-SIMILAR-001 remain separate ledger entries. The later rows gain POSSIBLE_DUPLICATE_CHARGE (Medium 40 and High 70 respectively).
11. Reconciliation: A 42 = 29 accepted + 12 quarantined + 1 duplicate + 0 technical failed. B 12 = 7 + 4 + 1 + 0. Pending 0, counts consistent, COMPLETED. Inconsistent/pending outcomes never produce a success notification; existing full regression verifies reconciliation status guards.
12. Notifications: safe rejected-file, successful-batch, warning-count and replay messages. Unacknowledged outcomes survive navigation and subsequent uploads, with explicit acknowledgement; sign-out clears the private session notice. No parser/SQL/AWS exception text is exposed.
13. Focused fixture/original-admission tests: 19 passed, zero failed/skipped. Final browser test: one passed. Local full run collected before the additional success-notification case: 588 passed, one expected administrator-only skip, zero failed; the final focused test covers the additional case.
14. Final Linux full suite: 590 passed, zero failed/errors/skipped, CPython 3.12.15 Linux x86_64, PostgreSQL 16 service roles verified.
15. Browser: PASS. Actual backend A/B/replay upload, rejected file, persistent/acknowledged notices, ledger/risk/quarantine/review/batch views, exact score-70 review transition, Auditor mutation restrictions, Maintainer technical scope and zero page errors. Local screenshots under browser; final CI screenshots under ci-browser. No hard-coded frontend financial results.
16. Verified source: `12b0c94844b6ff1a6389beb99e1f87a51fedb598`. Local implementation milestones: e3009ab, 7649919, 12b0c94. Initial CI selector mismatch was a test harness issue; it was corrected without altering risk logic.
17. CI: https://github.com/Nompil/fintrust/actions/runs/38066413745 (run 38066413745); all release gates passed. New source-bound artifact: `C:\Users\Nompilo\Desktop\fintrust\build\release1-ci\38066413745\release\build\release1-candidate\fintrust-release1-linux-py312.zip`. SHA256 `0ad342f40447751bf105e88d2ac1d473f6423394c1e01b3b4b921287a5d84b45`; base64 `CtNC9ARHdRvxBeiNKsHUc/ZCM5TB4Bs7S5ISh6XYS0U=`; 21404920 bytes. All five handlers and production/native imports passed. Download checksum and changed application/frontend UTF-8 source comparisons passed. Older verified archives remain preserved.
18. Remaining ingestion blockers: none. AWS/RDS read-only preflight, live migration, deployment, cloud authentication/operations paths and activation remain later controlled gates; no live readiness/deployment claim is made here. AWS Integration remains In Progress.

No AWS calls, secret retrieval, live DB access, artifact upload, migration, infrastructure mutation, concurrency activation or trigger wiring occurred.

FINTRUST RELEASE 1 DATASET AND INGESTION LIFECYCLE VERIFIED — READY FOR READ-ONLY AWS PREFLIGHT

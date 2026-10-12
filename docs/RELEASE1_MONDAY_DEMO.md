> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Monday local demonstration

> Current local presentation behavior (2026-10-11): see [Release 1 presentation readiness](RELEASE1_PRESENTATION_READINESS.md). Its human operating model supersedes earlier local permissions described below: Admin handles governance/oversight, Analyst handles routine review/correction, Auditor reads, Maintainer handles technical recovery. Terminal reopening and unassigned-account correction are not exposed in the current local UI/API. Local user-record governance is now implemented; token provisioning and enterprise authentication remain separate. Historical test counts and frozen cloud artifacts below retain their original source scope.


Run from the existing repository in PowerShell:

```powershell
& 'C:\Users\Nompilo\AppData\Local\Programs\Python\Python314\python.exe' tools/serve_release1_demo.py --role Admin --seed-scenarios
```

Use the already configured dedicated loopback test database. Enter a private random token of at least 32 characters at the hidden prompt, then open http://127.0.0.1:5001/release1 and sign in with that same token. The registry stores only its hash; do not capture the token in screenshots. Role selection is operator-controlled at launch, not a browser privilege switch.

1. Dashboard: show assigned-account totals. Explain seeded synthetic baseline plus explicitly constructed new scenarios; these are not imported CSV A/B.
2. Ingestion Batches: newest constructed batch has three rows: one normal, one risky, one invalid. Show received = accepted + quarantined + duplicate + technical-failed + pending.
3. Transactions: open the new ZAR 10 domestic transaction. Show frozen Low risk, source identity and audit detail.
4. Open the ZAR 200,000.01 US transaction. Explain HIGH_AMOUNT plus CROSS_BORDER and frozen combined score. Release1 HIGH_VELOCITY remains >5 accepted transactions in the closed 5-minute window; 10/11/12 per hour is deferred.
5. Review Queue: Open action, enter investigation notes, submit UNDER_REVIEW; refresh and resolve with CLEARED, CONFIRMED_RISK or ESCALATED and required resolution code. No financial facts are edited.
6. Quarantine: open the invalid amount record; show INVALID_AMOUNT and version-pinned safe candidate. Correct amount to a positive two-decimal value and RESUBMIT with notes. The local correction worker processes it asynchronously, validates and deduplicates again. Original evidence and correction history remain separate.
7. Reopen batches/reports/transaction details to show reconciliation and account/currency net movement from zero. Reporting does not claim bank balances or FX conversion.
8. Admin/Audit: show append-only review transitions with server-authenticated actor, version and request ID.
9. Stop with Ctrl+C, then launch `tools/serve_release1_demo.py --role Auditor` without reseeding, using a different private token. Open the same URL, sign in, show review history and absence of mutation buttons. Prior SQL audit survives. Mock payload/projection objects are session-local, so do not reopen old quarantine payloads as durable S3 evidence.
10. Cite the local browser evidence and PostgreSQL16 CI evidence from RELEASE1_PRESENTATION_STATUS.md. State AWS integration is still In Progress and live001/002 migration/new runtime activation remain unapproved.

The demo executes real validation, SQL persistence, scoring, correction and review code against dedicated local PostgreSQL. S3/DynamoDB are explicitly in-process mocks with unmocked AWS transport blocked. The service binds only 127.0.0.1. It is not an AWS deployment, production identity provider or durable cloud acceptance test. Existing mock evidence ends on process exit; do not discard SQL audit to hide that limitation.

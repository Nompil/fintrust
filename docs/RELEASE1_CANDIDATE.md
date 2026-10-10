# FinTrust Release1 candidate checkpoint

Continues verified source4d91c3d and evidence423f198. No settled network, RDS or risk decisions were reopened. This phase adds authoritative CSV-only upload, durable technical-operations receipts, Maintainer restrictions, bounded FIFO redrive/projection/correction retry, explicit alert PENDING/RETRYING and the compact vanilla frontend. Original historical ZIP remains untouched; new package is separately named `fintrust-release1-linux-py312.zip`.

## Actual external fixtures

Actual CSV A/B bytes have not been supplied. No paths, hashes, imported rows or expected outcomes are invented. Import only operator-supplied originals:

```powershell
python tools/import_release1_fixtures.py '<actual CSV A path>' '<actual CSV B path>'
```

Copies go to tests/fixtures/e2e unchanged. Admission inspection and SHA256 are recorded; a schema mismatch produces BLOCKED, never silent rewriting. Per-row expected outcomes require a reviewed fixed receipt clock, account baseline and sequential A then B processing; corrections must be separate files with original hashes retained. The current constructed tests prove named scenarios, not unseen CSV A/B. This remains a release acceptance blocker.

## File admission

The new local candidate upload is enabled only with FINTRUST_RELEASE1_UPLOAD=1 and FINTRUST_MODE=local. Admin-only, one multipart file per batch, .csv filename, maximum1MiB,5000 rows,32768-byte row. UTF8/BOM supported; controls/binary, malformed quoting, missing/duplicate/extra headers and empty/header-only files are rejected before S3/row work. MIME is advisory: text/csv,application/csv,text/plain,octet-stream and the Windows CSV label application/vnd.ms-excel are allowed only with valid text/schema. Renamed PDF/JSON/ZIP/executable/image fail content/schema admission. Legacy teaching upload retains its four-column schema only in its explicit legacy mode.

Release1 upload executes strict SQL worker locally and returns durable reconciliation, never queued-as-accepted. Cloud upload remains S3 versioned intake -> FIFO -> private worker; synchronous HTTP SQL ingestion is refused outside local mode.

## Technical operations

Maintainer can view operational/schema/release health and bounded delivery claims, and request audited retries. Backend rejects financial/review/quarantine/admin APIs for this role. Projection/correction retries queue existing worker-owned work; they cannot insert financial facts via HTTP DB privileges. Receipt UUID/digest/actor and terminal result are immutable. Replays return the receipt, modified payloads409. Failed/running receipts require investigation, not blind resubmission. Redrive validates exact account/region/source/DLQ ARNs and RedrivePolicy, receives1–10 messages, sends preserved body before delete, uses a new SQS delivery token and durable SQL idempotency. It does not purge queues or change compliance decisions.

Cloud redrive is deliberately disabled pending a reviewed external operations controller: the private API has no NAT/SQS endpoint. The proposed controller policy is offline, unattached and unvalidated against AWS Access Analyzer. No NAT/interface endpoint is silently added. Failed-alert claims are visible; SENDING/RETRYING/UNKNOWN are never automatically reclaimed. Definite SES rejection alone permits FAILED -> RETRYING -> SENT; ledger commit is independent.

## Launch and persistence

```powershell
python tools/serve_release1.py --role Admin --seed-scenarios
```

Open http://127.0.0.1:5001/release1 and use the privately entered token. Use --role Analyst,Auditor,Maintainer with distinct tokens for later sessions. Operator assigns role/accounts; no client-side role escalation. Source/version and migration hashes appear in Operations. A new isolated labelled `fintrust_release1_candidate` schema avoids rewriting the previous002 checksum or discarding old demonstration audit. S3/DynamoDB are explicitly session-local mocks; SQL persists. No cloud durability/authentication claim is made.

Required pages use real APIs: Dashboard,Transactions,Detail,Risk Events,Review Queue,Quarantine,Batches,Reports,Accounts,Audit,Operations,Administration. Administration truthfully exposes identity mechanism/status; HTTP user/role management and enterprise federation are designed, not implemented. No fake statistics or fake compliance decisions are used.

## Release gates

Risk freeze retained: HIGH_AMOUNT amount>50000, velocity>5 accepted transactions in a closed300-second window, cross-border country!=ZA, distinct similar charges remain separate facts. Risk is not a fraud verdict. SQL remains authoritative, projection outbox repairs partial success, correction outbox revalidates/deduplicates/scores, unknown financial operations remain deferred. Pending rows participate in reconciliation; an inconsistent count cannot be COMPLETED.

Revised002 has not been applied to live RDS. Source/catalog/privilege checks and PG16 service tests must pass for this exact revision. The existing cloud runner handles001 only. Live002 requires a separately prepared and verified runner/administrator path; do not invoke the001 runner with002. Local/CI candidate verification does not close that live deployment gate.

Final CI, artifact hashes/size, browser and remaining blockers are recorded in the candidate evidence report after the run. No AWS mutations are authorized in this phase.

Known-account upload authorization is enforced before storage: even Admin uploads must stay within assigned accounts. Unknown/malformed account rows still follow validation/quarantine.

## Final exact-source verification

Source d648dd0a77b6906daa94ec7ade7b2ff3e3158ed0, CI38058750009:571 passed,0 failed,0 skipped on Linux3.12.15 / PostgreSQL16.15. Browser and service-role gates passed. NewZIP981417e236116992e5d9e7d9208a6610815044bd870bde0ddee4fe12afa76fac is verified; historical ZIP untouched. Full hashes, size, dependency inventory, evidence and capability truth matrix: docs/EVIDENCE/12-e2e/release1-candidate/RESULT.md. ActualCSV A/B and cloud deployment gates remain blocked as documented.

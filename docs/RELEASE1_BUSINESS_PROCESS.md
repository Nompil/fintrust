> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# FinTrust Release 1 process and schema contract

> Current local presentation behavior (2026-10-11): see [Release 1 presentation readiness](RELEASE1_PRESENTATION_READINESS.md). Its human operating model supersedes earlier local permissions described below: Admin handles governance/oversight, Analyst handles routine review/correction, Auditor reads, Maintainer handles technical recovery. Terminal reopening and unassigned-account correction are not exposed in the current local UI/API. Local user-record governance is now implemented; token provisioning and enterprise authentication remain separate. Historical test counts and frozen cloud artifacts below retain their original source scope.


Prepared 2026-10-09 from checkpoint 49f919a and the user's Release 1 decisions.
Status: **LOCAL RELEASE 1 IMPLEMENTATION; NOT APPROVAL FOR LIVE MIGRATION OR DEPLOYMENT**.
The user approved minimal working analyst review and manual quarantine correction
as release scope; refunds, reversals and chargebacks are deferred. Migration 001
stays identity/idempotency-only. The workflows now have local backend/UI implementations and synthetic acceptance tests;
PostgreSQL 16.15/service-role and exact new-source Linux CPython 3.12.15 verification passed in CI run 38050661063.

## Process and transaction meaning

FinTrust records and monitors imported synthetic transactions. It does not debit
accounts, settle transfers or enforce a payment hold. The existing approve/hold
result is a review recommendation and must be labelled that way. Account balances
are not updated by import; reports show net movement from zero per currency.

| Flow | Release 1 sequence |
|---|---|
| Normal valid transaction | RECEIVED -> VALIDATED -> DEDUPLICATED -> QUEUED -> atomic ledger/risk/frozen-result commit -> HISTORY/REPORTING |
| Suspicious valid transaction | Same acceptance path; immutable risk event -> Medium/High review case; High automatic decision also creates one logical alert condition |
| Invalid row | RECEIVED -> validation or account/identity failure -> immutable QUARANTINE evidence -> manual CORRECTION or REJECTION; correction -> full REVALIDATION -> DEDUPE -> REPROCESS |
| Duplicate row/event | Record occurrence or retry receipt; resolve canonical identity; reuse frozen result; never add another financial entry merely because delivery repeated |

SQL ledger, risk event and processed result commit together. SCORED and STORED
are not independently advertised durable successes. Review creation/projection and
alert delivery may finish afterward. An alert failure does not undo an accepted
transaction. A missing downstream projection remains an operational backlog.
Low needs no review; Medium/High opens a review per risk event. Manual events remain
separate from the single automatic frozen decision; this release does not send
additional notifications for manual scores or analyst state changes.

## Identity and duplicate contract

Internal tx_id is immutable UUID. Normal feed requires nonblank source_system and
source_transaction_id (source_reference alias accepted if it agrees). Namespace
and reference are case sensitive and trimmed; limits 100/200 characters. Identity
is (source_system, account_id, reference). A supplied internal UUID is optional;
if supplied it must be valid and cannot identify a different accepted transaction.
Absent internal UUID with valid upstream identity is not an invalid transaction.
Missing both upstream identity and internal identifier is not admitted by the
strict release feed. Historical/no-reference files remain a separately labelled
legacy compatibility path, not the normal Release 1 contract.

Fingerprint version2 compares normalized financial content after identity match;
file, batch and internal UUID are excluded. It is not a global uniqueness key.
Batch identifies original bytes plus bucket; attempts identify upload/retry
occurrences with exact file/version/ETag. CSV source_row is record ordinal starting
at 2, not physical line number. Historical null identity data is not fabricated.

| Duplicate type | Release disposition |
|---|---|
| Same identity and equal content repeated in a file | First eligible row proceeds; later occurrence DUPLICATE_ROW_IN_FILE |
| Same source reference/account/system across files | DUPLICATE_TRANSACTION linked to canonical ledger result |
| Changed financial content under accepted identity | DUPLICATE_IDENTITY_CONFLICT, quarantined; no overwrite |
| Byte-identical completed file reuploaded in same bucket | New DUPLICATE_FILE attempt, original batch unchanged; no republish |
| Partial publication or worker/queue retry | Same occurrence/request identity, replay frozen result and external effects; not another row in business counters |
| Similar distinct references | Both retained; potential double-charge review signal, not duplicate-data deletion |

In-file duplicate may initially link to the first occurrence rather than a
canonical tx_id not committed yet. At reconciliation retain that link/receipt in
S3; never manufacture accepted money from an unknown-account first occurrence.
A correction preserves source identity; if it matches accepted content, resolve as
duplicate. If it differs under that accepted identity, quarantine conflict again.

## Validation contract

Normal feed requires account_id, amount, tx_date, tx_type, currency, country and
stable source identity. Do not silently default currency/country/timezone in this
strict profile. UTF-8 CSV has one unique header, named text fields, at most 1 MiB
and 5,000 records. Optional merchant is at most200 characters. Unknown extra named
fields stay in original source only; they are not copied into safe quarantine.

| Failure | Code / exact behaviour |
|---|---|
| Missing required value | MISSING_REQUIRED_FIELD; retain field name |
| Bad account UUID / unknown account | INVALID_ACCOUNT_ID / UNKNOWN_ACCOUNT; existence checked by authoritative scorer under account lock |
| Non-numeric/nonfinite amount | INVALID_AMOUNT |
| Zero / negative | ZERO_AMOUNT / NEGATIVE_AMOUNT; amounts always positive; type supplies direction |
| At least 10^13 / more than two decimals | AMOUNT_OUT_OF_RANGE / AMOUNT_PRECISION |
| refund, reversal, chargeback | UNSUPPORTED_FINANCIAL_OPERATION; no substitution with credit |
| Other unknown type | INVALID_TRANSACTION_TYPE; allowed debit, credit, outgoing transfer, fee |
| Bad/timezone-free/date-only timestamp or >6 fractional digits | INVALID_TIMESTAMP; strict ISO timestamp with timezone, normalized UTC |
| More than five minutes after first receipt | FUTURE_TIMESTAMP; <=300 seconds allowed, >300 rejected |
| Bad country syntax | INVALID_COUNTRY |
| Country outside supported demo set | UNSUPPORTED_COUNTRY; ZA, US, GB, KE, DE, FR only in this proposed bounded contract |
| Currency outside supported set | UNSUPPORTED_CURRENCY; ZAR, USD, EUR, GBP, KES |
| Missing/oversize source identity or disagreeing aliases | MISSING_SOURCE_IDENTITY / INVALID_SOURCE_IDENTITY / DUPLICATE_IDENTITY_CONFLICT |
| Supplied invalid internal UUID | INVALID_TRANSACTION_ID |
| Unlabelled extra CSV value/nontext contract field | MALFORMED_ROW |

The country set is an explicit supported demo subset, not a fabricated all-country
ISO database. Expansion requires a pinned reviewed reference list. Currency values
are never added across currencies; risk thresholds remain nominal in each currency
for the teaching model, not FX-adjusted equivalence. Five-minute future tolerance,
strict feed profile and demo country set are selected for this review; they need
acceptance with the overall contract before production integration.

First-receipt timestamp is immutable per batch. Retry/reupload does not move that
clock to make a previously future record valid. A manual correction has a new,
linked submission and receipt clock. Rejecting explicit financial-operation types
cannot detect a refund disguised upstream as a plain credit; that is a feed-contract
limitation. No auto-created accounts, account freeze or KYC mutation.

Every row failure has reason code/detail, available identity, batch, exact source
file/version and record number, safe allowlisted payload/version reference and
quarantine timestamp. All errors are available in validation_errors; existing
production validator returns only its first error and generic codes in some paths.
File failures without readable bytes/hash get a FAILED upload attempt with source
pointer; no fabricated batch hash or row count. If parsing count is unknown it stays
unknown. Dependency outages are technical errors, not invalid financial records.

## Explainable risk model

| Rule | Boundary | Points |
|---|---|---:|
| HIGH_AMOUNT | amount >50,000, not equality | 30 |
| VERY_HIGH_AMOUNT | amount >200,000, additive to HIGH_AMOUNT | 25 |
| HIGH_VELOCITY | >5 accepted records, current included, closed preceding300 seconds, same account | 30 |
| CROSS_BORDER | transaction country other than ZA | 15 |
| POSSIBLE_DUPLICATE_CHARGE | distinct nonnull refs in same source/account, matching debit/merchant/amount/currency in inclusive +/-120 seconds | 40 |
| TRANSFER | outgoing transfer | 20 |
| MERCHANT_MARKER | case-insensitive highrisk synthetic merchant marker | 20 |

Sum capped100; Low0-39, Medium40-69, High70-100. Cross-border alone scores15 Low:
international activity does not mean fraud. High amount alone scores30 Low; very
high alone55 Medium. Explain triggered reasons/points and matching charge IDs.
At most20 match IDs; both real charges survive. Closed windows use event time;
all accepted types/currencies currently contribute to account velocity. Frozen
results never retroactively change with late arrivals or changed configuration.

Twelve transactions spread five minutes apart over55 minutes do not exceed the
five-minute threshold (max2 in a closed window). Six clustered within300 seconds
do. There is no implemented 11/hour rule; adding one is a business-model change.
Keep the current rule rather than relabel the hour scenario as a guaranteed flag.

Release rule version: fintrust-r1-2026-10-09. Production integration must persist
that version and evaluated config with frozen result JSON before claiming this
contract is deployed. Current result already retains config/reasons; no new score
column on transactions is necessary. Historic unscored rows are UNASSESSED.

## Analyst review, roles and audit

Risk level, data disposition, analyst review state and notification delivery state
are independent. A transaction can be ACCEPTED, High and UNDER_REVIEW.
CLEARED does not erase its original risk score or change the financial record.

| Transition | Requirements |
|---|---|
| OPEN -> UNDER_REVIEW | authenticated assignee, actor, note, expected version |
| UNDER_REVIEW -> CLEARED | resolution VALID_ACTIVITY, actor/time/note |
| UNDER_REVIEW -> CONFIRMED_RISK | resolution CONFIRMED_SUSPICIOUS, actor/time/note |
| UNDER_REVIEW -> ESCALATED | resolution SPECIALIST_REVIEW, actor/time/note |
| ESCALATED -> UNDER_REVIEW | acknowledged reassignment/note |
| CLEARED/CONFIRMED_RISK -> UNDER_REVIEW | Admin-only explicit reopen, new evidence/note; history retained |

Review record stores risk_event_id, current status/assignee, reviewed_by/at,
notes/resolution and version. Transaction ID is derived from the event FK, avoiding
contradictory duplicate identifiers. An append-only history preserves every state
change. Update WHERE version=expected and increment once; stale write ->409.
Repeated command request must return its original outcome rather than execute a
second transition. History has a unique request_id; a transition records a new one.
The API must read an existing receipt, compare actor and original command fields,
and return it or409 on conflicting reuse. That API path is not yet implemented. No browser-supplied actor name is trusted as identity.

| Role | Release permissions |
|---|---|
| Admin | workflow reads/writes, reopen, alert reconciliation, audit; no implicit permission to edit accepted financial data |
| Risk/Compliance Analyst | safe reads, assignment/review/resolution, manual quarantine correction/rejection; no admin reopen, actor impersonation or delivery reset |
| Read-only/Auditor | read authorized history/reports/audit; no transitions, corrections or alert reset |

Backend verifies authenticated identity, role and scope for every write; no shared
AWS keys in a browser. Cognito is a later authentication option, not deployed here.
SQL trigger guards enforce state/version/history shape, not JWT authentication.
Direct DB privileges/table owners remain a separate trust boundary; no runtime
roles or grants are changed by migration002. Production-scale identity hardening
is deferred, but minimal server-enforced RBAC is required for release usability.

## Manual quarantine correction

Original S3 evidence and quarantine case are immutable. Case state is derived:
OPEN (no correction or latest correction rejected by validation), RESUBMITTED
(pending/technical retry), RESOLVED (accepted or duplicate canonical result),
REJECTED (analyst rejection with note). Rejection is recorded, not deletion.

Authorized analyst loads safe evidence, submits corrected values with reason and
idempotency request_id. Save a new versioned safe correction object, append a
correction receipt and allocate a new linked batch/record. Validate every field,
account and identity through the normal processing path before accepting it.
Concurrent corrections lock the original case; no second pending correction.
A database-assigned per-case correction version orders lineage independently of
client timestamps; request_id uniquely identifies a submitted command.
The original occurrence remains QUARANTINED. A corrected duplicate can resolve the
case without new money. Identity conflict/new invalid values remain quarantined
and visible, allowing another manually approved correction. Technical failure
retries the same correction request, not a fresh anonymous submission.

SQL stores references/lineage and outcome, not copied raw payload or passwords.
S3/SQL cross-store work requires immutable receipts and retry reconciliation:
an orphaned correction object is not a submitted/accepted transaction. Corrected
records cannot bypass validation or dedupe through a special direct ledger write.
Automated repair/reprocessing is deferred. Submission/resolution APIs and UI still
need implementation; local SQL correction tests do not prove those endpoints.

## Batch reconciliation

Hard invariant for parseable content:
`rows_received = accepted + quarantined + duplicate + failed_technical + pending`.
Dispositions count once per (batch_id,source_row), irrespective of delivery count.
FAILED_TECHNICAL is explicit unresolved technical failure, not quarantine, not
accepted; retry may move it back through QUEUED to a terminal business outcome.
Terminal ACCEPTED/QUARANTINED/DUPLICATE are immutable. Correction has a new occurrence
linked to the original; the original batch is never rewritten to erase rejects.

| Batch state | Exact meaning |
|---|---|
| RECEIVED | file/attempt registered, parsed total not yet known |
| PROCESSING | known total, publication not complete, records pending |
| QUEUED (UI: queued) | publication complete, final ledger outcomes still pending |
| COMPLETED | every row resolved, pending0 and failed_technical0; may include business quarantine/duplicates |
| PARTIAL | some business outcomes resolved but file/technical failure remains |
| FAILED | file failure before any business resolution, or only technical failures |

Unknown-total parser failure is FAILED with null total, not0. Header-only valid
empty file may complete with0. Whole-file duplicate is an attempt status on the
original content batch, not a new batch adding accepted/duplicate money again.
Counts derive from durable occurrence outcomes, not mutable counters on transactions.
Database checks refuse more registered occurrences than declared parsed total.
Do not treat COMPLETED as all rows valid; show each disjoint counter separately.

Outside-VPC ingest retains S3 receipt/publication audit. A private worker/read-model
projector imports immutable receipt metadata idempotently into operational SQL;
no new NAT or ingest SQL access is implied. The final acceptance outcome should
join the ledger commit where possible; publication/quarantine receipts may reconcile
later. Expired queues, DLQs and missing projections leave visible pending/technical
states with operator recovery. Existing application paths do not yet write these
operational tables. The new view is not currently a live batch dashboard.

## Alert idempotency and recovery

Release condition is HIGH automatic frozen decision. One such risk_event per
canonical transaction means existing cloud ALERT#canonical_tx key is its logical
notification identity. SQL direct/local delivery remains a separate teaching path;
release cloud authority is the existing DynamoDB claim, not SQL alerts alone.
A manual event, review resolution or projection rebuild does not create another
release alert condition or reset an existing claim.

Claim SENDING conditionally before SES; SENT retry returns recorded provider ID;
definite FAILED may retry; SENDING/UNKNOWN require Admin reconciliation with provider
evidence. Disable blind SDK retries. Success followed by failed state persistence
must not resend automatically. Exactly-once email cannot be promised. Notification
failure remains independently trackable and does not change ledger acceptance.
Retain claims for the supported replay horizon; audit reconciliation actor/reason.
Read-only delivery API must reflect DynamoDB authority; the SQL proposal introduces
no duplicate alert state table. Future channels/recipients require a new reviewed
logical identity, not reuse of a single-recipient claim.

## Frontend/backend contracts

All endpoints below beyond existing GET routes are proposed, not implemented.
Use backend authorization and bounded paging; safe summaries by default. No raw
customer identifiers/contact details exposed merely because SQL contains them.

| View | Required source and API behaviour |
|---|---|
| Login/RBAC | authenticated server-verified subject/role; Admin, Analyst, Auditor permissions above |
| Dashboard | per-currency ledger totals, risk counts, review states, reconciled batch counts, technical backlog and freshness |
| Transactions/detail | current bounded cursor list plus identity, country, provenance, canonical risk/result/review links |
| Risk events | immutable event score/reasons/config/version, manual/automatic distinction, matched charge links |
| Review queue | risk_reviews joined event/transaction; GET list/detail; POST transition with expected version/request_id |
| Quarantine | case/status/safe payload/source detail; POST correction or rejection with request_id |
| Batches | batch_reconciliation, attempts and record outcomes; original vs correction links; no QUEUED=accepted label |
| Reports | existing UTC/month/per-currency movement; controlled list/download and separate risk/review summaries |
| Account history | ledger plus authorized review/delivery links, monetary movement labelled accurately |
| Admin/Audit | append-only review/correction history, pending/failed record recovery and delivery reconciliation receipts |

## Schema proposal: migration002

[002_operational_workflows.sql](../sql/migrations/002_operational_workflows.sql)
adds seven relational tables and two derived views. Requires base schema plus001.
No transaction/risk/alert financial columns are changed, and001 hash stays pinned.

| Table | Reason |
|---|---|
| ingestion_batches | immutable source/content/receipt clock and parsed total; publication flag/file error |
| ingestion_attempts | exact source file/version/ETag; whole-file duplicates and unreadable-file failures, nullable batch for pre-hash failure |
| ingestion_records | one durable disposition per batch/record with exact source attempt and optional canonical transaction |
| risk_reviews | event-scoped current review, assignee/resolution, actor and optimistic version |
| risk_review_history | automatic transition history; updates/deletes rejected |
| quarantine_cases | immutable reason and original versioned safe evidence reference |
| quarantine_corrections | immutable actor/request/correction evidence and link to a new processing occurrence, or explicit reject |

Views batch_reconciliation and quarantine_workflow derive counts/states instead
of maintaining conflicting aggregates. Fixed SECURITY INVOKER triggers guard
terminal outcomes, original provenance, parsed count bounds, transitions/version,
audit immutability and correction serialization. Functions use qualified table
names and pg_catalog/pg_temp path; PUBLIC execution is revoked. They do not grant
new privileged capabilities or enforce application RBAC themselves.

Migration002 is a single transaction, fail-closed on existing target objects.
It is not blindly rerunnable: a second application fails rather than silently
accepting an incompatible table. A reviewed migration version/checksum ledger is
required for live execution. No runner update packages002: the verified runner
executes001 only. Any future002 runner/permissions/packages need their own review.
Fresh-install schema.sql has not been silently extended; bootstrap must use base
then001 then approved002 in its future migration orchestration.

## Verification, CSV import and remaining implementation

Existing 451-test Linux/PG16 gate remains historical evidence for its exact source.
This phase uses the dedicated local test database with isolated schemas and mocked
AWS transport. New tests check reference validation, risk boundaries, authorization
contract, actual SQL audit/transitions, stale writes, terminal immutability, exact
provenance, over-count rejection, correction duplicate resolution, unchanged legacy
rows and unchanged001. Existing idempotency/S3/SQL/SES/report tests are included.
Local PostgreSQL is18.6 / Python3.14.7; this does not establish new002 on RDS or
PostgreSQL16. No CI rerun/push or package rebuild occurred. Evidence records exact
final counts and environment; no failed attempt is labelled successful.

CSV A: fintrust_e2e_mixed_transactions.csv. CSV B:
fintrust_e2e_companion_transactions_B.csv. Both are external ChatGPT downloads,
not present in the repository. Tests currently use scenario rows, not claimed
CSV execution. Later import the actual files into a reviewed location, preserve
bytes/hashes, identify fixture account IDs, freeze receipt clock and expected row
outcomes, map source references between files and run the same local acceptance
path. No invented repository paths or AWS upload. Hour-velocity expectations must
follow the five-minute rule described above.

Still designed / not implemented: strict production validation integration and
structured envelope everywhere; reviewed rule version in actual frozen results;
review/correction command APIs using durable history/correction receipts and RBAC; per-occurrence
worker/projector writes and DLQ reconciliation; frontend endpoints/screens; cloud
alert read/reconciliation audit. Minimal working workflows are release requirements,
not a claim that this design milestone completed their implementation.

Deferred: refunds/reversals/chargebacks, advanced behavioural baselines, impossible
travel, enterprise case management, automatic quarantine repair/reprocessing,
additional notification conditions/channels, and production-scale identity hardening.
Existing account status/KYC is shown as context; automated enforcement is deferred.
All live RDS migration, snapshots, IAM/network changes, uploads, deployment,
Cognito creation, concurrency and trigger wiring remain separate approval gates.

Next checkpoint: **FINTRUST RELEASE 1 BUSINESS PROCESS AND SCHEMA READY FOR REVIEW**.
Approval of this contract is followed by focused local workflow/API implementation
and target-version tests, not automatic AWS execution.


### Recorded local result

Final focused run: **94 passed, 0 failed, 0 skipped**. Evidence:
[summary](EVIDENCE/12-e2e/release1-process-local/summary.json) and
[JUnit results](EVIDENCE/12-e2e/release1-process-local/results.xml).
All isolated workflow schemas were removed; migration001 and verified application
ZIP hashes are unchanged. These are local design/schema and existing pipeline
checks, not proof of production API/RBAC/CSV execution or live deployment.


## End-to-end closure continuation ? 2026-10-10

The authoritative implementation/status evidence is in `RELEASE1_GAP_REGISTER`
(JSON full fields; Markdown review table), `RELEASE1_OPERATIONS.md`,
`RELEASE1_E2E_MANIFEST.md` and `RELEASE1_FAILURE_INJECTION.md`. Earlier design-only
statements in this document are superseded where the continuation implements them.
The executable strict contract is `fintrust/release_contract.py`; the tools import
is compatibility for earlier tests. Normal Release1 intake/worker is version3;
legacy teaching/v1/v2 processing remains explicitly distinct.

Batch states are exactly RECEIVED, PROCESSING, QUEUED, COMPLETED, PARTIAL, FAILED.
Whole-file replay is an attempt disposition DUPLICATE_FILE, not a second financial
batch. Each parsed occurrence belongs to exactly one disjoint terminal outcome or
pending: received=accepted+quarantined+duplicate+technical_failed+pending. COMPLETED
means the financial/business partition is complete; pending projections/alerts
are operational backlogs and remain visible separately. Failed infrastructure is
not reclassified as accepted merely to reconcile totals.

**User freeze confirmed:** HIGH_VELOCITY remains >5 accepted transactions in the
closed preceding300 seconds including the current accepted transaction. A 10/11/12
one-hour scenario is deferred exploration, not a new rule. No risk threshold was
changed. Rule version `fintrust-r1-rules-2026-10-09` and config are frozen into each
new accepted result. Strict Release1 refuses a changed environment rule config
rather than labelling altered thresholds with the same version.

Migration002 now has immutable candidate/request digests, review trigger history,
quarantine correction/projection outboxes and durable local migration tracking.
No columns in migration001 changed. The local migration harness is restricted to
loopback dedicated test DBs; it is not approval or implementation of the live002
runner. Proposed workflow grants use a separate history-writer non-login owner
and deny API financial/history writes. PostgreSQL16 privilege proof is a hard gate.

Review/correction backend and `/release1` local workspace are implemented and
browser-tested with synthetic data. Actor, role and account scope come from the
backend's local hashed-token registry, never browser fields. Cognito/federation is
not deployed. Only Admin may inspect/correct unassigned-account cases; corrected
values must target an assigned account and must pass the same worker pipeline.
The original record and all previous correction/review history remain immutable.
No direct approve-into-ledger action exists.

The actual named CSV A/B files remain external and unexecuted. Constructed cases
verify the scenario contract; do not present them as evidence for unseen files.
No AWS access, schema mutation, deployment, trigger activation or Git push occurred.

## Monday verification closeout (2026-10-10)

Release1 local workflows and browser demo are verified. PostgreSQL 16.15 migration/service-role and Linux Python 3.12.15 native-import gates passed at commit 4d91c3d in CI run 38050661063 (543 passed, zero skips/failures). HIGH_VELOCITY remains >5 accepted transactions in a closed 5-minute window. CSV A/B bytes remain external; only that fixture acceptance is pending. No live migration/new AWS runtime activation occurred. Use RELEASE1_MONDAY_DEMO.md and RELEASE1_PRESENTATION_STATUS.md for exact launch and capability boundaries.

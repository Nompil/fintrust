> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

> 2026-10-10 continuation: local gap closure implements the review/correction and
> strict runtime contract. See [gap register](RELEASE1_GAP_REGISTER.md) and
> [operations/release gates](RELEASE1_OPERATIONS.md). This earlier review is
> historical design evidence, not a claim of new AWS/PG16 verification.

# FinTrust first-release business-rule and schema review

Review date: 2026-10-09 (Africa/Johannesburg). Source checkpoint: `a136467`.
Status: **INITIAL REVIEW SUPERSEDED BY THE RELEASE 1 CONTRACT; SCHEMA READY FOR REVIEW**.
See [Release 1 business process](RELEASE1_BUSINESS_PROCESS.md) for approved scope,
selected rule defaults, migration002 proposal, tests and implementation gaps.
The observations and unanswered recommendations below are historical review context.
This document is a proposed business contract and source-backed gap assessment,
not approval to change schema, run migration 001, or perform infrastructure work.
No application/SQL changes, package builds, AWS calls or live database access belong
in this review. The runner safety gate remains verified in CI 37931518056.

## Proposed first-release process

FinTrust monitors imported synthetic transaction records. It is not a payment
processor: its score does not approve, block, refund or reverse money. The current
`hold`/`approve` result must be presented as a review recommendation, not an executed
financial action. A valid high-risk transaction belongs in the ledger and review
queue; invalid data belongs in quarantine. Neither should silently disappear.

Proposed sequence: receive and identify a file; validate each record; record any
rejection or duplicate disposition; publish eligible rows; admit/score atomically
against the ledger; reconcile every row to its final outcome; present immutable
risk evidence; let an authorized analyst review it; notify once per approved
alert identity; correct rejected data through a new, linked submission and repeat
validation and duplicate checks. Reports distinguish financial facts from risk
signals, review outcomes and processing progress.

Analyst review and correction are proposed release-1 workflows, pending the user's
scope decision. Their absence today is a gap, not an already implemented feature.
Refund/reversal support is a separate open scope decision; the proposed bounded
release rejects those types explicitly rather than disguising them as credits.

## 1. Transaction identity

Sources: [jobs.py](../backend/fintrust/jobs.py), [ledger.py](../backend/fintrust/ledger.py),
[batches.py](../backend/fintrust/batches.py), [migration 001](../sql/migrations/001_transaction_identity.sql).

| Identity | Current implementation | Proposed business contract / decision |
|---|---|---|
| Internal `tx_id` | UUID primary key; supplied UUID accepted, otherwise deterministic UUIDv5 from batch and record ordinal | Immutable canonical ledger identity. A matching upstream reference can resolve a new submitted UUID to the existing canonical UUID. Do not promise every external UUID becomes a new transaction. |
| Upstream reference | Case-sensitive trimmed source reference, scoped by source system and account; partial SQL unique index | Require a stable reference for the normal release feed. Same reference with changed financial content is a conflict, never an update. Compatibility files without one carry an explicit limited-deduplication warning. |
| Source system | Trimmed text; defaults to bucket for v2 if omitted | Approve a stable named source contract. A bucket default is a compatibility fallback, not a business namespace registry; changing names must not defeat duplicate detection. |
| Fingerprint | v2 SHA256 of normalized financial/identity fields, excluding internal UUID/file/batch metadata; v1 compatibility retained | Compare content only after reliable identity matches. Never globally unique: similar real charges must survive. Contract/fingerprint version must remain recoverable. |
| Batch/file identity | Batch UUID derived from bucket + SHA256 of original bytes; separate attempt UUID and source key/version/ETag audit | Distinguish logical content batch, upload attempt, file location and transaction. Same bytes in a different bucket are currently a different batch. ETag is not the content hash. |
| Row | CSV record ordinal beginning at 2 | Call it a record number, not a physical text line: quoted multiline records can span lines. Corrections preserve the original record reference and add a new submission link. |

Historical null identity metadata is valid; do not invent references or backfill
fingerprints without evidence. New feed requirements can be stricter than legacy
storage. Current nullable columns/checks do not enforce all v2 fields as a group.
`Transaction` in models.py omits country although jobs/ledger persist it: reconcile
that serialization path before relying on it for the new frontend contract.

## 2. Duplicate behaviour

Sources: jobs.py, ingest.py, ledger.py, score.py; existing
[identity tests](../tests/test_idempotency.py) and
[database identity tests](../tests/data_quality/test_idempotency.py).

| Situation | Current behaviour | Freeze requirement |
|---|---|---|
| Same reliable identity twice in a file, equal normalized content | First published; later occurrence audited as DUPLICATE_ROW_IN_FILE | Count one acceptance and a separate duplicate disposition. |
| Same identity, different content | TRANSACTION_IDENTITY_CONFLICT | Quarantine conflict; no last-write-wins. First accepted content remains immutable. |
| Same reference/account/source in different files | SQL reuses canonical transaction and frozen result; duplicate receipt records new occurrence | Preserve provenance of every occurrence, including the new file; do not count as new money. |
| Completed byte-identical file in same bucket | DUPLICATE_FILE attempt; no republish | Preserve original batch counters; new attempt is not another set of accepted transactions. Renaming alone must not change this. |
| Partial publication, worker retry, concurrent arrival | May republish; account lock, SQL identity and frozen result prevent duplicate ledger/risk writes | A transport retry is not a business duplicate row. Reconcile delivery attempts separately. |
| Similar-looking transactions, no trustworthy common identity | Kept separately | Do not silently discard by fingerprint, amount or timestamp. Deduplication cannot be guaranteed across differently formatted files without reliable IDs. |
| Distinct references, same debit/merchant/amount/currency nearby | Both kept; possible duplicate-charge signal on newly processed transaction | Review signal only. Earlier frozen score remains unchanged; no automatic reversal or deletion. |

If two submitted rows have different source references but reuse the same internal
UUID, ledger conflict detection still applies. Source identity and internal identity
must not point to different accepted transactions.

## 3. Validation rules

Sources: [validators.py](../backend/fintrust/validators.py), ingest.py, score.py, schema.sql.

| Rule | Current behaviour | Proposed release decision / gap |
|---|---|---|
| Required values | account_id, amount, tx_date, tx_type required; UUID syntax checked | Keep these; normal release feed should also declare stable source/reference, currency and country. Defaults need an explicit feed contract. |
| Amount | Finite positive decimal, at most two fractional digits, below 10^13 | Keep. Zero, negative, NaN/infinity, over-capacity and excess precision reject. All supported currencies currently use this two-decimal teaching model. |
| Timestamp | ISO parsing, UTC normalization, max six fractional digits; date-only/naive accepted as UTC | Decide strict timezone-bearing timestamps for normal feed vs legacy compatibility. Future timestamps currently pass. Proposed future tolerance: five minutes against fixed first-receipt time, subject to approval; replay must not change the validation clock. |
| Unknown account | Cloud ingest checks syntax only; scorer checks existence under account lock and quarantines | Distinguish syntactically accepted/published from ledger accepted. Never auto-create customer/account from the feed. Account status/KYC admission behaviour is not currently enforced; decide monitoring-only scope. |
| Country | Two ASCII alphabetic characters; absent defaults ZA | ZZ passes today. Require an approved country-code reference list; do not treat any two letters as a real country. Clarify this means transaction country relative to ZA, not customer nationality. |
| Currency | ZAR/USD/EUR/GBP/KES allowlist, absent defaults ZAR | No FX conversion. Thresholds currently use the same numeric units in each currency. Approve currency-specific thresholds or restrict initial demonstration to ZAR; never aggregate mixed money. |
| Type | debit, credit, transfer, fee; amount always positive | Transfer currently means outgoing in reports. Credit is not proof of a refund. Incoming/internal transfer matching is outside current model. |
| Refund/reversal | Explicit refund/reversal types reject; no link to original transaction | Proposed defer for release 1. If required, define original-reference link, full/partial amounts, currency/account match, remaining reversible amount, repeated refund identity and scoring/report effects before schema design. |
| File format | UTF-8 CSV, required unique headers, 1 MiB/5,000 records; unexpected named columns ignored/redacted from quarantine | Document exact feed contract. File-level failures need a visible failed-attempt outcome even where failure occurs before BatchAudit starts. |

Validation cannot determine whether an ordinary credit is economically a refund
unless the upstream contract supplies that meaning. Do not claim automatic detection.

## 4. Quarantine process

Sources: [quarantine.py](../backend/fintrust/quarantine.py), ingest.py, score.py.
Current S3 records retain reason_code/detail, validation_errors, allowlisted row
payload, source bucket/key/version/ETag, record number, batch and timestamps.
Unknown columns are omitted and raw_row_redacted indicates omission. The allowed
merchant/reference fields can still be sensitive; this is restricted data, not
anonymized data. Original source bytes remain at the versioned source pointer.

Current codes include MISSING_REQUIRED_FIELD, INVALID_AMOUNT, INVALID_TIMESTAMP,
INVALID_ROW, UNKNOWN_ACCOUNT, TRANSACTION_IDENTITY_CONFLICT, DUPLICATE_ROW_IN_FILE,
DUPLICATE_TRANSACTION and DUPLICATE_FILE (file audit). Currency/country/type failures
currently fall into generic INVALID_ROW; stable specific codes are a proposed API
contract improvement. Only the first validation error is returned today.

Missing: stable quarantine-case identity, analyst ownership/state, immutable
correction linkage, reprocessing command/API and outcome audit. Proposal:

1. Preserve original payload and reasons; authorized analyst sees only needed fields.
2. Record correction author/time/reason and parent rejection; never edit the original.
3. Submit a new correction attempt with original source identity where appropriate.
4. Revalidate all rules and run normal identity checks. Fixing a rejected row is not
   permission to overwrite an already accepted transaction. A correction that now
   matches an accepted row ends DUPLICATE; differing content ends CONFLICT.
5. Record the final canonical transaction or new rejection and close the correction
   only after that outcome is durable. Concurrent/retried corrections must be idempotent.

Proposed quarantine states: OPEN, RESUBMITTED, RESOLVED, DISMISSED with audited
reasons. RESUBMITTED is not RESOLVED. These are not the risk review states below.
Store immutable source/audit objects in S3; derive an indexed workflow read model
only after the business contract is approved. No raw-payload SQL duplication needed.

## 5. Risk rules and boundaries

Source: [rules.py](../backend/fintrust/rules.py), score.py,
[boundary tests](../tests/test_processing.py), tests/data_quality/test_processing.py.
All are configurable demonstration rules, not business-approved fraud predictions.

| Signal | Exact current trigger | Points |
|---|---|---:|
| HIGH_AMOUNT | amount > 50,000 (equality does not trigger) | 30 |
| VERY_HIGH_AMOUNT | amount > 200,000, in addition to HIGH_AMOUNT | 25 |
| TRANSFER | outgoing transfer type | 20 |
| CROSS_BORDER | country differs from ZA or explicit true in rule input | 15 |
| MERCHANT_MARKER | merchant contains case-insensitive highrisk (synthetic marker) | 20 |
| HIGH_VELOCITY | >5 accepted transactions including current, same account, closed preceding 300-second event-time window | 30 |
| POSSIBLE_DUPLICATE_CHARGE | distinct nonnull refs, same source/account, debit, nonblank exact merchant, amount/currency; within inclusive +/-120 seconds | 40 |

Points sum, capped at 100. Low: 0-39; Medium: 40-69; High: 70-100.
High amount alone is Low (30); very high amount alone is Medium (55). This is
intentional current arithmetic, not proof those thresholds fit the business.
Velocity currently counts all accepted transaction types/currencies. At most 20
matching charge IDs are returned. Matching merchant case/spacing and source scopes
are exact after current normalization. No retroactive rescoring: late arrivals can
change only their own new result, so outcomes can depend on arrival order.

Approve rule weights, currency scope, windows, type scope and arrival-order policy.
Freeze a rule-set version and evaluated context for audit. Current frozen JSON saves
config, reasons, points and matching IDs; SQL risk_events stores only score and a
joined reason string. A dedicated rule version is missing. Do not reclassify old
scores under newly changed settings in the frontend. `flag_account` can add a
separate manual score100 event; distinguish that from automatic frozen decisions.

## 6. Status model

Keep three independent concepts; do not overload accounts.status or a single
transaction status column.

| Concept | Proposed meaning | Current support |
|---|---|---|
| Data disposition (per submitted occurrence) | RECEIVED / PUBLISHED / ACCEPTED / QUARANTINED / DUPLICATE, with failures/pending visible | Partial S3 and SQL evidence; no unified authoritative outcome model |
| Risk level (per scored transaction/event) | LOW / MEDIUM / HIGH with immutable numeric score/reasons | Implemented as title-case Low/Medium/High in frozen result; API naming needs a contract, not silent conversion |
| Review status (per case) | OPEN / UNDER_REVIEW / CLEARED / CONFIRMED_RISK / ESCALATED | Not implemented |

An ACCEPTED transaction can be HIGH and UNDER_REVIEW. CLEARED does not change the
original score or financial record. QUARANTINED data has no accepted transaction to
review for financial risk yet. Duplicate disposition is not an alert or risk level.
Delivery state (PENDING/SENDING/SENT/FAILED/UNKNOWN) remains a fourth, separate
operational concept. Missing historical risk assessment is UNASSESSED, not Low.

## 7. Risk review lifecycle (proposed; not implemented)

Proposed case scope: one initial case per canonical transaction with a Medium/High
automatic result; additional manual events link to the case instead of creating
uncontrolled duplicates. Low results remain visible without opening a case. Exact
case scope and opening threshold need approval.

| From | Allowed destination | Required evidence |
|---|---|---|
| OPEN | UNDER_REVIEW | authenticated reviewer assignment and time |
| UNDER_REVIEW | CLEARED / CONFIRMED_RISK / ESCALATED | actor, reason, note, time, previous state/version |
| ESCALATED | UNDER_REVIEW | authorized reassignment/acknowledgment with reason |
| CLEARED / CONFIRMED_RISK | UNDER_REVIEW only by authorized reopen | new reason and append-only history; never erase earlier resolution |

No direct browser mutation of scores, ledger data or alert-delivery claims.
Enforce transitions server-side with optimistic concurrency and request idempotency.
Record reviewer identity, not a browser-supplied display name as authority. A stale
review must conflict instead of silently overwriting another reviewer's decision.
CONFIRMED_RISK means the analyst confirmed the review concern; it is not a legal
fraud determination and does not freeze an account or move money automatically.
Current API has no review write routes or authenticated analyst workflow.

## 8. Batch reconciliation

Source: batches.py and both ingest/scoring entry points. PUBLISHED currently means
all eligible SQS sends/quarantine writes succeeded; not completed downstream SQL.
The current rows_valid/accepted_rows label is therefore misleading as a final
acceptance count. Downstream UNKNOWN_ACCOUNT/conflict/replay receipts do not update
the original completion marker. A ledger row stores first-batch provenance, so
ledger counts alone cannot reconcile duplicates occurring in later batches.

Proposed invariant for each parseable original submission:
`received = accepted_new + duplicate + quarantined + pending`.
At reconciled completion, pending=0. Categories are disjoint and counted once per
batch/record occurrence, not once per transport delivery. While an outcome is
uncertain, leave it pending with an operational error rather than invent success.
File parse failures with unknown record count stay FAILED_FILE with unknown count;
zero is not a fabricated reconciliation total. Nothing is silently discarded.

Currently rows_quarantined includes in-file duplicate audit records; present
quarantined_rejected = rows_quarantined - rows_duplicate for that original ingest
attempt. DUPLICATE_FILE attempts have different counters and must not apply that
formula or count original records again. Original completed-batch outcomes remain.

Proposed process requires a durable per-occurrence outcome link to canonical tx_id
or rejection, and an idempotent reconciliation projection. Accepted outcome belongs
with the ledger commit or a durable recoverable outbox; S3 publication and SQL are
not one transaction. A failed projection/receipt remains retryable and visible.
Keep ingest outside the VPC; do not make it write SQL just to implement the UI.
Retain/reconcile DLQ and expired deliveries; existing finite queues cannot guarantee
nothing disappears without an operator recovery procedure and overdue-batch view.

## 9. Alert idempotency

Sources: [alert_delivery.py](../backend/fintrust/alert_delivery.py), alert.py, dynamo.py.
Cloud stream path uses canonical account/transaction key ALERT#tx_id, conditional
SENDING claim, then SENT/FAILED/UNKNOWN. SENT retries return without sending.
SENDING/UNKNOWN are not automatically reclaimed. Definite rejection can retry;
uncertain provider acceptance or failed final status write requires reconciliation.
This prevents blind resend but does not promise exactly-once email delivery or
that every uncertain send was delivered.

SQL alerts + delivery_key is a separate direct/local path. Cloud stream sends do
not populate SQL alerts. The frontend must not query only SQL and claim a complete
cloud delivery history. Choose one authoritative delivery path for release 1;
retain delivery claims for the entire supported replay horizon. Rebuilding a risk
projection must not erase an existing delivery claim. Additional recipients/channels
or alerts on review changes would need a new explicit delivery identity contract.
Current stream claim supports one canonical transaction notification to configured
recipient. Review changes must not silently reset its claim.

## 10. Frontend data needs

Sources: [API contract](api_design.md), fintrust/api.py, query.py, report.py,
frontend/index.html, sql/monthly_summary.sql. Existing browser is a local prototype;
its displayed example risk score is explicitly not updated by uploads.

| Screen | Required business information | Existing support / remaining gap |
|---|---|---|
| Dashboard | ledger totals by currency, processing backlog, risk and review counts, last update | Basic counts/trend/currency totals exist; no batch backlog, review counts or unified live risk feed |
| Transactions | canonical ID, source reference, financial fields, risk and review links, provenance | Account-scoped cursor paging exists; current SELECT omits identity/batch/country metadata and joined risk/review status |
| Risk events | immutable score, reasons/points, rule version/context, matched charge links | SQL events and frozen JSON exist; no dedicated list/detail endpoint or rule version; manual/automatic events need distinction |
| Review queue | assignee, priority, case state/history, permitted transitions | No case model, audit history or authorized write API |
| Quarantine | safe record summary, reasons, source/record pointer, correction and final outcome | S3 objects exist; no indexed list/detail, correction history or reprocess API |
| Ingestion batches | file/attempt, total, published, terminal outcomes, pending/failures | S3 audit exists; no final scorer reconciliation or UI read model |
| Reports | bounded UTC period, per-currency movement, risk/review summaries if included | Monthly CSV/JSON movement exists; no report-list/download UI contract or review summaries |
| Account history | stable transaction paging plus contextual risk/review information | Ledger history exists; no complete linked review/alert history |

The report's running_balance is net movement from zero opening balance per
currency, not an authoritative bank balance. Transfers are outgoing; accounts.balance
is not maintained by ingestion. Label this accurately in the product. No mixed-FX
sum. Display timestamps with timezone while retaining UTC for ordering/reconciliation.
Authorization for an analyst browser is unimplemented; CORS is not authentication.
User/customer personal details and raw quarantine data require separate access
rules; existing SQL views containing customer names are not blanket UI permission.

## Derived data model: proposals, not column changes

| Business concept | Existing persistence | Minimal direction after approval |
|---|---|---|
| Immutable transaction identity | transactions + migration001 | Keep current foundation; approve source/time/currency contract and version treatment |
| Immutable risk decision | risk_events + processed_transactions.result | Reuse reasons/config; add version/event-origin semantics only when contract decided |
| Analyst case and transition history | Missing | Separate case/history concept; do not mutate frozen scores or overload transactions |
| Quarantine correction lineage | S3 rejection/source evidence only | Immutable original plus linked correction attempts/outcomes; indexed access when needed |
| Batch and record outcome ledger | S3 publication audit; first-batch SQL link | Stable per-occurrence outcomes and reconciliation view, preserving outside-VPC ingest |
| Notification delivery | DynamoDB cloud claims; SQL local claims | Select authoritative cloud path and expose controlled read/reconciliation workflow |

No table/column has been added. Persistence choices for new workflows are deliberately
not frozen by this review. A new SQL table is not automatically the answer to each
screen; reuse existing immutable evidence and make write consistency explicit.

## Decisions required before freeze

| ID | Decision | Proposed bounded choice (not approved) |
|---|---|---|
| D1 | Release scope | Include analyst review and correction/reprocessing if required by the demo; otherwise explicitly label read-only/deferred, not complete |
| D2 | Refund/reversal | Reject explicit types in release 1; do not map implicitly to credits |
| D3 | Source contract | Stable named source + account-scoped reference required for normal feed; legacy compatibility visibly limited |
| D4 | Time/country defaults | Strict normal feed with timezone, currency/country; allow legacy UTC/ZAR/ZA only under declared profile; approved country list; five-minute future tolerance |
| D5 | Scoring contract | Approve the table above or revised weights; ZAR-only initial demo unless currency thresholds approved; include all accepted types in velocity and no retroactive rescore only if accepted |
| D6 | Case semantics | One transaction case, opens Medium/High, transitions above, immutable actor/history, authorized reopen |
| D7 | Reconciliation and delivery | Per-record terminal outcome accounting; one cloud alert path; uncertain sends require operator reconciliation |

D1/D2 were unanswered at this initial review. The user subsequently selected working
review/correction scope and deferred refunds/reversals/chargebacks; see the Release 1 contract. Other
choices are recommendations for review, not assumptions silently applied to code.

## Migration 001 disposition and exit criteria

**Do not run or declare 001 final yet.** Its seven nullable metadata columns and
two indexes are a sensible identity foundation, but they do not constitute a full
release schema. This review found no justification to add review/batch workflow
columns to transactions blindly. Preferred sequence after business approval:

1. Record agreed D1-D7 and a small synthetic acceptance dataset covering each branch.
2. Finalize API/state and logical data contracts, then select storage/consistency paths.
3. Keep 001 identity-only if those contracts permit; implement additional workflow
   migrations separately. If source identity semantics or its checks must change,
   revise 001 deliberately and revalidate its pinned runner/helper and packages.
4. Add acceptance tests for future/country policy, correction replay/conflict,
   authorized review transitions/history/concurrency, final batch accounting under
   partial failures, and cloud alert/read-model reconciliation. Existing 451 green
   tests establish implemented behaviour, not acceptance of these proposed rules.
5. Reconcile canonical schema, ERD, API and frontend contract and only then mark
   BUSINESS RULES APPROVED / SCHEMA FROZEN. Live migration remains separately gated.

Prior documentation contains historical statements now superseded by source (for
example system_design.md's old identity/gap text and IDEMPOTENCY.md's old release
status). This review distinguishes those from current behaviour; broad historical
document cleanup should follow the approved freeze rather than repeat old audits.

## Verification in this review

Inspected source and relevant existing tests; no full suite/CI rerun for this
review-only change. A small offline Python probe confirmed: future year2099 and
country ZZ currently pass; zero/negative amounts reject; refund/reversal types
reject. Amount-only results: 50,000 ->0 Low; 50,000.01 ->30 Low; 200,000 ->30 Low;
200,000.01 ->55 Medium. Risk boundaries 39/40/69/70 ->Low/Medium/Medium/High.
No network, database or AWS calls were made by the probe. No application code,
SQL, IAM, infrastructure, verified ZIP or existing unrelated work was changed.

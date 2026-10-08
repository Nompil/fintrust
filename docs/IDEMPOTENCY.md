# Transaction identity and duplicate handling

Status: DUPLICATE/IDEMPOTENCY HARDENING READY FOR REVIEW; local implementation only; no cloud migration, role update,
package upload or activation has occurred. Stages 1–4 retain their previously
reported deployed status. Stage 5 remains blocked by the separate live tagging
permission issue. This change does not resolve or execute that diagnostic.

## Identity and admission

`tx_id` stays the internal UUID primary key. CSVs may additionally supply
`source_transaction_id` (or the equivalent `source_reference`) and
`source_system`. References are case-sensitive, stripped of surrounding spaces,
and limited to 200 characters; the namespace is limited to 100 characters.
The source bucket is the default namespace when a reference has no explicit
source system. A source must guarantee reference uniqueness within an account.
Production feeds must use a reviewed stable namespace, not change it per file.
There is deliberately no universal claim that references from different banks
identify the same financial event.

The partial SQL unique index is `(source_system, account_id,
source_transaction_id)` for non-null references. It prevents another ledger
writer bypassing Python admission from inserting that identity again. An internal
UUID which identifies another accepted transaction is also a conflict.

Version 2 fingerprints hash normalized financial fields: account, decimal amount,
currency, transaction type, UTC timestamp at microsecond precision, country,
merchant, source system/reference and contract version. Internal UUID, correlation
ID, file location and batch timestamps are excluded. Fingerprints are compared
only after a reliable identity matches; they have NO global unique constraint.
Changed financial data under an accepted identity is a conflict, not a duplicate.
Version 1 fingerprints and frozen results retain their original digest format.

Without a supplied UUID or upstream reference, UUIDv5 uses source bucket/file
SHA-256 batch identity and CSV row number. Exact content replay is stable, including
renamed files/new S3 versions in the same source bucket. Equal-looking rows at
separate row numbers remain separate. Differently formatted files without IDs
cannot establish cross-file business identity safely; provide upstream references.
A supplied UUID remains a compatibility identity, but a new UUID alone cannot
prove that an otherwise similar row is the same event.

| Situation | Behavior |
|---|---|
| Completed identical file in same source bucket | Skip transaction publication/load; audit `DUPLICATE_FILE` |
| Repeated reliable identity in one CSV, same financial data | Quarantine/audit `DUPLICATE_ROW_IN_FILE`; publish first once |
| Repeated identity with changed financial data | Structured `TRANSACTION_IDENTITY_CONFLICT`; never overwrite accepted data |
| Same upstream reference in another file/new internal UUID | Reuse canonical ledger/frozen result; audit `DUPLICATE_TRANSACTION` at scoring |
| Queue redelivery | Reuse committed result and canonical DynamoDB key; no new ledger/risk event |
| Similar or identical-looking rows without reliable identity | Retain; do not deduplicate by amount/time/fingerprint |
| Distinct references, matching debit/merchant/amount/currency nearby | Keep both; flag possible duplicate charge |

## Durable file tracking without a network redesign

Ingest remains outside the VPC, with no PostgreSQL access. The existing encrypted,
versioned quarantine S3 bucket holds the equivalent ingestion-batch model:

- `quarantine/batches/<batch UUID>/complete.json`;
- `quarantine/batches/<batch UUID>/attempts/<attempt UUID>.json`.

Batch UUID includes source bucket and SHA-256 of original uploaded bytes. The
completion marker is unique through a conditional `If-None-Match: *` write, not a
new SQL file-hash constraint. Every attempt records original filename, source
bucket/key/version/ETag, file hash, batch ID, ingestion/update timestamps, status,
row counts and a structured error/replay reason. Terminal counts separate total,
accepted, rejected and duplicate rows; original counters remain on the marker.
Direct text callers hash UTF-8 text; S3/local upload adapters pass the original
bytes, including any BOM. Canonical financial normalization is separate from the
byte hash.

STARTED is NOT a claim which suppresses other workers. A marker becomes PUBLISHED
only after all valid jobs have been accepted by SQS and quarantine writes have
succeeded (or local ledger loading has completed). A completed marker means
publication, not downstream scoring completion. Concurrent publishers or failures
before the marker can republish; deterministic IDs plus SQL final admission make
that safe. A 412 completion race checks the existing marker; 409, missing/corrupt
markers and authorization/storage failures retry. No denied read is treated as
proof that a marker is absent. Sequential completed replay records a separate
attempt and publishes nothing.

Retries may rewrite quarantine/attempt keys; S3 versioning retains earlier
versions. Completion/audit retention follows the existing quarantine policy,
which currently has no expiry. Removing markers is not a safe substitute for
ledger reconciliation. A manual replay after queue expiry/DLQ reconciliation needs
separate approval and a reviewed procedure; there is no automatic recovery from
expired queue messages. The low-level teaching `process_csv` helper retains an
explicit `track_batches=False` compatibility option; both S3 Lambda and local
browser upload enable durable tracking.

AWS semantics: [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).
These semantics were exercised with mocks locally, not observed live for this
new batch path.

## SQL and external effects

The shared ledger helper runs under the existing account `FOR UPDATE` lock.
Scoring atomically inserts ledger row, risk event and frozen result. Replays return
the original decision rather than applying changed thresholds/history. Conflicting
internal UUID/source-reference pairs fail admission. `ON CONFLICT DO NOTHING`
is followed by an explicit rejection, never silent acceptance of unknown data.
The local teaching loader also compares identity/content, records duplicate or
conflict reasons, isolates data failures with savepoints and retries infrastructure
errors.

DynamoDB publication and alerts use the canonical result UUID, even when a retry
arrives with another internal UUID. An immutable projection can be replayed after
SQL commit without generating another stream insert. Cross-file/new-UUID replay
receipts use `quarantine/accounts/duplicates/` before acknowledgment; inability to
persist an audit receipt causes retry. SQL risk-event IDs and original results
remain immutable. A direct caller of the lower-level `persist_score` helper is
responsible for its own audit/external publication; the processing entry point
supplies those boundaries.

## Quarantine and privacy

Invalid/unusable rows are quarantined with `reason_code`, `reason_detail`,
`validation_errors`, raw row, source/version/row pointer, batch ID, ingestion time
and available transaction/reference identity. Missing fields, invalid amount/time,
unknown accounts, repeated reliable identities and identity conflicts have
structured codes. Original raw source remains available through its object/version
and row pointer. The quarantine payload retains an allowlist of transaction fields,
including merchant/reference, and explicitly marks omitted unknown columns with
`raw_row_redacted`; customer IDs/contact details in arbitrary columns are not
copied to another bucket. Quarantine remains sensitive and access-controlled.
Whole-file syntax/size/encoding/header failures fail the invocation and retain a
FAILED batch attempt where tracking has started; they are not fabricated as rows.

Valid high-risk transactions proceed to scoring. Duplicate-data audit and risk
review are distinct; suspicious payments are not discarded as invalid data.

## Possible duplicate charge and time

`POSSIBLE_DUPLICATE_CHARGE` compares distinct non-null references in the same source
system/account, matching merchant, amount, currency and debit type. It searches a
symmetric event-time window to handle out-of-order arrival. Defaults are 120 seconds
and 40 risk points, configurable by `RISK_DUPLICATE_CHARGE_SECONDS` and
`RISK_DUPLICATE_CHARGE_POINTS`. Matching canonical UUIDs and the window appear in
frozen risk metadata; SQL stores the rule name. Both ledger entries remain.
Matching is intentionally conservative: no merchant/reference means no such
signal. At most 20 matching IDs are returned. This is a review signal, not proof
of fraud or accidental billing. Earlier frozen decisions are not retroactively
rescored; the newly accepted transaction carries the signal.

Existing SQL TIMESTAMPTZ and model/API ISO serialization preserve timezone and
microseconds. Ingestion normalizes timestamps to UTC without rounding; naive
legacy timestamps are explicitly interpreted as UTC. Inputs above six fractional
digits are rejected instead of silently truncating. Daily/monthly grouping is
report aggregation, not a change to ledger timestamp precision.

## Migration, compatibility and release gates

The additive [migration](../sql/migrations/001_transaction_identity.sql) adds
nullable identity, fingerprint, country, batch, hash and row columns; it adds the
partial identity index and a comparison index. Existing PK/FKs and financial
constraints remain. The same additive statements are in [schema.sql](../sql/schema.sql)
for new installations. No historical source IDs/fingerprints are invented or
backfilled. An old processed event still matches its version 1 digest. Historical
teaching-loader rows without a saved fingerprint require review rather than
silently accepting a conflicting/replayed identity. Existing views, seeds, stored
procedures, CTE/window reports, cursor pagination and API queries remain compatible.

Before cloud use, separately approve:

1. Database backup/reconciliation and migration on the intended RDS database;
   nullable historic values are expected. Reapply safely; do not run local setup
   against RDS. New source-index builds require a reviewed maintenance window.
2. Stable source-reference namespace/business contract and data-quality review.
3. Scoped proposed ingest `GetObject` on `quarantine/batches/*`, prefix-restricted
   `ListBucket`, and S3-mediated KMS decrypt context for that existing bucket.
   The local role renderer and Stage 5 runtime JSON agree. No attached role changed.
   Access Analyzer returned zero findings for the proposed Stage 5 runtime JSON
   on 2026-10-08. Effective authorization and live SSE-KMS read/write still need
   verification before attachment/activation. S3 bucket-key contexts identify the bucket, so S3 object scope
   is also necessary. See [SSE-KMS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html).
4. New Linux package build/import verification, green full CI with zero skips and
   a reviewed new digest/object version. The old uploaded VersionId remains valid
   for OLD SOURCE ONLY; it does not contain this hardening and must not be reused
   as evidence for these changes. No rebuild/upload/CI run happened in this task.
5. Review new templates/policy package pinning and drain old queue contracts before
   activating a new producer. Deploy compatible consumer/migration before v2
   producer. Version 1 can still parse/replay historical messages; do not mix old
   unmodified consumers with version 2 messages. Keep concurrency zero/triggers
   unwired through the separate Stage 5 recovery gate.

Rollback is a separately reviewed application rollback, not deleting ledger data
or dropping metadata. Keep the additive columns/index and audit objects; do not
start an old consumer against v2 jobs. Reconcile queued messages and canonical
SQL/DynamoDB IDs first. No new fixed-charge resource, NAT, endpoint or dependency
was introduced. Extra S3 list/get/put, retained object versions and KMS usage have
usage costs; existing RDS/key standing costs are unchanged.

## Verification status

Implemented and locally verified: admission/identity checks, batch/replay audit,
structured quarantine, SQL concurrency/uniqueness, timestamp preservation and
possible duplicate-charge signal. Local tests use the dedicated PostgreSQL test
database and mocked AWS; a transport guard rejects unmocked AWS HTTP requests.
The normal local administrator-only role test remains skipped by the restricted
local database account; this is not cloud permission evidence.

Implemented but not cloud verified: new S3 audit path, scoped IAM proposal,
version 2 queue contract and updated Lambda source.

Designed/planned: production namespace reconciliation, approved RDS migration,
new Linux/CI artifact approval, live SSE-KMS/provider checks, consumer-first
release, approved replay after queue expiry and retroactive risk reconciliation.


### Recorded local validation — 2026-10-08

`python tools/local.py test --database`: **252 passed, 0 failed, 1 skipped**,
69.65 seconds. All tests collected: 253. The only skip is the existing
administrator-dependent service-role test; no new hardening case was skipped.
The 35 new cases in `tests/test_idempotency.py` and
`tests/data_quality/test_idempotency.py` exercise file replays, interleaved
publication/conditional completion, failed publication, in-file and cross-file
references, concurrent SQL claims, source conflicts, canonical stream projections,
version 1 frozen results, repeated migration, microseconds, near-identical real
charges, quarantine reasons/redaction and high-risk admission. Existing fixture
setup executed schema, seeds, views and stored procedures; report/window/CTE,
constraint and API tests passed against `fintrust_local_test`.

Read-only validation used the confirmed `fintrust-inventory` IAM user in account
966467878406 / af-south-1. `accessanalyzer validate-policy` on the changed Stage 5
runtime policy returned `findings: []`. This does not prove effective attached
permissions or service-to-service request context. No policy was attached/updated.

The retained ZIP SHA-256 remains
`d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62`.
Comparison found three missing new modules and eight changed runtime files;
it cannot verify current source. Its historical Linux manifest was preserved.
New source Linux verification remains pending; no CI run/build/upload occurred.

Changed files:

- Runtime: `fintrust/batches.py`, `ledger.py`, `quarantine.py`, `jobs.py`,
  `ingest.py`, `score.py`, `rules.py`, `validators.py`, `local_upload.py`,
  `models.py`, `query.py`.
- Database: `sql/schema.sql`, `sql/migrations/001_transaction_identity.sql`.
- IAM proposal: `infrastructure/iam/create_roles.py`,
  `infrastructure/iam/stage5-ingest-runtime-policy.json`.
- Tests: two new hardening modules, shared `tests/conftest.py`, and the existing
  processing, budget-boundary, cleanup, dashboard and Stage 5 regressions.
- Documentation: this file, architecture, ERD, operations, data governance and
  `infrastructure/DEPLOYMENT_BOOTSTRAP.md`.

No customer data, practice database, ignored credentials, evidence files or
pre-existing untracked project files were staged or deleted. Only the dedicated
local test database received schema/test changes. No cloud resource mutation or
push occurred.

Implementation milestone (local only): `1a0897b97b88ee1e5c7297df46cf02b555f5af7c`.

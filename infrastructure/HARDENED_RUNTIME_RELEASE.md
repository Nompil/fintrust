# Hardened ingest release preparation — NOT READY

Stage 5 infrastructure is live and verified using historical SHA
`d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62`.
Concurrency remains 0; triggers are unwired. Hardened source, migration and the
new candidate below are LOCAL preparation, not live. No AWS mutations, invocation,
new uploads, SQL application, source push or runtime activation occurred.

## Source and tests

Implementation commit 1a0897b97b88ee1e5c7297df46cf02b555f5af7c and documentation
784ab28 are present. No later commit changed fintrust, SQL or dependency files.
Source binding at preparation: e52ca2d9db1e219184b0892126222ec0ab2f0bda.
Compared with the historical ZIP, normalized code changes are:
fintrust/batches.py, fintrust/ingest.py, fintrust/jobs.py, fintrust/ledger.py, fintrust/local_upload.py, fintrust/models.py, fintrust/quarantine.py, fintrust/query.py, fintrust/rules.py, fintrust/score.py, fintrust/validators.py.
Other apparent byte differences are Windows CRLF, recorded separately in evidence.
The archive contains all current fintrust/src Python files, checked byte for byte.

Full current local suite with PostgreSQL: **342 passed, 0 failed, 1 skipped**,
90.62s. Focused ingest/identity/processing/constraints suite: **114 passed, 0
failed, 1 skipped**, 76.03s. The skipped service-role execution test requires a
superuser on a disposable database; the existing local app role cannot create
roles. Tests ran on Windows CPython 3.14 and PostgreSQL 18, not target Linux
CPython 3.12/PostgreSQL 16. Existing tests cover file/row/cross-file identity,
partial publication/replays, concurrent SQL admission, canonical DynamoDB reuse,
conflicts, timestamp precision, duplicate-charge flags, normal and high-risk
admission, structured quarantine, API queries, views and reporting compatibility.
The final full run includes the focused packaging regression: SDK examples are
removed while runtime service models are preserved, the archive checksum is
recomputed and Linux verification cannot be inherited. No skipped test is counted
as passed.

## Exact migration audit

sql/migrations/001_transaction_identity.sql creates **no tables**. It adds seven
nullable columns to transactions, with no defaults and no historical backfill:

| Column | Type | Added constraint |
|---|---|---|
| source_system | varchar(100) | participates in identity CHECK |
| source_transaction_id | varchar(200) | identity CHECK and partial unique index |
| transaction_fingerprint | char(64) | lower-case hex 64-character CHECK; NULL allowed |
| batch_id | uuid | none; no new foreign key |
| file_sha256 | char(64) | lower-case hex 64-character CHECK; NULL allowed |
| source_row | integer | >= 2; NULL allowed |
| country | char(2) | no new country CHECK |

Named CHECK transactions_source_identity_check requires a nonblank source ID to
have a nonnull/nonblank source system. Null IDs remain allowed for seed/legacy
rows. Unique **index**, not a new pg_constraint UNIQUE object:
idx_tx_source_identity on (source_system, account_id, source_transaction_id),
WHERE source_transaction_id IS NOT NULL. idx_tx_duplicate_charge indexes
(account_id, merchant, currency, amount, tx_date) under the same predicate.
There is no unique fingerprint constraint: legitimate similar charges can coexist.
No existing foreign key, NOT NULL, default, type or timestamp precision is changed.

The migration has BEGIN/COMMIT. ADD COLUMN/CREATE INDEX IF NOT EXISTS and the
catalog guard for the named CHECK permit reruns on a matching schema. They do
NOT repair conflicting preexisting definitions. Preflight must compare catalogs,
existing source identity duplicates, nullability and lengths before application.
Index creation is not CONCURRENTLY; schedule controlled maintenance, bound lock
wait and statement duration, pause writers, and preserve errors on transaction
rollback. A failed migration must not be treated as applied.

Local validation created an isolated schema inside fintrust_local_test, loaded
the **pre-hardening parent schema**, seed, views and procedure, applied this
migration twice, and verified the original 200 seed rows remained unchanged.
The isolated schema was removed afterward. The full database suite then tested
current concurrency/replay, unique identity, similar charges, SQL reports/views
and API queries against the dedicated test database. No valuable practice data
or AWS RDS was modified.

Current live RDS schema compatibility is **UNKNOWN**. CREATE_COMPLETE proves an
instance, not initialized tables or service grants. The repository explicitly
says the private migration runner is proposed, not implemented. Do not assume
transactions/processed_transactions exist, or blindly apply current schema.sql
as a substitute for an inspected upgrade. First capture the live catalog and
verify the canonical preconditions and service grants through an approved private
path. The untracked infrastructure/rds/schema.sql was not adopted or changed.

Recovery: if DDL fails before COMMIT, ROLLBACK and retain the previous code/schema.
After successful additive DDL, prefer code rollback and leave nullable columns
and indexes intact. Do not drop identity metadata/constraints automatically.
Take a reviewed backup/snapshot before live migration; restore into a separately
reviewed DB if necessary, rather than destructive in-place downgrading. Backups,
restores and any temporary private runner have cost/security approval gates.

## Candidate artifact and verification limits

Path: build/hardened-release/fintrust-hardened.zip
SHA256: `3b95884caa30bb678d47dbf6fe4993784fae8b958b48a4630b5bd35cec7de29e`
Base64: `O5WITKowu2eNR9v2/kmTeE+ui5WLSKRjC1vTXOx94p4=`
Compressed size: **21626987 bytes**; uncompressed:
35686045 bytes.

Built fresh using the existing package tool plus the focused hardened wrapper and pinned production wheels targeting
manylinux2014_x86_64/CPython 3.12. The shared five-handler layout, native psycopg
ELF/ABI, SQL, CA, frontend, CRC and manifest checks pass. Dependency versions are
unchanged from the historical ZIP. SDK example documentation and public sample keys were excluded; a scan of all
final members found no ignored local secret values, AWS access-key patterns or
private-key headers. Runtime service models remain included.
Existing verified public CA bytes were reused;
the old archive was not reused as the new deployment package. Package inspection
found no tests/docs/project-reference, .env, .aws credential directory, Windows
binaries or dev dependency distributions. Project files are the existing reviewed
source; no credentials were added to them by this preparation.

**Linux execution is NOT verified**. This host is Windows; WSL is not installed
and Docker is unavailable in PATH. The verifier exits before probing with:
`RuntimeError: This verification requires Linux x86_64 and CPython 3.12`.
The new manifest correctly retains linux_execution_verified=false. Do not reuse
historical Linux success as proof for this source. The existing Linux CI can
validate it only after separately authorized source publication, or an approved
local Linux environment is supplied. No CI run for older remote source was used.
The administrator-dependent DB test also needs disposable PostgreSQL 16 CI proof.

Reproduce the candidate locally with:

```powershell
& 'C:\Users\Nompilo\AppData\Local\Programs\Python\Python314\python.exe' tools/package_hardened_lambda.py --ca-bundle build/hardened-release/global-bundle.pem --output build/hardened-release/fintrust-hardened.zip
```

Target verification, on an approved Linux CPython 3.12 x86_64 host only:

```sh
python3.12 tools/verify_lambda_linux.py build/hardened-release/fintrust-hardened.zip
```

Rebuilding on Linux may produce a different hash due to source line endings; if
so bind the manifest, template, object key, release policy and evidence to that
actual verified artifact. Never relabel this candidate as verified.

## Runtime and deployment IAM delta

Live fintrust-ingest-dev has no inline policies and only FinTrustStage5IngestRuntime
v1 attached. Its live document differs from the locally prepared runtime policy.
Required hardened runtime additions already present locally:
- s3:GetObject only on quarantine/batches/*;
- s3:ListBucket only for quarantine/batches/* prefixes;
- kms:Decrypt adds quarantine bucket and batch-object encryption contexts, through
  S3 af-south-1 only and account 966467878406.
Existing raw read/versioned-read, quarantine PutObject, KMS GenerateDataKey,
FIFO/failure SendMessage and exact log-stream writing remain unchanged.
Conditional completion PUT uses the existing PutObject permission.

SendMessageBatch is authorized by **sqs:SendMessage**, not a separate IAM
sqs:SendMessageBatch action. This follows the AWS SQS permission table:
https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-api-permissions-reference.html
No batch-action typo is added. Lambda ingest does not use DynamoDB, Secrets
Manager or SQL at runtime: its queue branch uses check_accounts=false and
track_batches=true. No database/VPC/environment change is required for ingest.
Scoring handles SQL admission, duplicate-charge evaluation and canonical DynamoDB
projection later; shared packaging does NOT deploy or authorize those handlers.

The existing Stage 5 deployer policy lacks UpdateFunctionCode and reads only the
historical object. Proposed supplemental FinTrustStage5HardenedRelease:
[infrastructure policy](iam/stage5-hardened-release-policy.json) permits only
UpdateFunctionCode on this exact ingest function through CloudFormation, exact
new S3 object version reads, and S3-mediated decrypt for this key/object/bucket
context. Region stays af-south-1. It adds no concurrency, trigger, configuration,
async update, delete or general object-write authority. FinTrustStage5Async/v7
remain as proven. Runtime policy replacement and release-policy attachment require
separate administrator approval. The final candidate template passed read-only CloudFormation validation.
Both proposed JSON policies passed Access Analyzer
with zero findings; this does not prove backend context or all resource policies.

Candidate template: build/hardened-release/stage5-hardened-ingest.json. It differs
from the frozen historical template only in IngestFunction.Code.S3Key. The required
CodeObjectVersion parameter gets the later approved upload's returned VersionId.
Expected UPDATE change set: **one Modify IngestFunction, replacement false**;
IngestLogs and IngestAsync unchanged. If async modification appears, STOP: the
current async policy deliberately has no UpdateFunctionEventInvokeConfig grant.

## Safest release order and exact future command plan — NOT EXECUTED

1. Prove Linux imports and the zero-skip target suite first; freeze its exact hash.
2. Review/implement the temporary private-RDS migration/bootstrap path and master
   secret handling; inspect actual schema and grants. No NAT/public DB workaround.
3. Preserve backup and historical ZIP/VersionId; keep concurrency 0/triggers unwired.
4. After explicit IAM approval update runtime policy to reviewed local document,
   and attach the exact release policy to deployer. No IAM version deletion by
   assumption; read current versions and quota again before a future change.
5. Apply reviewed additive migration BEFORE enabling a consumer that needs it.
   Ingest itself does not access DB, but queued schema_version=2 jobs must not be
   delivered to an unreviewed historical scoring consumer. Scoring release and
   activation are separate gates; keep all triggers unwired.
6. Only after release approval upload the verified archive and pin returned version.
7. Prepare/review an UPDATE change set; execute once after separate approval.
8. Verify code/checksum, async settings/logs, concurrency 0, and no triggers.
9. Plan cloud smoke testing separately: concurrency 0 prohibits execution; no
   meaningful positive Lambda invocation can happen without an explicitly approved
   temporary concurrency/activation test plan. Current mock/local tests are not
   live smoke proof. Do not call InvokeFunction during this preparation.

After all blockers and approvals are cleared, these commands apply only if this
exact candidate hash is what Linux verifies. Run from the repository root:

```powershell
$releaseAws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
$releaseManifest = Get-Content build/hardened-release/fintrust-hardened.manifest.json | ConvertFrom-Json
if (-not $releaseManifest.linux_execution_verified) { throw 'Linux verification required before upload' }
$releaseChecksum = 'O5WITKowu2eNR9v2/kmTeE+ui5WLSKRjC1vTXOx94p4='
$releaseKey = 'deployment/lambda/3b95884caa30bb678d47dbf6fe4993784fae8b958b48a4630b5bd35cec7de29e/fintrust.zip'
$upload = & $releaseAws s3api put-object --bucket fintrust-reports-966467878406-af-south-1-dev --key $releaseKey --body build/hardened-release/fintrust-hardened.zip --server-side-encryption aws:kms --ssekms-key-id arn:aws:kms:af-south-1:966467878406:key/598a4158-2cc6-4946-af24-512784a276c8 --checksum-algorithm SHA256 --checksum-sha256 $releaseChecksum --profile fintrust-admin --region af-south-1 --no-cli-pager --output json
if ($LASTEXITCODE -ne 0) { throw 'Upload failed; stop' }
$releaseUpload = $upload | ConvertFrom-Json
$releaseVersion = $releaseUpload.VersionId
if (-not $releaseVersion -or $releaseVersion -eq 'null') { throw 'VersionId missing' }
$head = & $releaseAws s3api head-object --bucket fintrust-reports-966467878406-af-south-1-dev --key $releaseKey --version-id $releaseVersion --checksum-mode ENABLED --profile fintrust-admin --region af-south-1 --no-cli-pager --output json
if ($LASTEXITCODE -ne 0) { throw 'Head verification failed' }
$h = $head | ConvertFrom-Json
if ($h.VersionId -ne $releaseVersion -or $h.ChecksumSHA256 -ne $releaseChecksum -or $h.ContentLength -ne 21626987 -or $h.ServerSideEncryption -ne 'aws:kms' -or $h.SSEKMSKeyId -ne 'arn:aws:kms:af-south-1:966467878406:key/598a4158-2cc6-4946-af24-512784a276c8') { throw 'Artifact mismatch; stop' }
```

Save returned VersionId, checksum and encryption JSON as evidence before proceeding.
The private SQL step is deliberately **not represented by a fake AWS invocation
command**: the approved-path implementation is absent. Once reviewed private
connectivity/credential delivery exists, the SQL client command *inside that
private environment* is:

```sh
psql --no-psqlrc --set=ON_ERROR_STOP=1 --file=sql/migrations/001_transaction_identity.sql
```

Require verified TLS/server hostname, trusted RDS CA, private host and the reviewed
administrator identity/secret supplied in memory, never password literals/history
or logs. Require expected database/schema and catalogs before running; use bounded
lock/statement timeouts. A laptop command alone cannot reach this private RDS.
No exact AWS runner invocation can be approved until that runner exists and its
payload/secret path is reviewed. Do not proceed on an UNKNOWN schema.

After confirmed migration/service-grant readiness and separate change-set approval:

```powershell
& $releaseAws sts get-caller-identity --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $releaseAws cloudformation create-change-set --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-hardened-review --change-set-type UPDATE --template-body file://build/hardened-release/stage5-hardened-ingest.json --parameters "ParameterKey=CodeObjectVersion,ParameterValue=$releaseVersion" --resource-types AWS::Lambda::Function AWS::Lambda::EventInvokeConfig AWS::Logs::LogGroup --tags Key=Project,Value=FinTrust Key=Environment,Value=dev --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $releaseAws cloudformation wait change-set-create-complete --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-hardened-review --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $releaseAws cloudformation describe-change-set --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-hardened-review --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
```

Check every exit code and STOP for review: exactly one Modify IngestFunction,
no replacement, other resources/triggers unchanged. After execution approval only:

```powershell
& $releaseAws cloudformation execute-change-set --stack-name fintrust-ingest-dev --change-set-name fintrust-ingest-hardened-review --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $releaseAws cloudformation wait stack-update-complete --stack-name fintrust-ingest-dev --profile fintrust-deployer-role --region af-south-1 --no-cli-pager
& $releaseAws lambda get-function-configuration --function-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $releaseAws lambda get-function-concurrency --function-name fintrust-ingest-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
& $releaseAws lambda get-function-event-invoke-config --function-name fintrust-ingest-dev --qualifier '$LATEST' --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Require UPDATE_COMPLETE, CodeSha256=O5WITKowu2eNR9v2/kmTeE+ui5WLSKRjC1vTXOx94p4=, runtime/role/network/environment
unchanged, concurrency 0, exact async config, logs and repeated trigger checks.
No automatic retries/IAM broadening. After an approved rollback restore the
historical template and VersionId through a reviewed UPDATE change set; preserve
additive SQL, reconcile pending schema_version=2 messages and batch markers before
any activation. Do not delete quarantine audit records or loosen ledger uniqueness.

## Evidence and blockers

Saved evidence: docs/EVIDENCE/11-ci/hardened-release-*-postgres-tests.xml and
hardened-release-local-tests.json; hardened-release-linux-verifier.log;
docs/EVIDENCE/05-rds/hardened-release-local-migration.json;
docs/EVIDENCE/08-lambda/hardened-release-package-inspection.json,
hardened-release-runtime-iam.json, hardened-release-policy-validation.json.
Ignored build ZIP/manifest/template/logs remain under build/hardened-release/.

Future evidence filenames (do not fabricate):
- 11-ci/hardened-release-linux-verified-manifest.json and linux-verifier-passed.log;
- 05-rds/hardened-release-live-schema-preflight.json, migration-reviewed.png,
  migration-applied.json and service-grants-verified.json;
- 08-lambda/hardened-release-upload-version.json, update-change-set-reviewed.json,
  update-complete.json and code-checksum.json;
- 12-e2e/hardened-release-smoke-plan.md and smoke-result.json, only after separately
  approved controlled activation/invocation.

**HARDENED RUNTIME NOT READY**: Linux CPython 3.12 handler/native import proof and
a zero-skip PostgreSQL 16 suite are missing; the private-RDS runner/credential path
is not implemented and live schema/grants are unverified. Local tests/build and
IAM proposals are prepared. Historical disabled Stage 5 infrastructure remains
verified; no hardened AWS release has occurred.

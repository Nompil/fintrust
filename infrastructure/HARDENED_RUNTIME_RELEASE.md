# Hardened ingest release - LINUX RELEASE VERIFIED; AWS RELEASE BLOCKED

## Current verified release checkpoint

[GitHub Actions run 37850256137](https://github.com/Nompil/fintrust/actions/runs/37850256137)
passed after the approved push of source commit
`5385c581e76ae1c0d486e569b6beb4c6b67d548c` to origin/main.
The authoritative build used Ubuntu 24.04, Linux x86_64, CPython 3.12.15 and
disposable PostgreSQL 16.15. Full tests: **385 passed, 0 failed, 0 skipped**
in **13.39 seconds**. Both archived-policy integrity checks and the administrator
required database-role test ran and passed; original historical hashes remain intact.

The exact Linux-built ZIP passed content/security and source binding checks,
all five handler imports, all production-module imports, native PostgreSQL and
MarkupSafe dependency loads, SQL/CA checks, and manifest/checksum checks.
No outbound network operations occurred during the import probe; its existing
exact urllib3 IPv6 loopback capability-check exception remained unchanged.
The content gate rejected Windows executables/PE files, launchers, development
material, .env files and credential patterns while accepting dependency-internal
Python modules such as boto3/docs. These are scoped checks, not a general secret audit.

Authoritative artifact:

- Filename: `fintrust-hardened-linux-py312.zip`
- Size: **21,372,233 bytes**
- SHA256: `cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654`
- Base64 SHA256: `z5wYpfJnNz4vwuIjMZh7ttzo4uZTZrLR9WUbsDXdZlQ=`
- Published artifact: `fintrust-hardened-linux-py312` (ID `11581842656`)
- `linux_execution_verified = true`
- `release_gate_passed = true`

The workflow published the verified ZIP, manifest with checksums, and verification
evidence. The downloaded ZIP was independently rechecked locally for checksum,
base64 checksum, size, content/layout and source binding without rebuilding.
Local artifact: `build/hardened-release/fintrust-hardened-linux-py312.zip`.
Run evidence, manifest, JUnit results, import output, computed checksums and receipt:
[docs/EVIDENCE/11-ci/37850256137](../docs/EVIDENCE/11-ci/37850256137/local-release-receipt.json).
GitHub artifacts have the workflow's 30-day retention; preserve the local copy.

The old Windows-built `fintrust-hardened.zip`, SHA256
`3b95884caa30bb678d47dbf6fe4993784fae8b958b48a4630b5bd35cec7de29e`, is
**SUPERSEDED - contained Windows launcher executables**. Its bytes and original
unverified manifest are preserved; verification flags apply only to the new Linux ZIP.

This closes the Linux release gate, not the AWS deployment gate. No AWS access,
upload, migration, invocation, concurrency change or trigger wiring occurred in
this CI task. The private RDS migration path and live schema/grants remain pending.
The existing release template/IAM proposal still references the superseded
Windows candidate; rebinding it to this Linux artifact and a future S3 VersionId
requires a separate focused review before any AWS upload or deployment.
The post-run documentation/evidence commit is local only and is not pushed.

## Historical preparation record

The following sections retain the earlier preparation and failed-run evidence.
Their candidate identifiers, counts and pending statuses describe those checkpoints;
the current verified Linux checkpoint above supersedes their release-gate status.

Stage 5 infrastructure is live and verified using historical SHA
`d645d8949ee5b128b2b5c4c1558dd61a1a5c0fd3cdeace60363b19f70d167d62`.
Concurrency remains 0; triggers are unwired. Hardened source, migration and the
new candidate below are LOCAL preparation, not live. No AWS mutations, invocation,
new uploads, SQL application, source push or runtime activation occurred at that
historical preparation checkpoint.

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

## Safest release order and exact future command plan â€” NOT EXECUTED

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

## Isolated Linux verification environment checkpoint

Checked the exact candidate ZIP without rebuilding or uploading it. Its SHA256
remains `3b95884caa30bb678d47dbf6fe4993784fae8b958b48a4630b5bd35cec7de29e`
and base64 remains `O5WITKowu2eNR9v2/kmTeE+ui5WLSKRjC1vTXOx94p4=`.

No Docker, Podman or QEMU executable was found on PATH or the checked standard
installation paths. No Docker, Linux distribution or VM runtime appeared in the
checked installed-program records. WSL explicitly reports it is not installed.
The available host is Windows AMD64, CPython 3.14.7. The existing verifier exits
1 at its host prerequisite: `This verification requires Linux x86_64 and CPython
3.12`. Handler/module/native imports therefore did not run; this is not evidence
of an artifact incompatibility. `linux_execution_verified` remains false.

Exact host-check evidence and verifier stdout/stderr are recorded in
`docs/EVIDENCE/11-ci/hardened-release-linux-environment-check.json`. No application,
dependency, ZIP, manifest, AWS resource or private-database migration was changed.
No tests were rerun because only evidence/documentation changed. No tooling was
installed: installing a Linux environment requires a separate user decision,
as requested. After an approved Linux CPython 3.12 x86_64 environment is available,
run the existing verifier against this exact ZIP and additionally check every
packaged production module before declaring this release verified.

**LINUX VERIFICATION BLOCKED â€” no installed Linux CPython 3.12 x86_64 execution
path is available on this host.**

## Authoritative release process: Linux CI builds and verifies

**GitHub Actions Linux CPython 3.12 builds the release artifact. The same job
verifies the exact artifact it built. Only a CI-verified artifact may proceed
to AWS deployment.** WSL remains optional and paused; Docker is not required.

Current preparation is READY FOR PUSH, not evidence of a successful Linux build.
An explicit push approval is still required. The invalid Windows ZIP is not
transferred, tracked or rebuilt locally. The earlier exact-local-ZIP transfer
plan is replaced by this source-to-Linux-build process.

### Why the Windows archive contained executables

`tools/package_lambda.py` runs the host Python's pip with CPython 3.12/Linux
wheel-selection flags and a target staging directory. Those flags select wheels;
they do not change the host operating system used to generate console scripts.
The installed pip/distlib ScriptMaker sets `_is_nt` from the host `os.name` and
writes `.exe` launchers on Windows. The packager then archives every staging
file, including `bin/dotenv.exe` and `bin/flask.exe`. Their MZ signatures were
confirmed. Neither launcher is needed by Lambda to import dotenv or Flask.

The hardened wrapper now removes every `bin/` console launcher on all hosts,
plus existing SDK example material. Linux CLI scripts are unnecessary too.
Underlying Python packages, distribution metadata, service models and native
extensions are preserved. Regression tests prove both host launcher variants
are omitted and checksums are recomputed. Dependencies and application code
are unchanged; this remains the existing shared five-handler production package.

### One existing workflow, one authoritative artifact

`.github/workflows/ci.yml` reuses Ubuntu 24.04 x86_64, setup-python CPython 3.12
x64 and disposable PostgreSQL 16. Its stages are:

1. Checkout source with credential persistence disabled and assert OS/architecture/Python.
2. Fetch the public RDS CA trust bundle and build from pinned `requirements-lambda.txt`
   production wheels with `tools/package_hardened_lambda.py`. Test dependencies
   are not installed at this point and cannot enter the ZIP staging directory.
3. Generate `build/hardened-release/fintrust-hardened-linux-py312.zip` and its
   manifest using ordered members/fixed ZIP metadata. Repeatability assumes
   identical source, wheel and CA inputs; changes in those inputs change hashes.
4. Check hash against the build manifest before extraction; archive layout/CRC,
   first-party source binding, forbidden config/development files, CLI launchers,
   Windows file suffixes and MZ signatures, plus access-key/private-key patterns.
   This scoped scan is not a guarantee for every conceivable secret format.
5. Run `tools/verify_lambda_linux.py --all-production` against that same archive.
   All five handlers, every packaged fintrust/src module, production dependency
   entry packages, psycopg2._psycopg and markupsafe._speedups load from the extracted
   archive. SQL and CA trust loading are checked. Existing DNS/socket audit
   controls remain, including only the attributed urllib3 capability bind exception.
6. Install test-only dependencies outside the ZIP, then run the full suite with
   PostgreSQL 16, including duplicate/identity/replay/quarantine/precision tests,
   SQL admission/concurrency and service-role permission tests. No failed/error/
   skipped test is accepted by the release gate.
7. Record actual commit/run URL/timestamp, OS/architecture/Python, filename, SHA256
   hex/base64, size, handler/module/native results and JUnit totals. Re-hash the
   final ZIP before publication and compare it to the verified manifest.
8. Preserve failure/success evidence in `fintrust-hardened-verification-evidence`.
   Publish the ZIP only after all gates pass in `fintrust-hardened-linux-py312`,
   with manifest, JSON/Markdown evidence, import output and JUnit XML. Retention
   is 30 days; download successful artifacts/evidence promptly for release storage.

The GitHub token has only contents:read. There are no repository-secret inputs,
OIDC/deployment permissions, AWS CLI/API commands, AWS uploads or live invocations.
Literal testing credentials and disabled metadata discovery support mocked tests.
Database tests connect only to the disposable CI PostgreSQL service. The package
probe rejects network operations; package indexes/public CA download are build
inputs, not AWS account access. Concurrency/triggers/private RDS remain untouched.

### Pending actual execution and supersession

The old ZIP SHA256 is still
`3b95884caa30bb678d47dbf6fe4993784fae8b958b48a4630b5bd35cec7de29e`, with base64
`O5WITKowu2eNR9v2/kmTeE+ui5WLSKRjC1vTXOx94p4=` and
`linux_execution_verified=false`. It is NOT RELEASE-READY. After a successful
Linux build, record its replacement checksum/run URL here and label the old ZIP
`SUPERSEDED — contained Windows launcher executables`. Do not claim that transition
before the workflow actually runs. No authoritative replacement hash exists yet.

Any deployment template/IAM artifact path/checksum binding still referencing the
Windows candidate must be updated in a separately reviewed release step using
only the downloaded CI-verified artifact. Preparation does not authorize upload,
IAM changes, private RDS migration, deployment or activation.

Local validation: 48 focused tests passed, 0 failed, 0 skipped on Windows Python
3.14.7; YAML, Python syntax, workflow stage order, build/test separation, runner/
service configuration and read-only permissions checked. These are preparation
checks, not Linux execution proof. Evidence:
`docs/EVIDENCE/11-ci/hardened-linux-build-preparation.json`.

A push is required because the reviewed source/workflow is not yet on GitHub.
After separate approval, push the reviewed commits; the existing main push trigger
runs the job. Manual rerun command, if needed after that approved push:

```powershell
gh workflow run ci.yml --repo Nompil/fintrust --ref main
```

**LINUX BUILD PIPELINE READY FOR PUSH.**

## CI run 37847686705: path-classification correction

**CI packaging verification failed due to an over-broad content classification
rule; Linux build itself succeeded.** Actual run:
https://github.com/Nompil/fintrust/actions/runs/37847686705
Source commit: `0804fd86ba9661d0bf507085f5bd7d1f75cc9424`.
Ubuntu 24.04 x86_64, CPython 3.12.15 and PostgreSQL 16.15 were confirmed.
The gate rejected `boto3/docs/__init__.py` before imports/tests; no release ZIP
was published, only failure evidence. Candidate SHA256
`cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654`
is NOT release-approved; execution remains false.

Root cause: the verifier treated any `docs` path segment as repository material.
The corrected rule rejects top-level `docs/` and docs nested in first-party
`fintrust/` or `src/`; dependency-internal Python modules are not rejected merely
for a `docs` segment. This is path-aware, not a special filename allowance.
The pinned boto3 1.43.104 installed distribution RECORD hash matches that member,
and boto3 resources/action.py and dynamodb/transform.py import boto3.docs modules.
The upstream module is documented at
https://github.com/boto/boto3/blob/develop/boto3/docs/__init__.py .
The failed CI ZIP was not published; distribution provenance was checked against
local pinned distribution/retained package plus the actual CI failure evidence,
not by claiming a download of that CI ZIP. No dependency files were removed.

Every archive member still undergoes Windows suffix/MZ, credential, private-key,
.env, cache, unsafe path and unwanted CLI checks. Existing project tests and
pytest/moto exclusions remain. `.github` is explicitly rejected too. The checksum,
layout, source binding, native import, full-test and zero-skip gates are unchanged.
No workflow/build strategy, application code or dependencies were changed.

Local regression result: **63 passed, 0 failed, 0 skipped** (3.94 seconds), including
legitimate nested docs, repository docs/tests, both Windows launchers, hidden MZ,
.env/credential patterns inside dependency docs, and unrelated development material.
Evidence: `docs/EVIDENCE/11-ci/hardened-content-gate-correction.json`.
A separately approved push/rerun is required. `linux_execution_verified` is still
false; the Windows candidate is still not release-ready and supersession awaits
a fully successful Linux artifact. No AWS access, rebuild, push or CI rerun occurred.

**CI CONTENT GATE FIX READY FOR RERUN.**

## CI run 37848817090: historical policy byte representation

The Linux build, content gate, five handlers, all production modules and native
extensions passed; network attempts were empty. Full CI tests were 372 passed,
2 failed, 0 skipped (14.21s). Both failures were historical policy SHA assertions,
not runtime package failures. The release ZIP was not published. Archived run
JSON truthfully records import-only `linux_execution_verified=true` alongside
`release_gate_passed=false`; the release remains unapproved. Do not rewrite that
run evidence to imply either a release pass or an import failure.

`core.autocrlf=true` stores LF Git blobs and checks them out as CRLF on Windows.
The original evidence recorded raw Windows bytes, while Linux hashed LF bytes:

| Immutable policy | Recorded Windows CRLF SHA256 | Git/Linux LF SHA256 |
|---|---|---|
| stage5-deployment-diagnostic3-policy.json | bc51f45a07560c6a2f11adebb6db721a1303eff62b871d0d3a6aa7f69b257c48 | b4bc2ca9fe33396548c402d0ac42d008477a661b7d26806bfa015d6fd8d8a84f |
| stage5-deployment-tagloggroup-diagnostic-policy.json | 7ccef683b4e4da11aa85c9c1fdc25fd8216b1dbd5eddc4e3aea06a56641e06e6 | e4dc5766884cef1895d667065bf94e715bcb6e9b63cfeb6a66fd5582279eb7e4 |

The v5 policy is unchanged since fb75a47; the diagnostic candidate, validation
record and version baseline are unchanged since 9c5d215. Current Git blobs match
their first committed bytes exactly; current Windows content differs only in
newlines. The later e14b6af test adjustment accommodated the reviewed canonical
v7 addition without changing the historical policies or evidence.

The second recorded digest binds to the immutable 9c5d215 diagnostic candidate,
not the mutable canonical policy. The original candidate/v5 hashes and evidence
remain untouched. A test-local helper reconstructs original CRLF bytes before
hashing on either OS. It does not parse/reformat JSON or disregard whitespace,
key/statement order, actions, resources or conditions. Regression tests check LF
and CRLF against the same original hashes; substantive and formatting mutations
still change the hash. New canonical versions cannot replace historical bindings.

Focused tests: both original failures passed (2 tests); entire module 29 passed;
related evidence/authorization suite 93 passed. Full local result is recorded in
`docs/EVIDENCE/11-ci/archived-policy-integrity-correction.json` after completion.
No application, packaging/workflow, dependency, artifact or IAM files were changed.
No AWS access, rebuild or push occurred. A separately approved CI push/rerun is
required; `release_gate_passed` stays false pending that run.

Full local suite: **384 passed, 0 failed, 1 skipped**, 96.57s, on Windows
CPython 3.14.7 and PostgreSQL 18. The existing service-role execution test requires
a disposable database superuser and remains skipped with the restricted local
role; this is not counted as passed. Linux CI must still pass with zero skips.

**ARCHIVED POLICY INTEGRITY FIX READY FOR CI RERUN.**

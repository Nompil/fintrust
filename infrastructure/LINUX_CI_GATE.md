> Retained engineering evidence and procedure snapshot. Current navigation: [operations](../docs/OPERATIONS.md) and [evidence register](../docs/EVIDENCE/README.md). Preparation does not establish execution.

# Linux verification gate

Status: **PREPARED; LINUX EXECUTION NOT YET VERIFIED.** No remote is configured.
No repository creation, push, GitHub run or AWS account access occurred.

## Pre-push review

Reviewed all 27 existing commits and 231 reachable file versions across local
refs, including extracted PDF text. Pattern checks covered AWS access keys,
GitHub/API tokens, private-key headers, password assignments and PostgreSQL URLs.
Candidate matches were reviewed: configuration placeholders, disposable test
credentials, code references and an old workflow permission. Actual credential
values from the ignored local `.env` did not appear in reachable Git objects.
No live secrets were detected. This is a scoped review, not a guarantee that
arbitrary secret formats can be identified.

The tracked `.env.example` is a placeholder template. The two tracked PDFs in
`output/pdf/` are intentional presentation deliverables and are retained.
No generated Lambda ZIPs/manifests, local database files, AWS credential files,
private keys, IDE state, logs or Python caches were found in tracked content or
reachable history. `.env`, `build/fintrust.zip` and its manifest are ignored.
Ignore rules now also cover local AWS/editor directories, logs, temporary files,
database files and misplaced FinTrust package outputs. No tracked file is hidden
by these rules. No secret-related cleanup or history rewrite is indicated by
this review. Keep local configuration out of future commits; never force-add it.

These pre-existing untracked files remain outside this change and outside a push:

- `infrastructure/DEPLOYMENT_READINESS.md`
- `infrastructure/rds/schema.sql`
- `project-reference/completed_work.md`
- `project-reference/component_guide.md`
- `project-reference/live_demo_script.md`
- `project-reference/local_software_setup.md`
- `project-reference/presentation_notes.md`

Review those separately before staging them. No local data or presentation files
were deleted. The redundant `.github/workflows/deploy.yml` was removed after its
verification steps were consolidated into `ci.yml`; it was not a deployment
workflow. Historical versions remain in Git.

## Workflow

[FinTrust Linux verification](../.github/workflows/ci.yml) runs manually, on pushes
to `main`, and on pull requests targeting `main`. One Ubuntu 24.04 x64 job uses
Python 3.12, a 20-minute timeout and cancellation of superseded runs on the same
ref. The GitHub token has only `contents: read`; checkout does not persist it.
There is no OIDC permission, AWS credential action, repository secret reference,
AWS CLI command, infrastructure application, trigger enablement or Lambda upload.
The literal `testing` credentials prevent SDK credential discovery; they cannot
authenticate to AWS. AWS interactions in the suite use mocks.

Steps:

1. Check out source and select Python 3.12 x64.
2. Install the existing approved dependencies from `requirements.txt`.
3. Run `python3.12 -m pytest -q --junitxml=test-results/pytest.xml` against a fresh
   PostgreSQL 16 service. Its public test password is confined to that disposable
   service. All database tests run, including the administrator-dependent role
   test that is skipped on the developer's restricted local database.
4. Download the public RDS CA bundle over HTTPS and build `build/fintrust.zip`
   with the existing pinned Linux dependency list. This HTTP download requires
   no AWS credentials and makes no AWS account API call.
5. Run the existing Linux verifier, retaining its output. It checks CPython 3.12,
   x86_64, handlers, archive CRC/sizes/digests and manifest, then imports all five
   archived handlers and native psycopg in an isolated subprocess. It checks
   module locations, SQL, CA loading and checksum, and rejects DNS/socket
   operations through its audit hook. This hook is not an OS network sandbox.
6. Require successful verification and a nonempty JUnit report with zero failures,
   errors or skips. Record commit SHA, run ID/attempt, test counts and the full
   package manifest in `build/ci-evidence.json`, and write a run summary.
7. Retain JUnit results even after failure. Only a successful gate publishes the
   verified ZIP, matching manifest, verifier log and CI evidence as the
   `fintrust-linux-verified` GitHub artifact. Both artifacts expire after seven
   days. Download evidence before expiry; nothing is uploaded to AWS.

Dependency/action downloads and artifact storage require internet access.
GitHub Actions usage is subject to the private repository's plan and limits.
There is no scheduled run or deployment job.

## Running after separate repository/push approval

Once the workflow is on the private repository's default branch, open **Actions
> FinTrust Linux verification > Run workflow** and select the reviewed branch.
The first push to `main` already triggers a run, so do not start another unless
needed. GitHub requires `workflow_dispatch` to be on the default branch for
[manual execution](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
The database follows GitHub's
[PostgreSQL service-container pattern](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers).

The verification command is:

```sh
python3.12 tools/verify_lambda_linux.py build/fintrust.zip
```

It must exit zero and print:

```text
All five archived handlers imported on Linux CPython 3.12.
```

The resulting manifest must contain `linux_execution_verified: true` and actual
platform/probe evidence. The later CI summary must print:

```text
Linux execution verified: TRUE
```

The unchanged suite currently collects 159 tests: CI is expected to pass all 159
with no skips because its database administrator can run the role test. That
expectation is not execution evidence. Any failed or skipped test blocks the
gate. Retain the green run URL, commit SHA and artifacts together.

CI rebuilds the archive from the checked-out commit. Its checksum may differ
from the Windows-built archive; the manifest must match the exact CI artifact.
Never attach a successful manifest to a different ZIP. Every rebuild requires
verification again. Ubuntu proves Linux imports, not the exact Lambda Amazon
Linux 2023 environment or AWS integration.

## Current validation and next boundary

Local full suite: **158 passed, 0 failed, 1 skipped**. The skip remains the
administrator-dependent role test. Workflow YAML and embedded Python parse;
credential boundaries and whitespace checks pass. The GitHub job itself has not
run, and no Linux verification success is claimed.

Remaining blockers: an approved private repository/remote/push, an enabled
GitHub Actions runner with sufficient allowance, and a successful run with its
matching package evidence. Once those checks pass, the next status can be
**READY FOR READ-ONLY AWS INVENTORY**, subject to separate inventory authorization.
Deployment, spending, real parameters and cloud integration gates remain open.

Stop here. Do not create a repository, configure a remote, push or access AWS
without separate approval.

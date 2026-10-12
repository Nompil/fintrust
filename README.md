# FinTrust: Transaction Insights and Risk Monitoring

FinTrust validates transaction CSVs, maintains a PostgreSQL ledger, calculates repeatable risk results and prepares high-risk email alerts and monthly reports. The repository implements the processing components and local analyst dashboard. AWS foundation stages 1–4 are recorded as verified; complete application integration and live SQL bootstrap remain pending. The restructured application passed local assurance. Historical artifacts remain preserved; a new candidate built from the current source requires a fresh Linux Python 3.12 execution gate before deployment.

The configured cloud path is S3 ? ingest ? SQS FIFO ? private scoring ? PostgreSQL and immutable DynamoDB projections ? DynamoDB Streams ? alert delivery through SES. The local CSV demonstration uses a direct SQL helper. It does not demonstrate the cloud queue path.

Open the [current presentation pack](docs/presentation/FinTrust_Project_Planning_and_Design_Evidence.pdf) for the seven authoritative diagrams, speaker notes and live script.

## Repository architecture

```text
frontend/       browser UI; entries, js/, css/
backend/        fintrust/, migration_runner/, src/ runtime packages
sql/            PostgreSQL schema, migrations, seeds and reporting SQL
infrastructure/ AWS definitions and scoped IAM policies
tests/          automated verification and test fixtures
tools/          local operational/developer tools
docs/           architecture, operations, presentation and existing EVIDENCE/
build/          generated deployment artifacts and isolated verification output
```

The Python package names and Lambda handlers remain stable; source location changes do not constitute deployment. Local tools select backend/ explicitly; for direct module use set PYTHONPATH to the absolute backend directory. Pytest and CI declare the same source root. See the [exact move map and path contracts](docs/architecture/REPOSITORY_STRUCTURE.md) and [authoritative flow/gap matrix](docs/architecture/FINTRUST_FLOW_AUDIT.md).

```text
Risk Analyst -> CSV -> input S3 -> ingest parsing -> SQS FIFO candidates
  -> consumer validation -> invalid: quarantine -> correct/revalidate
  -> valid: SQL transaction + frozen Low/Medium/High risk result
       -> DynamoDB projection -> High-risk alert -> SES
       -> Medium/High durable review -> Analyst decision
SQL/DynamoDB -> authenticated query API -> Transactions / Insights / Reports / Audit
EventBridge -> report Lambda -> report S3
Technical failure -> bounded retry / DLQ -> Maintainer investigation / redrive
```

This describes implemented components and intended cloud wiring. The local upload path uses mocked AWS and direct consumer processing, so it is not proof of live queue transport. Review creation does not depend on successful email. No new domain semantics were introduced by the structure cleanup.

## Canonical documentation

| Document | Purpose |
|---|---|
| [Architecture](docs/architecture.md) | Current components, flow, service choices and design gaps |
| [Security](docs/SECURITY.md) | Identity, database roles, network boundaries and sensitive data |
| [Operations](docs/OPERATIONS.md) | Local setup, Linux gate, failures, retention and cost controls |
| [Presentation guide](docs/PRESENTATION_GUIDE.md) | Study path, demonstration limits and questions to prepare for |
| [Diagram register](docs/diagrams/README.md) | Seven final views, retained assets and export status |
| [Evidence register](docs/EVIDENCE/README.md) | Recorded checks, missing proof and evidence retention |

Reuse the existing lowercase `docs/architecture.md` and `docs/diagrams/`; do not create case-only duplicates. Supporting contracts are the [ERD](docs/erd.md), [API design](docs/api_design.md) and [infrastructure entry points](infrastructure/README.md).

## Run locally

Install PostgreSQL and the dependencies in `requirements.txt` in your Python environment. Run each command from this repository root:

```powershell
py -m pip install -r requirements.txt
py tools/local.py test
py tools/local.py setup
py tools/local.py check
py tools/local.py test --database
py tools/local.py ingest
py tools/local.py serve
```

Setup prompts for the local administrator password without storing it; application settings go into ignored `.env`. Practice uses `fintrust_local`, tests use `fintrust_local_test`, and AWS exercises are mocked. Use the local helper's displayed browser address. See operations for the Linux verification and cloud authorization boundaries.

Repository hardening regression: **731 passed, zero failed, 1 skipped**. The administrator-only role test is covered separately by the disposable PostgreSQL 16 service-role proof. Browser workflow, module imports, moved asset URLs, SQL bootstrap/migrations and offline packaging/source binding passed. See [verification evidence](docs/EVIDENCE/12-e2e/repository-hardening/verification-summary.json). No new Linux execution or live AWS integration success is claimed.

## Documentation inventory and disposition

Historical files remain in place. ARCHIVE below is a proposed disposition, not an action performed. No historical files were deleted, moved or archived. Durable current information from MERGE sources is now in the canonical guides; their original details remain available.

| Existing document / group | Classification | Current destination or purpose |
|---|---|---|
| `README.md`; `docs/architecture.md` | CANONICAL | Navigation and system architecture |
| `docs/SECURITY.md`; `docs/OPERATIONS.md`; `docs/PRESENTATION_GUIDE.md` | CANONICAL | Security, operation and presentation |
| `docs/erd.md`; `docs/api_design.md` | CANONICAL | Supporting schema and API contracts |
| `docs/diagrams/README.md`; `docs/EVIDENCE/README.md` | CANONICAL | Asset and evidence registers |
| `infrastructure/README.md` | CANONICAL | Local rendering entry points and legacy-tool boundaries |
| `infrastructure/READ_ONLY_INVENTORY.md`; `infrastructure/OPERATOR_PARAMETERS.md` | CANONICAL | Supporting unexecuted runbook and blank worksheet |
| `tests/data_quality/README.md` | CANONICAL | Test-specific instructions |
| `project-reference/HANDOFF.md`; `project-reference/README.md` | CANONICAL | Maintainer resume point and historical reference index |
| `docs/system_design.md` | MERGE INTO CANONICAL | Architecture, security, operations and presentation; retain original SDLC history |
| `docs/iam_role_matrix.md` | MERGE INTO CANONICAL | Security; old role assumptions are historical |
| `docs/data_governance.md`; `docs/day3_resilience.md` | MERGE INTO CANONICAL | Security and operations; distinguish proposed retention from implemented behavior |
| `infrastructure/BUDGET_FIRST.md` | MERGE INTO CANONICAL | Architecture, security and operations; preserve original decision record |
| `infrastructure/FINAL_VERIFICATION.md`; `infrastructure/LINUX_CI_GATE.md` | KEEP AS EVIDENCE | Offline results and scoped pre-push/CI preparation record |
| `docs/rubric_checklist.md` | KEEP AS EVIDENCE | Requirements mapping; completion needs evidence register, not a checked box alone |
| `project-reference/daily_log.md` | KEEP AS EVIDENCE | Historical engineering progress; not current architecture authority |
| `project-reference/requirements_day1_day3.md` | ARCHIVE | Original milestone requirements; pending approval to archive |
| `project-reference/upcoming_features.md` | ARCHIVE | Superseded feature status; current gaps are in canonical guides |
| `project-reference/learning_guide.md` | MERGE INTO CANONICAL | Current command summary in operations; retain original detailed learning exercises |
| `project-reference/completed_work.md` (untracked) | ARCHIVE | Earlier completion snapshot; preserve and review before any staging |
| `project-reference/component_guide.md` (untracked) | MERGE INTO CANONICAL | Architecture/service explanation; original prototype status is outdated |
| `project-reference/live_demo_script.md`; `project-reference/presentation_notes.md` (untracked) | MERGE INTO CANONICAL | Presentation guide; preserve original material |
| `project-reference/local_software_setup.md` (untracked) | MERGE INTO CANONICAL | README/operations command summary; original machine-specific instructions retained |
| `infrastructure/DEPLOYMENT_READINESS.md` (untracked) | ARCHIVE | Earlier audit with superseded placement assumptions |
| `docs/presentation/*.pdf`; `docs/presentation/diagrams/`; `docs/presentation/diagram-source/`; `docs/EVIDENCE/12-e2e/historical-design-diagrams/` | KEEP | Current seven views and separately archived historical exports |
| `docs/diagrams/aws-icons/` | CANONICAL | Reusable source assets with attribution |
| `infrastructure/rds/schema.sql` (untracked) | REMOVE LATER AFTER REVIEW | Older duplicate; runtime schema authority is `sql/schema.sql`. No deletion performed. |

After review, historical MERGE sources can also be archived with approval. None must be deleted to use the canonical set. The seven pre-existing untracked files remain unstaged and outside these documentation commits.

## Maintenance policy

Update the relevant canonical guide with each major change to architecture, permissions, data flow or recovery behavior. Use the evidence register for results and the existing daily log for historical progress. Do not add another checkpoint/readiness/planning document unless it covers a genuinely new subject that cannot fit an existing guide.

Keep claims specific: implemented in code, prepared but unexecuted, or verified by linked evidence. Do not invent deployment results, performance measurements or personal experience. Keep stakeholder prose plain, project-specific and free of dates or assistant instructions. Historical engineering records retain their original context.

Maintain the seven final diagram views in the register. Before presentation, reconcile diagrams and PDF generators with canonical content; after AWS verification, reconcile them with actual configuration and evidence. Open PDFs in a PDF reader rather than a text editor.

Repository creation, remote configuration, push and AWS access remain outside the current authorization. Documentation preparation does not authorize deployment or spending.

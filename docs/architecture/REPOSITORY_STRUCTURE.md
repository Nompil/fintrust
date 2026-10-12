# Repository structure and safe path contract

Before: runtime code was split between root `fintrust/`, `migration_runner/` and `src/`; frontend scripts/styles were flat. After: runtime packages are in `backend/`; browser scripts/styles have dedicated subfolders. Existing package internals remain cohesive rather than being split into invented abstractions.

| Current concern | Location |
|---|---|
| Browser entries | frontend/index.html, frontend/release1.html |
| JavaScript / styles | frontend/js/, frontend/css/ |
| API, services, authentication, validation, scoring, DB access | backend/fintrust/ (existing Python package retained) |
| Temporary fixed-phase migration runner | backend/migration_runner/ |
| Existing legacy Lambda entry adapters and logger | backend/src/ |
| PostgreSQL bootstrap, migrations, seed, reporting SQL | sql/ (unchanged checked SQL contracts) |
| AWS resources and IAM | infrastructure/ (unchanged deployment resource/handler contracts) |
| Automated verification / fixtures | tests/ (existing cross-test fixtures retained) |
| Local/developer tools | tools/ |
| Architecture / operations / presentation / history | docs/ and retained project-reference/ |
| Evidence | docs/EVIDENCE/ (same hierarchy) |
| Generated packages, isolated environments, old source snapshots | build/ |

## Import, resource and packaging contract

Local tools explicitly add the backend source root; pytest.ini declares `backend` and the repository root. CI uses PYTHONPATH to select its own checked-out backend. This is a standard source layout, not an old-location import shim. Python names (`fintrust.*`, `migration_runner.*`, `src.*`) and Lambda handler names remain unchanged. No duplicate application source remains in the old root locations. Existing `src` adapters are retained because they predate this move and preserve existing documented entry contracts.

Lambda archives still flatten application packages to `fintrust/`, `src/` or `migration_runner/`, with frontend/SQL/cert resources at archive root. Builders read from backend/ but do not introduce backend-prefixed handlers. Source binding compares repository files with their intentional archive names. Resource-root resolution explicitly supports these two layouts: repository backend source and Lambda flat archive. Historical ZIPs, checksums and uploaded VersionIds are unchanged. A new candidate requires a new Linux execution gate; a historical gate cannot certify moved/changed source.

Frontend URLs now use `/assets/js/...` and `/assets/css/...`; the existing generic asset route serves those files from the resource root. No new framework or page architecture. A running pre-move Python process must be restarted to load the changed resource-root constant. Use `python tools/serve_release1.py --role Analyst --reuse-auth`; preserve the existing ignored credential file. No reset/seed is required.

SQL, IAM, fixture identities and checksums remain unchanged. Tests keep their existing placement because splitting them would needlessly change shared fixture imports. Infrastructure and canonical docs remain in their existing locations to preserve runbooks and historical links, especially four dirty user deployment notes. No empty target folders were invented.

## Classification and disposition

- Source moved: runtime packages and browser script/style files (table below).
- Generated artifacts: build packages, copied source snapshots, virtual environments, native toolchains, tmp render checks and caches. Identified and retained; no historical release deleted.
- Historical evidence: docs/EVIDENCE and project-reference retained byte-for-byte where unrelated.
- Obsolete candidates: legacy app.js/styles.css are not the current release1 entry; src entry adapters are historical compatibility contracts. Kept, clearly identified, not silently removed.
- Duplicate documentation: historical planning/runbook material stays in place; current flow authority is FINTRUST_FLOW_AUDIT.md. Do not rewrite or remove user evidence merely to achieve a tidy tree.
- Residual old package directories contain only ignored Python caches, not runtime .py source. No destructive cache cleanup was needed.

## Exact move map

| Old source | New source |
|---|---|
| fintrust/__init__.py | backend/fintrust/__init__.py |
| fintrust/alert.py | backend/fintrust/alert.py |
| fintrust/alert_delivery.py | backend/fintrust/alert_delivery.py |
| fintrust/api.py | backend/fintrust/api.py |
| fintrust/auth.py | backend/fintrust/auth.py |
| fintrust/batches.py | backend/fintrust/batches.py |
| fintrust/config.py | backend/fintrust/config.py |
| fintrust/db.py | backend/fintrust/db.py |
| fintrust/dynamo.py | backend/fintrust/dynamo.py |
| fintrust/file_admission.py | backend/fintrust/file_admission.py |
| fintrust/frontend_workflows.py | backend/fintrust/frontend_workflows.py |
| fintrust/ingest.py | backend/fintrust/ingest.py |
| fintrust/jobs.py | backend/fintrust/jobs.py |
| fintrust/ledger.py | backend/fintrust/ledger.py |
| fintrust/local_upload.py | backend/fintrust/local_upload.py |
| fintrust/local_users.py | backend/fintrust/local_users.py |
| fintrust/migrations.py | backend/fintrust/migrations.py |
| fintrust/models.py | backend/fintrust/models.py |
| fintrust/operations.py | backend/fintrust/operations.py |
| fintrust/pagination.py | backend/fintrust/pagination.py |
| fintrust/quarantine.py | backend/fintrust/quarantine.py |
| fintrust/query.py | backend/fintrust/query.py |
| fintrust/release_contract.py | backend/fintrust/release_contract.py |
| fintrust/release_ingest.py | backend/fintrust/release_ingest.py |
| fintrust/release_workflow.py | backend/fintrust/release_workflow.py |
| fintrust/report.py | backend/fintrust/report.py |
| fintrust/rules.py | backend/fintrust/rules.py |
| fintrust/score.py | backend/fintrust/score.py |
| fintrust/upload_notifications.py | backend/fintrust/upload_notifications.py |
| fintrust/validators.py | backend/fintrust/validators.py |
| fintrust/visual_insights.py | backend/fintrust/visual_insights.py |
| fintrust/workflow_api.py | backend/fintrust/workflow_api.py |
| migration_runner/__init__.py | backend/migration_runner/__init__.py |
| migration_runner/admin.py | backend/migration_runner/admin.py |
| migration_runner/bootstrap002_entry.py | backend/migration_runner/bootstrap002_entry.py |
| migration_runner/bootstrap_entry.py | backend/migration_runner/bootstrap_entry.py |
| migration_runner/cleanup002_entry.py | backend/migration_runner/cleanup002_entry.py |
| migration_runner/cleanup_entry.py | backend/migration_runner/cleanup_entry.py |
| migration_runner/common.py | backend/migration_runner/common.py |
| migration_runner/config.py | backend/migration_runner/config.py |
| migration_runner/contract.py | backend/migration_runner/contract.py |
| migration_runner/iam.py | backend/migration_runner/iam.py |
| migration_runner/iam002_entry.py | backend/migration_runner/iam002_entry.py |
| migration_runner/iam_entry.py | backend/migration_runner/iam_entry.py |
| migration_runner/preflight_entry.py | backend/migration_runner/preflight_entry.py |
| migration_runner/release1_preflight.py | backend/migration_runner/release1_preflight.py |
| migration_runner/sql_binding.py | backend/migration_runner/sql_binding.py |
| migration_runner/workflow_catalog.py | backend/migration_runner/workflow_catalog.py |
| migration_runner/workflows.py | backend/migration_runner/workflows.py |
| src/__init__.py | backend/src/__init__.py |
| src/api/__init__.py | backend/src/api/__init__.py |
| src/api/app.py | backend/src/api/app.py |
| src/ingest/__init__.py | backend/src/ingest/__init__.py |
| src/ingest/handler.py | backend/src/ingest/handler.py |
| src/scoring/__init__.py | backend/src/scoring/__init__.py |
| src/scoring/handler.py | backend/src/scoring/handler.py |
| src/shared/__init__.py | backend/src/shared/__init__.py |
| src/shared/logger.py | backend/src/shared/logger.py |
| frontend/app.js | frontend/js/app.js |
| frontend/release1-display.js | frontend/js/release1-display.js |
| frontend/release1.css | frontend/css/release1.css |
| frontend/release1.js | frontend/js/release1.js |
| frontend/styles.css | frontend/css/styles.css |

## Verified checkpoint

Repository hardening regression: **731 passed, zero failed, 1 skipped**. The administrator-only role test is covered separately by the disposable PostgreSQL 16 service-role proof. Browser workflow, module imports, moved asset URLs, SQL bootstrap/migrations and offline packaging/source binding passed. See [verification evidence](docs/EVIDENCE/12-e2e/repository-hardening/verification-summary.json). No new Linux execution or live AWS integration success is claimed.

The local server has been restarted with `--reuse-auth`; `/release1` and the moved current JavaScript/CSS URLs return HTTP 200. The original isolated-harness failure log is retained alongside the corrected final result; it is not evidence of a live AWS change.

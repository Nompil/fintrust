# Deployment gates — consolidated candidate

Status: **local candidate verified; not deployed** (16 October 2026 SAST).

## Evidence completed

- One isolated candidate combines the current UI, Cognito authentication and production migration runner for 003–006. Current country/assignee filters, report currency separation, SAST report dates, high-risk colors and text repairs are preserved.
- 1072 unique Linux tests passed across the full run and affected rechecks. The initial full run had 1,068 passes and one browser-harness failure caused by a Windows-only executable path. That failure was repaired and passed in the 190-test recheck. Three new scanner tests also passed. This is a full run plus targeted rechecks, not a claim that the original full run had zero failures.
- Final shared Lambda ZIP passed archive/content/source checks and all five handler imports, plus all-production-module checks, on Linux x86_64 Python 3.12. It was not uploaded.
- Migrations 003–006 passed the production-handler PostgreSQL 16.15 rehearsal, including ordering, reruns, privilege guards and rollback checks. Its new disposable cluster was stopped and removed. Existing clusters and saved ledger were preserved.
- Three immutable migration phase ZIPs were accepted only after every SQL/runner binding matched this candidate, then reimported on Linux and bound to the fresh rehearsal and 107 focused tests.
- Local Stage 5 deployment IAM now matches the verified live v8, including CloudFormation-only, exact-function AddPermission/RemovePermission. The superseded standalone proposal is archived under build/consolidation, not an active IAM source.
- No AWS changes, quota changes, emails, endpoints, schedules or live consumers were activated during this consolidation.

Source manifest identity: `d87b1c676b40df5326e477093a402c5b444800446273c1752407310aa6a33367`.
Lambda ZIP SHA256: `ebf94636046662736b6f77bec1616bd122e0f14c856e189f1d90fc9fa77ea1ff`.
Detailed receipts in this branch: `docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/verification-summary.json`, `full.xml`, `repair.xml`, `runner/extensions-verification.json`, `pg16-extensions-rehearsal.json`, and `fintrust-consolidated.manifest.json`.

## Live state carried forward from verified receipts

- SES mailbox identity verified; application alert delivery not yet live-tested.
- Ingest S3 invoke resource permission applied and verified. Reserved concurrency remains zero and raw bucket notifications remain absent.
- Six service templates validated; remaining service stacks are prepared, not deployed. Use the cost-gated `infrastructure/service_preparation` templates for remaining services. Existing SES identity creation stays false; optional alarms and recovery add-ons remain false; report scheduling is separately disabled.
- Temporary migration PrivateLink/network/IAM resources were removed. No temporary endpoint was recreated.

## Remaining gates and order

1. Release source has been assembled on the dedicated `release/fintrust-consolidated-20261016` branch. Its runtime source must match the retained manifest before commit. The running main checkout, local auth registry and saved database remain untouched; no production deployment is implied.
2. Resolve the regional Lambda concurrency restriction through the account's quota/support workflow. No confirmed support case ID is available. Do not request 1,001 or change the quota without the owner's decision.
3. Prove an approved migration access path and live RDS IAM/TLS/schema preflight. No interface endpoint or other recurring network cost is authorized by this candidate verification. Keep live migration blocked until both capacity and access gates pass.
4. Run and verify live migrations, then deploy/wire scoring, query/API Gateway, Cognito account scopes and backend RBAC, alert/SES, reports/EventBridge, DLQs and logging/monitoring under least privilege. Prepared templates still require real IDs and immutable artifact versions. Any optional paid alarms/features require the existing cost decision.
5. Enable consumers and the raw S3 notification only when the downstream system is ready. Run a real ingestion-to-scoring-to-persistence-to-authorized-retrieval-to-alert/audit E2E. System completion remains blocked until it passes.

No live RDS changes or live E2E have been performed by this verification.

## Post-freeze live checks

- Runtime source frozen as commit `3368f4c31373291d11d5ef852884abb669f6dca8` on `release/fintrust-consolidated-20261016`. This does not deploy or switch the running local checkout.
- Deployer identity reauthenticated and verified. Existing foundation/ingest stacks are present and healthy.
- Quota read permissions were missing. Admin was used only to publish FinTrustConsoleReadOnly v4, adding exact-quota GetServiceQuota/history and region-bounded Lambda GetAccountSettings. Existing v3 grants were preserved. Access Analyzer returned no findings; all three new reads succeeded with deployer after propagation.
- Regional quota is still 10, unreserved quota 10, and function count 1. Service Quotas request history is empty. This does not prove there is no separate AWS Support case. No quota write was attempted.
- Existing foundation outputs are mapped in `docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/live-deployment-inputs.json`. Unresolved values remain explicit; the worksheet cannot be used as an execution-ready parameter file.
- The separate AWS Support console session requires interactive sign-in. The Support case remains a draft; paid support, a 1,001 quota request and endpoint recreation remain unauthorized.

## Support case submitted - latest evidence

The owner-provided case-details screenshot confirms submission of AWS Support
case **179210878300923**, created **16 October 2026, 01:59:43 SAST**
(`2026-10-15T23:59:43.512Z`). Its displayed status is **Unassigned**.
The console shows case type **Account**, category **Service Quotas, General**,
severity **General question**, and **Basic Support**. Earlier draft-only and
no-case-ID statements above describe the earlier state and are superseded here.

Evidence is saved without visual editing as
`docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/aws-support-case-179210878300923-details.png`.
The adjacent status JSON records the PNG SHA256, dimensions and provenance.

The quota gate remains **BLOCKED_PENDING_AWS_REVIEW**. The screenshot does not
confirm a quota increase, an assigned agent, or approval for live migration.
No live migration, service activation, support-plan upgrade or endpoint creation
was performed while saving this evidence. Keep the case-access IAM policy only
for required case follow-up, then execute its recorded cleanup plan.

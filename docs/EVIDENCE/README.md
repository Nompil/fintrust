# Verification evidence

This register points to recorded checks and identifies missing proof. Prepared commands and expected results are not execution evidence. Do not commit credentials, customer records, account-sensitive exports or generated Lambda packages here.

| Item | Evidence available | Limit / next evidence |
|---|---|---|
| Local tests | [Final offline verification](../../infrastructure/FINAL_VERIFICATION.md): 158 passed, zero failed, one skipped | Last recorded run; not rerun for documentation edits. Administrator-dependent database-role test skipped. |
| Pre-push review | [Linux CI gate](../../infrastructure/LINUX_CI_GATE.md): reviewed reachable history and tracked content | Scoped secret review, not a guarantee. Review newly staged material before push. |
| ZIP structural checks | Final offline verification records size and digest | Does not prove native dependency loading on Linux. |
| Linux CI | [Workflow](../../.github/workflows/ci.yml) and acceptance procedure prepared | No run URL or successful Linux execution evidence yet. |
| Regional compatibility | Public documentation references in final offline verification | Does not prove account opt-in, quotas or actual resource configuration. |
| AWS inventory | [Procedure](../../infrastructure/READ_ONLY_INVENTORY.md) and [blank worksheet](../../infrastructure/OPERATOR_PARAMETERS.md) | Unexecuted; separate authorization required. |
| Deployment / integration | None recorded in this phase | Permissions, TLS, API identity, queue/stream behavior, email and reporting need live evidence. |
| Presentation exports | Existing PDFs and SVGs retained | Historical content; see [diagram register](../diagrams/README.md). |

## Retaining a successful Linux run

Record the private run URL, commit SHA, run ID and attempt, actual test counts and artifact digest. Download the verified ZIP, matching manifest, verifier log and `ci-evidence.json` before the seven-day artifact expiry; store them together in approved private storage. Keep packages out of Git. The JUnit report must contain tests with zero failures, errors or skips. The manifest must record `linux_execution_verified: true` for that exact archive.

Only after the run passes can the status become ready for separately authorized read-only AWS inventory. This is not deployment approval. Ubuntu verification also does not prove execution on the exact Lambda operating system.

## Documentation evidence rules

Use implemented for behavior found in repository code, prepared for an unexecuted procedure, and verified only when a linked result establishes the claim. Deployed requires actual AWS evidence. Keep historical reports intact and point readers to the current canonical guides. Add future evidence to this register instead of creating another readiness report.

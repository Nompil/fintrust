> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Release1 migration verification

Migration001 is unchanged (normalized LF SHA256 `0ff06ca8c43596ac9b8651f4bd851bfb0487343f4c9eccb198849e3e59772bd6`). Migration002 adds operational batch/attempt/row accounting, review/history, quarantine/correction and correction/projection outboxes. Financial facts remain append-only.

Local migration tracking validates ordered source/catalog checksums. Unknown/partial/conflicting definitions fail closed; rollback removes partial writes and tracking. Tests cover fresh empty schema, legacy 200-row schema, ordered001/002, rerun, conflicting definitions, drift and row preservation. PostgreSQL 16.15 CI confirms these tests and real scoring/API service-role behavior. Review history is written only through a fixed-search-path trigger under a non-login owner; API financial/history writes and schema CREATE are denied. Privilege probes rollback and preserve 200 rows.

Evidence: `docs/EVIDENCE/12-e2e/release1-closure/postgres16-roles.json`, `postgres16-junit.xml`, `linux-ci.json`. CI 38050661063, source 4d91c3d,543 passed / zero skips. The previous local-only administrator skip executed successfully in CI.

This verifies disposable schemas, not live RDS. The existing private migration runner handles001 only; live002/grants require a separately reviewed runner/plan and approval. Never edit applied checksums, mark unverified migrations applied, drop audit/financial history or activate new runtime before schema/grants verification. No live migration was attempted. Old-runtime fallback must pause intake and reconcile operational rows; additive schema compatibility alone does not make old runtime Release1-capable.

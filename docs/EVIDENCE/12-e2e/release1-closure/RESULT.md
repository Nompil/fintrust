# Monday local Release1 verification

Verified source/pushed commit: `4d91c3d30cece5192db1afc22f71fb42e3e00413`; implementation commit `1bb141d11e6344a95a8d94679ca4e9d1f863c752`. Final evidence/documentation is committed locally afterward and not pushed.

[Successful CI 38050661063](https://github.com/Nompil/fintrust/actions/runs/38050661063): Linux x86_64, CPython 3.12.15, PostgreSQL 16.15; **543 passed, 0 failures/errors/skips**. The formerly skipped local administrator/service-role test executed successfully. Dedicated new privilege probes exercised the real scoring worker and API review transition, denied direct API financial/history writes and schema creation, rolled back grants/test writes and preserved 200 baseline rows.

Local Windows Python 3.14.7/PostgreSQL 18.6: final focused **97 passed, zero skips/failures**; full **542 passed, one expected administrator skip, zero failures**. Browser **1 passed**: all Release1 pages, review submission, detail, Auditor with zero mutation buttons and zero script errors. Network stayed loopback. Demo launcher setup and real API smoke passed with only interactive prompt/server-loop substituted; the earlier piped Windows getpass probe timed out, so launch interactively as documented.

Failures found and corrected, not hidden: initial receipt-marker/harness assertions; batch-scope SQL alias; concurrent batch registration secondary unique constraint; first CI missing synthetic projection environment setting (failed run 38048685288). Immutable receipt validation remains after conflict handling. Final source passed all above gates.

Downloaded new CI ZIP SHA256 `e134f98d1d01447ecbaa79c433deaad3c40ea78e9b74868d16fdd063125a1c4d`, base64 `4TT5jR0BRH7LqnnEM96q08QOp46bdIaNFv3QYxJaHE0=`. It was independently hashed after download into `build/release1-ci/38050661063/release/`, separate from historical ZIP. Production handlers/modules and native psycopg loaded on Linux without AWS/network calls. Source binding and package layout passed.

Migration001 normalized-LF SHA256 remains `0ff06ca8c43596ac9b8651f4bd851bfb0487343f4c9eccb198849e3e59772bd6`; historical ZIP remains `cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654`. No AWS actions, live RDS access, secrets retrieval, snapshots, migrations, concurrency, triggers or deployed-code changes occurred.

Original gap classifications: 9 BLOCKER, 16 RELEASE_1, 7 ALREADY_COVERED, 6 DEFERRED. These are historical impact categories, not remaining blocker counts. No Monday local-demo blocker remains. Actual CSV A/B bytes are external: only their per-file acceptance/hash/import tests are pending. Cloud release/live migration remains a separate approval and verification phase. Demo S3/DynamoDB are explicit session-local mocks; financial, review and correction code runs against real dedicated local PostgreSQL.

Launch: see `docs/RELEASE1_MONDAY_DEMO.md`. Truth matrix: `docs/RELEASE1_PRESENTATION_STATUS.md`. Machine evidence: `linux-ci.json`, `postgres16-roles.json`, `postgres16-junit.xml`, `linux-import-verification.txt`, `local-summary.json`, `demo-launcher.json`, `browser/browser-result.json`.

FINTRUST MONDAY DEMO RELEASE VERIFIED

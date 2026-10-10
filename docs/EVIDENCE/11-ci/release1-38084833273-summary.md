# Release 1 Linux artifact verification

Frozen application source: `3234ba5139ed354943098ecbb81080802baad9f3`.
Frontend evidence checkpoint: `115d38f29f87480a95d2ce72e0bd2d11d27ce7a6`.
CI: https://github.com/Nompil/fintrust/actions/runs/38084833273 (successful).
Only frozen source was pushed to `release1-linux-3234ba5`; main and unrelated local files were not pushed.

## Artifact

`build/release1-candidate/3234ba5/fintrust-release1-linux-py312.zip`

- Bytes: 21,414,325.
- SHA256: `788f786f4947c186a639427fd21f209a6a3cdcf0f0a284a94c0be4237177eb10`.
- Base64: `eI94b0lHwYamOUJ/0h8gmmo83PDwooSpTAvkI3F36xA=`.
- Linux x86_64, CPython 3.12.15, pinned manylinux2014 production wheels.
- Five handlers and all packaged production modules/native dependencies imported from the extracted ZIP in an isolated process; no AWS calls.
- Content audit passed; all first-party Python/frontend bytes exactly match frozen Git blobs. Fixed metadata/ordered ZIP build, pinned dependency versions and CA digest are recorded; no claim of a second independent bit-for-bit rebuild.
- Historical ZIPs retained. New ZIP is not committed or uploaded to AWS.

## Gates

- Full regression: 604 passed, 0 failed/errors, 0 skipped.
- Focused frontend/workflow subset: 55 passed within the full run.
- Separate browser gate passed all four roles, actual A/B fixtures, replay and session isolation.
- Disposable PostgreSQL 16.15 service-role gate passed, migrations 001/002 applied locally, privileges rolled back and isolated schema cleaned.
- Previously administrator-only test executed successfully in CI.
- CI verification evidence and exact package manifest are preserved under the existing `docs/EVIDENCE/11-ci/` folder with prefix `release1-38084833273-`.
- Full CI browser screenshots remain in the downloaded build evidence and the GitHub run artifact; historical frontend evidence is not overwritten.
- Release manifest records dependency versions, handler list, fixture/migration Git-blob hashes, environment, artifact hashes and CI provenance.

## Boundary

No source/build-script change was required. Capability statuses are unchanged; this is new exact-source verification evidence, not live AWS verification.
No AWS inventory, secret retrieval, RDS access, migration, endpoint/operator creation, code upload, trigger/concurrency change or deployment occurred.
Next checkpoint: remaining AWS screenshots/current-state evidence, then separately approve the scoped migration operator and temporary private preflight path. Perform read-only RDS schema preflight and stop before migration 002.

FINTRUST RELEASE 1 LINUX ARTIFACT VERIFIED — READY FOR CONTROLLED AWS PREFLIGHT INFRASTRUCTURE

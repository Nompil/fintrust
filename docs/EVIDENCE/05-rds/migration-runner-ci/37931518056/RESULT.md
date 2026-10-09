# Private RDS index privilege path verified

[Successful CI run 37931518056](https://github.com/Nompil/fintrust/actions/runs/37931518056) at `cc3d1948e52c6a7f465acbc2a4d5e02564daa9a8`.
451 passed, 0 failed, 0 skipped; 66 focused migration tests included.
Ubuntu 24.04 x86_64 / Python 3.12.15 / PostgreSQL 16.15.

The parameterless helper permits the two fixed indexes without schema CREATE or
helper-role membership for the migration login. PostgreSQL rehearsal verified
bootstrap, privilege denials, exact existing-index handling, conflict refusal,
transaction rollback, migration/rerun, helper self-removal and removal of both
temporary roles. All 200 legacy rows and existing runtime permissions survived.
The owner's inherent table DDL/regrant authority remains a documented limitation;
this is not a column-level DDL sandbox. The helper role internally has schema
CREATE, but the login cannot assume it and its callable function accepts no input.

All four actual ZIP handlers/modules and native psycopg2 imported on Linux CPython
3.12, including the Lambda runtime container with networking disabled. Raw manifests
record imports, native/libpq versions, source bindings and base64 checksums.
Downloaded ZIP CRCs, ELF architecture, ABI, phase isolation, source bindings and
SHA256/base64/size were checked again locally without rebuilding.

| Phase | Bytes | SHA256 |
|---|---:|---|
| preflight | 20670849 | `2f8afab595bac03f2b53f2ee7cda5befd282d5adaf57e7f7514ab1602d3dbd5f` |
| bootstrap | 20674310 | `b2e6112dd0a6d7dcd1d74cab7aa0f5b54dfc94b0185657de12d58af1f5d6a9e4` |
| iam | 20671887 | `8113cb82761282dc43bb71f8b7e389eb53092519c95c64b4ea2d947b9493f249` |
| cleanup | 20671895 | `33e5d041688e1785ec459172d18c6c6c782227a8999e333f3113ac104947b92a` |

ZIPs are retained locally under `build/migration-runner/ci/37931518056/`; binaries are not
committed. `regression.xml`, `pg16-role-rehearsal.json`, four manifests,
`lambda-image-digest.json`, `run.json` and `summary.json` preserve evidence here.
Earlier failed runs and focused corrections are recorded in summary.json and the
runner design document. No test was removed or skipped to obtain this pass.

Application artifact SHA256 remains `cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654`.
No AWS account access, live RDS, secret retrieval, upload or deployment occurred.
Vanilla PostgreSQL's stand-in rds_iam role does not prove real RDS IAM/TLS login.
Access Analyzer/template validation and all live approval gates remain separate.
Next checkpoint: business-rule/schema freeze, not AWS execution.

# Original CSV A/B acceptance checkpoint

The actual downloadable artifacts were found in Downloads and copied unchanged into tests/fixtures/e2e. They are not regenerated scenarios. The application and verified Linux ZIP remain unchanged.

| Original | Bytes | Data rows | SHA256 | SHA256 Base64 |
|---|---:|---:|---|---|
| fintrust_e2e_mixed_transactions.csv | 2328 | 33 | 1b2a3a1fa424b7c4e320b2fc9d0f13154945d0dc370a0aaa5a0e44f0573ff8df | Gyo6H6Qkt8TjILL8nQ8TFUlF0Nw3CgqqWg5E8Fc/+N8= |
| fintrust_e2e_companion_transactions_B.csv | 868 | 11 | 7d981dd595b0ba56dbedbe683fd991ad5cec41f49fc68b7d5e7e1a8b96da60b6 | fZgd1ZWwulbb7b5oP9mRrVzsQfSfxot9Xn4ai5baYLY= |

Both headers are transaction_id,account_id,amount,currency,country,transaction_type,transaction_timestamp. Exact header matches: transaction_id,account_id,amount,currency,country. Missing required headers: source_system,tx_date,tx_type and one of source_transaction_id/source_reference. Unsupported headers: transaction_type,transaction_timestamp. Actual parser result: MISSING_HEADERS; HTTP result:400 INVALID_CSV_SCHEMA.

The frozen contract is authoritative: internal UUID tx_id is distinct from trusted upstream source reference. These older external fixtures do not match it. TX-* strings belong conceptually to an upstream reference, not the current transaction_id internal UUID alias. ACC101..ACC104 are not UUID accounts. PURCHASE is not debit/credit/transfer/fee, and its mapping must be reviewed rather than inferred. Merely renaming headers would leave those semantic mismatches and the absent source namespace unresolved.

The row-by-row report in contract-audit.json preserves all44 original row positions and labels. All business outcomes are NOT_PROCESSED because file admission rejects the entire file; there is no fictitious accepted/quarantined/duplicate outcome. A then B then unchanged A are submitted through the actual authenticated local /v1/upload path. The test asserts zero calls to the storage/row adapter, baseline200 ledger rows retained, zero ingestion batches and zero quarantine cases. Rejection is expected security behavior; passing rejection tests is not dataset acceptance.

Duplicate-file, cross-file duplicate, identity-conflict and possible-double-charge acceptance from these originals are NOT VERIFIED. Existing constructed tests remain verified on candidate source d648dd0 and CI38058750009; they are not substituted for these files. Additional coverage problems: no same-source-label materially changed payload case exists; TX-VEL rows are four minutes apart and cannot prove >5 accepted transactions in five minutes. The frozen rule remains unchanged.

Reviewed correction proposal, not performed:

| Original representation | Proposed contract representation | Review needed |
|---|---|---|
| transaction_timestamp | tx_date | Preserve timestamp bytes/value, including intentionally malformed/missing/future cases |
| transaction_type | tx_type | Define financial meaning of PURCHASE before mapping; do not assume debit |
| TX-* transaction_id | source_transaction_id | Preserve upstream label; let internal tx_id be generated |
| missing source_system | Explicit stable source namespace | Choose one namespace shared by A/B so cross-file identity is meaningful |
| ACC101..ACC104 | Assigned UUID account baseline | Supply approved map and baseline; preserve missing account and unknown ACC999999 as invalid cases |

If approved, produce separately named corrected fixtures with transformation evidence and original hashes. Never overwrite these originals or fix deliberately invalid amounts/countries/timestamps to achieve acceptance. Define a reviewed fixed receipt clock before deriving expected future-timestamp outcomes. Keep required velocity boundary and identity-conflict cases separate and explicit if actual files do not contain them.

AWS readiness steps7â€“10 are conditional on a green real-fixture gate. That gate failed, so no new AWS/controller/RDS readiness audit or execution was started. Existing infrastructure/RELEASE1_DEPLOYMENT_CHECKPOINT.md remains the future checkpoint: fintrust-inventory for metadata-only inventory; controlled fintrust-admin for later approved bootstrap/recovery where the existing plan requires it; scoped deployment identities only after review. Endpoint/runner deployment itself is a mutation, not read-only AWS inventory. No live invocation or secret read is authorized here.

Verified artifact retained: build/release1-candidate/fintrust-release1-linux-py312.zip;21404079 bytes;SHA256981417e236116992e5d9e7d9208a6610815044bd870bde0ddee4fe12afa76fac. No rebuild, upload, AWS action or application-code change. Source remains d648dd0a77b6906daa94ec7ade7b2ff3e3158ed0. New fixture/audit commits are local-only; no CI run is required to rebuild an unchanged application just to prove file-header rejection.

Final local results: fixture-specific3 passed; final focused subset123 passed; full regression573 passed,0 failed,1 expected administrator-only skip,0 unexpected skips. The administrator test already passed in the unchanged candidate PostgreSQL16 CI. An initial new-test table-name error was corrected; no application defect was found. Detailed results and redacted full JUnit are in local-test-results.json and full-regression.xml. Existing Linux/PostgreSQL16.15 CI38058750009 remains571 passed,0 failed,0 skipped; previous required-page browser gate passed. No new accepted fixture data reaches UI, so no new browser result is claimed.

FINTRUST REAL DATASET ACCEPTANCE BLOCKED â€” original CSV schema and identity/type/account semantics do not match the frozen contract; reviewed mapping and missing velocity/identity-conflict coverage are required

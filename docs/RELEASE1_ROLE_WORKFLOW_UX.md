> Supporting source retained for traceability. Use [Project Master](FinTrust_Project_Master.pdf) for consolidated project information and [Project Progress](FinTrust_Project_Progress.pdf) for current status. Historical counts and deployment statements below apply to their original checkpoint.

# Release 1 role and workflow correction

Separate correction after the immutable presentation parent `5b5bb50f4bf02bca518940675f9b476bd8750a67`. Application source changed; the historical Linux artifact remains unchanged and a new source-bound build is still required before cloud deployment. No AWS, live SQL, seed changes, scoring changes or deployment occurred.

## Findings and behavior

The exact screenshot file was not supplied. The old `samples/transactions_day2.csv` and original external fixtures use the legacy schema: Release 1 requires `source_system` plus either `source_transaction_id` or `source_reference`. A .csv extension alone cannot satisfy this contract. Missing columns now appear in safe rejection details. Duplicate headers, unsupported columns, encoding, empty/header-only files and malformed structure have specific bounded messages. Invalid amounts, types and timestamps within admitted rows continue to follow the existing quarantine rules rather than rejecting otherwise valid rows.

Uploads now require Analyst on both the HTTP boundary and the upload adapter. Admin, Auditor and Maintainer cannot upload. Technical retries/redrive require Maintainer; Admin retains read-only operations visibility and user governance. Analyst has review/correction authority but cannot administer users or technical retries. Manual endpoint calls are covered by regression tests; hidden buttons alone are not the authority.

Analyst lands in Review Queue, Admin/Auditor in Overview and Maintainer in Operations. Upload form appears before latest notices and batch history; selected review/correction and technical actions appear before history. Active review/quarantine rows sort before closed history. Notifications remain session-private and persistent until acknowledged, with separate items rather than concatenated messages. Main errors omit correlation UUIDs and hide server failures; technical/audit records retain their correlation IDs. Table headers no longer split words.

Eight backend-driven charts, report downloads, identity/deduplication, financial validation, risk thresholds and immutable evidence are preserved. Reports continue to export the current authorized account/page, not an invented date-period selection.

## Known scope limits

At this historical freeze, non-Admin batch views excluded unknown/unassigned outcomes. That limitation is superseded only for genuinely unknown rows in the original authenticated uploader's batch by the explicit approval below. Batches containing known unassigned accounts remain inaccessible. Historical rule: unknown-account correction was deferred at this freeze. The explicitly approved continuation now permits an active Analyst to view and correct genuinely unknown/missing-account rows from their original authenticated local upload only. The first-admission receipt is immutable and versioned; duplicate re-upload does not transfer ownership. Corrected accounts must exist and be assigned. Historical batches without ownership evidence and cloud intake without trusted admission remain blocked. Known unassigned accounts remain inaccessible. The browser exercises scoped Analyst review/correction and Admin batch reconciliation separately. Notifications clear on sign-out to prevent another user seeing the uploading user's session history.

## Verification

Results and separate screenshots are under `docs/EVIDENCE/12-e2e/role-workflow-ux/`. Existing focused regression passed 122 checks; six new role/error checks and two offline bootstrap composition checks passed. The final four-role browser gate passed after verifying action-before-history layout, upload actor, separate notices and concealed Admin mutations. Full regression outcome is recorded in verification.json. The original freeze evidence is not overwritten.

FINTRUST ROLE AND WORKFLOW UX VERIFIED

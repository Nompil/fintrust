# Next database gate: initialize the missing application schema

The single live read-only request on 17 October 2026 succeeded against database
`fintrust`, PostgreSQL 16.15, as `fintrust_admin`, with TLS verified by the runner.
Its assessment was `missing-base`. All six expected base tables and the inspected
release workflow objects were absent. The inspected FinTrust runtime/maintenance
roles were also absent. No write or financial row transfer occurred.

This is evidence that the expected application objects are absent, not a claim
that every schema in the instance is empty. Do not run the existing migration
bootstrap against this result: it requires an existing `public.transactions`.

The existing `tools/render_release1_base.py` pins the canonical base prefix of
`sql/schema.sql`. Its guard rejects any non-extension relation already present
in `public`, including unrelated tables. The additional disposable PostgreSQL
16.15 verification in `empty-base-pg16-verification.json` proved that:

- an unrelated existing table and its row survive a refused initialization;
- a non-superuser database owner can create the six empty base tables;
- repeating initialization is refused;
- no seed data or AWS access is involved, and the temporary cluster is removed.

This local proof does not authorize or establish a live schema change. The next
reviewed live runner must bind the fixed initializer, recheck database identity,
TLS, backups and the empty-public-schema guard within its transaction, and return
only sanitized verification metadata. It must not accept SQL in its event, run
`sql/seed.sql`, copy the preserved local ledger, or reset existing objects.

After base initialization, execute the existing reviewed migration phases in
order (001 through 006), with their own source/catalog/history checks and temporary
privilege cleanup. Verify service database logins, IAM authentication and least
privilege before enabling any application function. A successful catalog query
is not a completed database deployment or an end-to-end application test.

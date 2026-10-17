# Guarded cloud database initialization

This packet targets only account 966467878406, af-south-1, the existing private
`fintrust-ledger-dev` PostgreSQL database. It refuses a nonempty/unexpected base
schema. It does not import or modify the preserved local ledger.

The fixed sequence creates the empty six-table base, applies migrations 001–006,
verifies their catalog signatures, removes maintenance database access, provisions
three least-privilege IAM database logins, and creates two explicitly fictional
customer/account references with zero balances. It creates no financial transaction.

Each phase uses its own hash-bound Linux Python 3.12 archive and qualified Lambda
version. The previous version must be removed before the next phase is enabled.
The runner normally has concurrency zero; one synchronous qualified request runs
using the shared regional capacity. An uncertain request is never automatically
replayed. Receipts identify attempted and verified operations separately.

`postgres16-rehearsal.json` records isolated real PostgreSQL 16 execution, including
scoring, API read/review updates, account-scope denial and report output through
the service logins. AWS was mocked in that rehearsal. It does not establish live
AWS IAM authentication, TLS transport or email delivery.

The administrator is used only for IAM and policy validation. A temporary scoped
operator performs service work. Application concurrency, disabled consumers,
disabled report schedule and absent raw-bucket notification are checked throughout.
Backup retention, encryption, deletion protection and recent restorable time are
required before database writes.

The single-AZ private Secrets Manager endpoint incurs usage charges authorized
by the owner. Cleanup begins by removing this paid endpoint, then waits for the
temporary Lambda network interfaces before removing temporary roles and policies.
It preserves the database, runtime logins, staged package versions and retained log
group. The Basic Support plan is unchanged. No public database, NAT, additional
reserved concurrency or automatic ingestion is created.

`manifest.json` binds the exact templates and package contents. Live completion
requires the saved execution receipt and cleanup verification; package validation
alone does not mean the application is deployment-ready.

# Short live demonstration script

Use the existing [Monday demonstration runbook](../RELEASE1_MONDAY_DEMO.md) for launch and fixture instructions. Keep credentials out of slides, evidence and copied commands. Do not seed or migrate live RDS for this presentation.

1. State the boundary: this is the frozen local application with isolated PostgreSQL and local service substitutes; the AWS foundation is separate.
2. Sign in as the prepared Analyst. Show assigned scope, transactions and batch reconciliation.
3. Admit the prepared permitted CSV from the runbook. Show accepted, duplicate and quarantined outcomes. Explain that no row disappears silently.
4. Show a rejected file and its safe receipt. Contrast file rejection with row quarantine.
5. Open a quarantined row; show reason and lineage. Explain correction and revalidation before demonstrating an approved fixture correction.
6. Show LOW, MEDIUM and HIGH results, the reasons and review history. Explain that HIGH signals investigation, not proven fraud.
7. Show reports/insights and audit. Sign out, then use the prepared Auditor identity to demonstrate read-only scope.
8. Use the role-separation diagram for Administrator governance and Maintainer recovery. Do not improvise technical retries in front of the panel.
9. Close with the AWS architecture: private PostgreSQL, no NAT, gateway endpoints; pending application wiring is clearly labelled.

If a fixture is unavailable, show the verified evidence and say so. CSV A/B files created outside this repository are not assumed to exist here. Do not invent fixture paths or deployment status.

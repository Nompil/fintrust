# FinTrust Release 1 presentation pack

Start with [speaker notes](FINTRUST_USE_CASE_SUMMARY.md), then [the live demo script](LIVE_DEMO_SCRIPT.md). Use the data decision flow first; keep the full ERD as the technical appendix.

| View | Screen export | Editable source |
|---|---|---|
| PostgreSQL ERD | [SVG](../diagrams/fintrust-release1-erd.svg) | [DOT source](../diagrams/fintrust-release1-erd.dot) |
| AWS Architecture | [SVG](../diagrams/fintrust-release1-aws-architecture.svg) | [DOT source](../diagrams/fintrust-release1-aws-architecture.dot) |
| Activity Diagram | [SVG](../diagrams/fintrust-release1-activity.svg) | [DOT source](../diagrams/fintrust-release1-activity.dot) |
| Use Cases | [SVG](../diagrams/fintrust-release1-use-cases.svg) | [DOT source](../diagrams/fintrust-release1-use-cases.dot) |
| Data Decision Flow | [SVG](../diagrams/fintrust-release1-data-decisions.svg) | [DOT source](../diagrams/fintrust-release1-data-decisions.dot) |
| Duplicate Handling | [SVG](../diagrams/fintrust-release1-duplicate-handling.svg) | [DOT source](../diagrams/fintrust-release1-duplicate-handling.dot) |
| Role Separation | [SVG](../diagrams/fintrust-release1-role-separation.svg) | [DOT source](../diagrams/fintrust-release1-role-separation.dot) |

[ERD keys, relationships and storage notes](../diagrams/fintrust-release1-erd-notes.md) explain the physical schema. SVG exports scale without losing detail; open them directly in the browser. The full ERD is an appendix for closer inspection of its 17 tables.

## Evidence boundary

Application freeze: `10eb378abf6a4a256043cd56617378cc17ae505c`. The local assurance checkpoint recorded 713 tests and browser checks with no failures. AWS stages 1–4 are recorded as verified; the historical ingest deployment remains disabled. Live schema bootstrap and complete application wiring remain pending. The final frozen release candidate still needs its Linux execution gate; earlier Linux verification does not prove the new candidate.

No AWS checks or changes were performed when producing this pack. Architecture colors distinguish verified foundation, pending target, and disabled ingest.

[Diagram/reference inventory and after-presentation cleanup](DIAGRAM_REFERENCE_INVENTORY.md) · [Render evidence](../EVIDENCE/12-e2e/presentation-diagram-pack/render-validation.json) · [Current presentation readiness](../RELEASE1_PRESENTATION_READINESS.md).

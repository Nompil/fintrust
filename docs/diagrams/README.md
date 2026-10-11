# Diagram register

The current behavior is documented in [architecture](../architecture.md), [ERD](../erd.md) and [security](../SECURITY.md). Existing graphic exports predate the FIFO/Streams design and schema additions. They are retained as historical design artifacts and are not deployment evidence or reconciled final presentation material.

## Seven final views

| Required view | Retained source / asset | Reconciliation required |
|---|---|---|
| AWS architecture | `fintrust.drawio`, `architecture_target.svg` | Show five functions, FIFO, immutable projections, Streams and current VPC placement. |
| PostgreSQL ERD | [Current Markdown ERD](../erd.md), `erd.svg`, draw.io ERD page | Export the additive schema including processed transactions and legacy alert fields. |
| End-to-end transaction sequence | `upload_sequence.svg` | Existing view is local upload; replace its final presentation scope with queue/scoring/projection/alert retries. |
| Quarantine versus DLQ | `activity.svg` | Existing local activity view does not cover the complete cloud failure routes. |
| Network and security | No dedicated current asset | Show shared private subnets, database grants, gateways and external ingest/alert placement; no NAT. |
| Data lifecycle | No dedicated current asset | Distinguish monthly summaries, proposed full archive and blocked deletion. |
| Use cases | `use_cases.svg` | Reconcile analyst, operator and system actions; label unavailable cloud browser integration. |

Retain `architecture_day1_day3.svg` as the early direct-SQL design. Do not use its historical implementation label as current status. The three draw.io pages also need reconciliation. No new graphic exports were generated during documentation consolidation.

## Sources and export policy

AWS icon PNGs in `aws-icons/` are unmodified assets from the official AWS Architecture Icons package (July 2026 version). They identify services and do not imply endorsement. Preserve attribution and the existing assets.

`tools/build_diagrams.py` writes AWS architecture, ERD, draw.io and PDF outputs. `tools/build_system_document.py` writes behavior diagrams and the system PDF. Their hardcoded content must be updated before regeneration. Regeneration can overwrite manual draw.io edits; review the source first. The documentation environment uses reportlab, pillow, pymupdf and svglib; these are not Lambda runtime requirements.

The retained PDFs are [architecture and ERD](../../output/pdf/fintrust_architecture_and_erd.pdf) and [system documentation](../../output/pdf/fintrust_system_documentation.pdf). Both require content reconciliation and visual inspection before final presentation.

Maintain these seven views rather than producing diagrams for every checkpoint. Update a view when a material architecture decision changes it. Label repository implementation, target design and unverified integration explicitly. After AWS verification, reconcile actual configuration against source, update canonical docs and generator content, rebuild exports, inspect every page and link supporting evidence. Do not label a target as deployed without that evidence.

## Release 1 operating-model presentation

Use [current operating-model diagrams](release1-operating-model.md) for the four current architecture/decision/recovery/role views. They label local verification and incomplete AWS integration explicitly. Historical SVG/PDF exports above remain historical and must not be presented as reconciled live architecture.

# Authoritative Release 1 diagrams

Open the [presentation index](../presentation/README.md). These seven views replace the older current-directory exports and duplicate inline diagrams.

| View | Rendered export | Source |
|---|---|---|
| PostgreSQL ERD | [SVG](fintrust-release1-erd.svg) | [DOT](fintrust-release1-erd.dot) |
| AWS Architecture | [SVG](fintrust-release1-aws-architecture.svg) | [DOT](fintrust-release1-aws-architecture.dot) |
| Activity Diagram | [SVG](fintrust-release1-activity.svg) | [DOT](fintrust-release1-activity.dot) |
| Use Cases | [SVG](fintrust-release1-use-cases.svg) | [DOT](fintrust-release1-use-cases.dot) |
| Data Decision Flow | [SVG](fintrust-release1-data-decisions.svg) | [DOT](fintrust-release1-data-decisions.dot) |
| Duplicate Handling | [SVG](fintrust-release1-duplicate-handling.svg) | [DOT](fintrust-release1-duplicate-handling.dot) |
| Role Separation | [SVG](fintrust-release1-role-separation.svg) | [DOT](fintrust-release1-role-separation.dot) |

[ERD notes](fintrust-release1-erd-notes.md) document physical keys/cardinality and the two derived views. The schema has 17 tables; users and browser notifications are not invented SQL entities. MEDIUM and HIGH open reviews according to the frozen application.

## Rebuild and verification

`tools/render_release1_diagrams.cjs` renders the seven DOT sources using an installed `@viz-js/viz` package. Set `FINTRUST_VIZ_MODULE` to that package directory and run the renderer with Node. No application or AWS operation occurs. Run `tools/verify_release1_diagrams.cjs` for the browser checks; set `FINTRUST_PLAYWRIGHT_MODULE` and `FINTRUST_CHROME_PATH` if their installed locations differ. Viz.js 3.25.0 / Graphviz WASM rendered the current pack; installed Chrome/Playwright checked all exports for blank output, clipped labels and overlapping nodes at 1600×1050. [Validation evidence](../EVIDENCE/12-e2e/presentation-diagram-pack/render-validation.json) includes screenshots. Inspect the full ERD at native size when explaining individual keys.

## Historical exports

Nine older SVG/draw.io/PDF exports are preserved under [historical design evidence](../EVIDENCE/12-e2e/historical-design-diagrams/). [Move manifest](../EVIDENCE/12-e2e/presentation-diagram-pack/historical-export-moves.json) records original paths, hashes and references. They are archive-only and must not be used to claim current implementation or deployment.

The two older Python diagram builders now write only into that historical folder; their hardcoded content remains historical. Current diagrams are maintained as DOT sources. The AWS architecture now embeds the unmodified official AWS icon assets retained in `aws-icons/`, imported by the historical generator from the AWS Architecture Icons package. Source attribution: [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/). Embedded icons make the SVG portable; icon color does not imply deployed status. The diagram’s status labels and background legend define that boundary. See the [complete inventory](../presentation/DIAGRAM_REFERENCE_INVENTORY.md).

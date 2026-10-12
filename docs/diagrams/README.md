# Release 1 diagram maintenance

User-facing planning and presentation evidence: [combined PDF](../presentation/FinTrust_Project_Planning_and_Design_Evidence.pdf).

| View | Final export | Editable source |
|---|---|---|
| Erd | [PDF](../presentation/diagrams/FinTrust_ERD.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-erd.dot) |
| Aws Architecture | [PDF](../presentation/diagrams/FinTrust_AWS_Architecture.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-aws-architecture.dot) |
| Activity | [PDF](../presentation/diagrams/FinTrust_Activity_Diagram.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-activity.dot) |
| Use Cases | [PDF](../presentation/diagrams/FinTrust_Use_Case_Diagram.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-use-cases.dot) |
| Data Decisions | [PDF](../presentation/diagrams/FinTrust_Data_Decision_Flow.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-data-decisions.dot) |
| Duplicate Handling | [PDF](../presentation/diagrams/FinTrust_Duplicate_Handling.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-duplicate-handling.dot) |
| Role Separation | [PDF](../presentation/diagrams/FinTrust_Role_Separation.pdf) | [DOT](../presentation/diagram-source/fintrust-release1-role-separation.dot) |

## Reproduce

Set `FINTRUST_VIZ_MODULE` to the installed `@viz-js/viz` package and run `tools/render_release1_diagrams.cjs` with Node. It reads only the seven DOT sources and writes intermediate SVGs into ignored `build/presentation-pdf/svg/`. Run `tools/build_presentation_pdf.py` with Python/reportlab/svglib/PyMuPDF and Arial fonts to reproduce the eight PDFs. `tools/verify_release1_diagrams.cjs` checks the intermediate vector layouts using installed Chrome/Playwright. No AWS or application operation occurs.

The AWS diagram embeds unmodified official service icon assets retained in `aws-icons/`: [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/). The ERD has one conceptual overview and four physical domain pages, preserving 17 tables and 16 foreign keys. AWS and activity each have two pages separating core paths from supporting workflows. Orthogonal routing and A3 sheets preserve readable labels; compact support diagrams use A4 landscape. Each diagram retains one DOT source and one PDF; multi-view sources use `// VIEW:` separators. [Exact schema notes](fintrust-release1-erd-notes.md) are retained as development source documentation.

Nine older SVG/draw.io/PDF exports remain [historical design evidence](../EVIDENCE/12-e2e/historical-design-diagrams/). Existing render screenshots are historical validation records rather than current deliverables. [PDF validation](../EVIDENCE/12-e2e/presentation-diagram-pack/pdf-validation.json) records every final page. The two old Python builders write only into the historical archive.

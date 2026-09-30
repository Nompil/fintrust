# Diagram sources

`fintrust.drawio` contains three editable pages: current Day 1-3 architecture, final target and the relational ERD. SVG exports are embedded in the design documents. The combined presentation PDF is in `output/pdf/fintrust_architecture_and_erd.pdf`.

The selected AWS service icons are unmodified PNG assets from the official July 2026 [AWS Architecture Icons package](https://aws.amazon.com/architecture/icons/). They are used to identify AWS services, not to imply AWS endorsement. The SVG diagrams embed the images so they can be shared without separate image paths.

The build command is `py tools/build_diagrams.py`, with `reportlab`, `pillow` and `pymupdf` installed in a documentation environment. The system-record builder also requires `svglib`. These are documentation tools, not Lambda application dependencies. The generator writes PDF/SVG/draw.io outputs together; regeneration overwrites manual draw.io edits.

The diagrams express implementation/design status and proposed boundaries. They are not deployment evidence. Detailed connection/security gaps are recorded in `docs/architecture.md`.

## Behaviour diagrams

The local activity, use-case and upload-sequence diagrams are editable SVG files: `activity.svg`, `use_cases.svg` and `upload_sequence.svg`. They are rebuilt by `tools/build_system_document.py` and included in the complete system PDF. AWS diagrams and the ERD remain in the draw.io source. Diagram sources describe design and do not establish cloud deployment evidence.

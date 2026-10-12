# FinTrust Release 1 PostgreSQL schema

The authoritative [full ERD](presentation/diagrams/FinTrust_ERD.pdf), [editable DOT source](presentation/diagram-source/fintrust-release1-erd.dot) and [key/cardinality notes](diagrams/fintrust-release1-erd-notes.md) describe the verified local PostgreSQL catalog: 17 tables and two derived views.

The diagram includes identity, ingestion lineage, quarantine/correction, ledger/risk review, operations receipts, durable outboxes and migration history. A lineage column is not a foreign key unless the catalog declares it. User identities are stored outside SQL; browser notifications are session state.

The diagram does not prove live RDS has been bootstrapped. That remains pending after the read-only preflight found an empty application schema. See [presentation readiness](RELEASE1_PRESENTATION_READINESS.md) and the [presentation index](presentation/FinTrust_Project_Planning_and_Design_Evidence.pdf). Earlier schema exports remain [historical evidence](EVIDENCE/12-e2e/historical-design-diagrams/).

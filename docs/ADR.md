# Architecture Decision Record Index

This file is the indexed log of material architecture decisions for Town Council.

Use each entry to record:
- the decision
- the reason it was made
- the affected boundary or contract
- links to the canonical docs that carry the ongoing operational or architecture detail

## 2026-04-06: Use seam creation before the next model-coupled typing wave

- Status: Accepted
- Decision:
  - Strict typing has reached a boundary where direct subtree enrollment would immediately drag model-heavy and helper-heavy dependency debt.
  - The next strict-typing follow-up should create a typed seam around the extraction boundary before attempting the next model-coupled service-layer wave.
- Why:
  - Recent typed-subtree waves exhausted the low-churn utility and medium service-layer candidates that stayed isolated.
  - Probing the next likely candidates showed direct typing would spill into `pipeline.models`, extractor/text-cleaning helpers, and related runtime surfaces.
  - A seam at the extraction boundary reduces transitive drag while preserving current extraction behavior.
- Affected boundaries:
  - `pipeline/extraction_service.py` remains the orchestration layer for extraction reprocessing.
  - extractor, cleaning, and bad-content classification helpers remain dependencies behind narrow typed contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

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

## 2026-04-06: Enroll extraction_service before larger service waves

- Status: Accepted
- Decision:
  - `pipeline/extraction_service.py` is the next strict-typing enrollment target after the seam-creation prep wave.
  - The service should isolate extractor, text-cleaning, and bad-content classification behind local typed wrappers so the typed subtree can expand without dragging those neighbors into the same wave.
  - `pipeline/agenda_service.py` remains deferred because its current import surface still spills into untyped `pipeline.models` and `pipeline.utils`.
- Why:
  - The extraction seam was already in place, which made it the narrowest meaningful post-seam enrollment candidate.
  - A direct agenda-service enrollment would still require broader model/helper typing work.
  - This keeps strict-typing progress incremental while preserving the larger model-coupled service wave for later.
- Affected boundaries:
  - `pipeline/extraction_service.py` remains the extraction orchestration layer.
  - extractor, cleaning, and bad-content classification stay behind locally typed service wrappers.
  - the typed subtree expands by one service file without widening into `pipeline.models`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Enroll summary_hydration_diagnostics after query-boundary cleanup

- Status: Accepted
- Decision:
  - `pipeline/summary_hydration_diagnostics.py` is enrolled in the typed subtree after a boundary-prep pass that split policy logic from query assembly and localized ORM symbol loading.
  - The module keeps `SummaryHydrationSnapshot` and existing script-visible output semantics stable while containing model/query typing inside the diagnostics boundary.
  - `pipeline/agenda_service.py` remains deferred because it still spills directly into untyped `pipeline.models` and `pipeline.utils`.
- Why:
  - The next honest strict-typing problem after `extraction_service` was the model/query-heavy summary hydration diagnostic boundary.
  - Refactoring that boundary made the module type-clean without widening the strict subtree into the ORM layer.
  - This reduces the cost of later service-layer typing work while preserving current operator workflows.
- Affected boundaries:
  - `pipeline/summary_hydration_diagnostics.py` remains the operator-facing hydration backlog diagnostic boundary.
  - `scripts/diagnose_summary_hydration.py` and `scripts/staged_hydrate_cities.py` keep consuming the same snapshot contract.
  - the typed subtree expands by one diagnostics module without typing `pipeline.models`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

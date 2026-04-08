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

## 2026-04-07: Establish a shared models seam before the next service enrollments

- Status: Accepted
- Decision:
  - Strict typing should stop relying on one-off service wrappers and instead introduce a shared `pipeline.models` access seam for agenda and verification workflows.
  - `pipeline/agenda_service.py` is enrolled through that seam as the first consumer.
  - `pipeline/verification_service.py` adopts the seam selectively for session and catalog/item loading, but remains outside the typed subtree until its remaining local annotation debt is addressed separately.
- Why:
  - Repeated direct-enrollment probes had reached the same structural blocker: broad imports from `pipeline.models` and `pipeline.utils`.
  - A shared seam keeps service modules dependent on the smallest record/query contracts they actually consume.
  - `agenda_service` was the narrowest path to prove the seam is reusable without dragging in a full verification cleanup wave.
- Affected boundaries:
  - `pipeline.models` remains the ORM layer.
  - `pipeline/agenda_verification_model_access.py` becomes the typed boundary for narrow agenda and verification model access.
  - `pipeline/agenda_service.py` remains an agenda-domain service and no longer imports broad ORM symbols directly.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Finish strict typing for the reusable pipeline core

- Status: Accepted
- Decision:
  - Strict typing for the reusable pipeline core is complete once the remaining shared foundations and helper modules are enrolled together.
  - `pipeline/models.py`, `pipeline/utils.py`, and `pipeline/verification_service.py` are enrolled alongside the next reusable helper layer: `pipeline/agenda_resolver.py` and `pipeline/vote_extractor.py`.
  - `pipeline/agenda_crosscheck.py` and `pipeline/agenda_legistar.py` are enrolled with `agenda_resolver.py` because they are now part of the same typed helper boundary.
- Why:
  - The shared `pipeline.models` seam removed the structural blocker that had kept `verification_service` out of the typed subtree.
  - The remaining reusable-core debt was concentrated in typed foundations and helper modules, not in new architecture work.
  - Stopping here keeps strict typing scoped to reusable pipeline modules without widening into worker entrypoints or backend-heavy modules.
- Affected boundaries:
  - `pipeline.models` remains the ORM layer, but its helper surface is now part of the strict typed core.
  - `pipeline.utils` remains the shared utility boundary, now with explicit contracts.
  - `pipeline.verification_service`, `pipeline.agenda_resolver`, and `pipeline.vote_extractor` are part of the reusable typed pipeline core.
  - worker/orchestration modules and backend-heavy modules remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Enforce Ruff formatting for the scoped formatter-ready path set

- Status: Accepted
- Decision:
  - The current formatter-ready path set is mechanically normalized with Ruff and now enforced in CI with a path-scoped `ruff format --check` command.
  - Formatter enforcement remains limited to the existing formatter-ready path set rather than expanding to repo-wide Python coverage.
- Why:
  - The reusable pipeline core is now stable enough to support a dedicated mechanical formatting wave.
  - The repo already had an explicit formatter-ready path set, which made it possible to enforce formatting without widening into unrelated modules.
  - Keeping the formatter command path-scoped preserves low-risk rollout and avoids conflating formatting policy with broader cleanup.
- Affected boundaries:
  - `docs/ENGINEERING_GUARDRAILS.md` remains the human-readable formatter policy.
  - `tests/test_repository_guardrails.py` remains the alignment check for the scoped formatter command.
  - `.github/workflows/python-guardrails.yml` enforces the same explicit path set in CI.
- Canonical references:
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [ROADMAP.md](../ROADMAP.md)

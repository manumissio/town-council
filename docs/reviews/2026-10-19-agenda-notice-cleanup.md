# Agenda cleanup: fewer false items, more honest labels

Date: 2026-10-19. Compared against commit
`1383f41c446a17f33c3d765a89f57f0acd31e3e8` and the unchanged
[24-document source bundle](../../experiments/results/agenda_boundary_2026_10_18.json.gz).
This is diagnostic evidence, not a promotion baseline or user acceptance.

## Frozen Text Replay

| Measure | Before | After |
| --- | ---: | ---: |
| Candidate items | 231 | 220 |
| False items: noise or fragments | 173 | 162 |
| Uncertain items | 8 | 8 |
| Missed business units, out of 96 | 48 | 48 |
| Previously covered business units lost | — | 0 |

Twelve previously labeled noise candidates disappeared. Filtering freed space
under an unchanged item limit, exposing one additional viewing instruction.
Two independent blind AI reviewers both labeled it noise. Retained candidates
reuse earlier judgments only when catalog, title, description, classification,
page, and result match; order is not a semantic identity field. The reference
is AI-reviewed, not human gold.

Median fallback extraction time was 4.7 ms across three measured runs per
document, after one warmup. This replay made no model calls and incurred no
inference API cost. That excludes review compute and machine operating costs;
it is not the latency or cost of the complete resolver.

The [new evidence bundle](../../experiments/results/agenda_notice_2026_10_19.json.gz)
records the original artifact hash, unchanged extraction configuration,
candidates, removed candidates, carried labels, blind delta reviews, source-code
hashes, and browser observations. The base commit plus those source-code hashes
identify the evaluated uncommitted implementation; the base commit alone does
not contain these changes.

## Controlled Live Correction

The normal resolver, not the fallback-only experiment, processed the same 24
catalogs. It selected Legistar for 19 and the existing LocalAI path for five.
The five provider calls returned empty responses and used the existing fallback.
Model settings, timeouts, item limits, and resolver thresholds stayed unchanged.

Stored agenda rows changed from 269 to 251. All 77 existing catalog/matter
associations survived, and nine additional matter-linked rows previously
excluded by filters were recovered. These row counts are not false-item or
business-coverage scores for the complete resolver.

Before writing, a fresh snapshot and dependency check confirmed no selected
item embeddings, votes, history, or spatial metadata would be discarded. The
correction used the existing agenda persistence function, which handles empty
replacement, and committed all selected records in one transaction. Scoped
document rows and catalog fields outside agenda hash/status fields matched the
snapshot; an aggregate digest of outside agenda rows stayed unchanged. All
targeted Meilisearch delete/add tasks succeeded.

No canonical source text, summaries, topics, people links, or model policy were
rewritten. Physical page-map repair was deferred rather than needed to justify
the display fix.

## Browser Checks

Playwright searched by each real document filename, expanded its card, and
opened Structured Agenda against the modified API and a fresh frontend build.
All 24 checks confirmed:

- Rendered titles exactly matched the stored API response.
- The API used the neutral `catalog_agenda_items` source label.
- The agenda panel did not claim “Local AI” and retained a verification warning.
- The original document URL remained available as “Open source document.”
- No item-level `#page=` link was invented from an unverified page number.

A 390-pixel mobile check retained a source-linked residential proposal and its
accessible source control without horizontal overflow. Clicking that source
control opened its expected URL. This does not verify remote availability or
the contents of every source document. Unverified page links were removed, not
repaired or replaced with another guessed page map.

## What Remains

The cleanup is deliberately conservative. A canceled Sunnyvale meeting still
has six fragments, down from eight; the two Mountain View cancellation records
each have four, down from six. City names, body headings, and sentence fragments
can remain. There is no document-wide cancellation classifier, and no guarantee
that a cancellation notice produces an empty agenda.

The existing task and maintenance wrappers can mark segmentation empty without
replacing old rows. That separate defect was not expanded into this change;
the controlled correction bypassed those wrappers and tested empty replacement
through the existing persistence function. A guarded rollback was prepared but
not executed.

Full resolver output did not receive a new independent business-labeling pass.
The 162 false items and 48 missed units above describe only the frozen text
fallback. This remains too noisy and incomplete to call dependable for users.

## Verification and Reproduction

Tests were written before implementation. Initial regressions reproduced notice
rows, lost matter-backed rows, false method labels, and invented page links.
The SQLite fixture initially lacked required place fields; that test setup was
corrected without changing production persistence.

Commands run locally include:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_agenda_notice_cleanup.py tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py tests/test_resultcard_agenda_status_refresh.py tests/test_search_sort_ui_guardrails.py tests/test_semantic_search_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_run_pipeline_orchestration.py tests/test_pipeline_batching.py tests/test_task_metrics.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
COMPOSE_DISABLE_ENV_FILE=1 PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

The full suite passed with 2,044 tests passed and 20 skipped. Earlier runs
failed because Compose loaded the local reader credential and coverage found
temporary Python scripts under the repository cache. The scripts were moved
outside the repository, and Compose's documented environment-file isolation
was used for tests only. No assertion, coverage scope, or threshold was changed.
The diagnostic exposure of the local reader key was followed by rotation and
revocation, preserving its action and index scope.

Frontend `npm ci`, `npm test` (44 passed), and `npm run build` ran in an isolated
source copy using the checked-in lockfile and Node 24.20.0 container. The stale
host React installation was not modified. Installation reported seven existing
dependency vulnerabilities; no audit fix or dependency update was attempted.

To reproduce the fallback, load each `documents` entry from the original bundle
and call `pipeline.agenda_extraction_fallback.run_agenda_extraction_pipeline`
with its content, `raw_provider_content=None`, the recorded segmentation mode,
and a logger. Compare candidate identities and labels with the new bundle.
Live correction additionally requires the exact catalog IDs, private runtime
credentials, a fresh dependency-checked snapshot, and a read-only resolver
preview. Do not substitute an arbitrary `--limit 24` backlog selection.

Authoritative PR CI and rollback execution are not verified by this local run.

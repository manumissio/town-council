# Agenda cleanup: fewer false items, more honest labels

Date: 2026-10-19. Compared against commit
`1383f41c446a17f33c3d765a89f57f0acd31e3e8` and the unchanged
[24-document source bundle](../../experiments/results/agenda_boundary_2026_10_18.json.gz).
This is diagnostic evidence, not a promotion baseline or user acceptance.

## Frozen Text Replay

The sections through PR Review Correction describe the initial candidate-only
cleanup. The later Cancellation-Only Correction supersedes its cancellation
limitation and reports the final replay and live state.

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

## PR Review Correction

Review found that adding these headings to the shared procedural list could
change whole-page parser selection. On a numbered page with two notice rows,
that switch lost an unrelated long business title. The new regression
`test_notice_cleanup_preserves_long_numbered_business` reproduced the loss
before the repair and passed afterward.

The new exclusions now apply only when accepting individual candidates and
filtering Legistar rows. The shared procedural list and parser thresholds are
unchanged from the base commit. A fresh replay of the same 24 documents produced
all 220 candidate payloads unchanged, including order and configuration. Median
fallback time rounded to 4.7 ms again. The quality counts above therefore stay
unchanged. The bundle's `review_followup` records the repaired source hashes;
the original hashes and browser observations remain historical evidence of the
initial implementation. Live database writes and browser checks were not
repeated for this repair; API and frontend production code did not change.

Two other review findings concerned test coupling. The Legistar regression now
uses the public resolver with outbound HTTP responses substituted at the
transport boundary. The agenda warning remains covered by rendered PDF and
HTML interactions; its redundant source-expression assertion was removed.

## Cancellation-Only Correction

The initial cleanup left false items on cancellation notices. Matching rendered
titles to stored rows did not establish that those rows were useful or correct.
The revised acceptance test requires no agenda items for the actual canceled
meeting notices and checks the source text alongside the displayed result.

| Same frozen fallback sample | Initial PR | Cancellation correction |
| --- | ---: | ---: |
| Candidate items | 220 | 199 |
| False items | 162 | 141 |
| Uncertain items | 8 | 8 |
| Missed business units, out of 96 | 48 | 48 |
| Previously covered business units lost | 0 | 0 |

All 21 newly removed candidates were already independently labeled noise.
Remaining candidate payloads reuse their existing labels by identity. No new
semantic labels were invented. Median fallback time was 4.9 ms; this replay
made no inference calls and incurred no inference API cost. These are still
fallback-only scores, not complete-resolver scores or human gold labels.

The normal resolver rerun produced 228 stored items, down from 251. Catalogs
6530, 6961, 8733, and 8769 now have zero rows and recorded empty status. The
operator approved clearing catalog 6961's nine wrong rows, including matter
links 10840, 10837, 10844, and 11856: its source cancels a Zoning Administrator
hearing, while those rows described Arts Commission business. All 82 matter
associations on unaffected records survived. Selected source/document fields
and the outside-agenda digest remained unchanged. Targeted indexing succeeded.

Playwright reopened all 24 records, read their Full Text, and inspected the
Structured Agenda. The four notice sources visibly announce cancellation and
display zero agenda cards with neutral empty-result wording. All original
source URLs remained available; no guessed page anchors or false AI-generation
labels appeared. For other records, a source quote was checked in Full Text,
and all displayed titles were recorded for content inspection, not accepted as
correct merely because they matched the API.

That inspection confirms an important remaining defect: catalog 3034's source
describes City Council board/commission vacancy interviews, but its agenda
shows unrelated Planning Commission material. The general Legistar
meeting-matching repair remains deferred. Noise and missed business elsewhere
also remain; this correction does not make the full agenda feature dependable.

Tests reproduced false cancellation items, unrelated structured-source
override, stale rows in all three successful-empty persistence paths, and
misleading empty UI copy before their respective fixes. Mixed agendas, attached
notices, provider output, long numbered business, and cancellation mentions are
covered through public behavior. The new resolver import exposed an existing
`int(object)` type error in parsed-order deduplication; converting the parser's
numeric order through text fixed typing without a suppression or policy change.

The bundle's `cancellation_followup` preserves the final replay, source hashes,
browser observations, and the explicit 6961 exception. Earlier bundle fields
remain historical evidence rather than being relabeled as the final run.
Rollback execution remains unverified.

Final local checks passed:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_agenda_cancellation_notices.py tests/test_agenda_notice_cleanup.py tests/test_agenda_fallback_boundaries.py tests/test_async_flow.py tests/test_agenda_worker_status_poison_pill.py tests/test_backlog_maintenance_laserfiche_guard.py
./.venv/bin/ruff check .
./.venv/bin/mypy
COMPOSE_DISABLE_ENV_FILE=1 PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-config=.coveragerc --cov-report=term-missing:skip-covered tests/
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py tests/test_env_example_profile_alignment.py
git diff --check
```

The focused run passed 97 tests; the coverage run passed 2,066 tests with 20
skipped and 84.65% coverage against the unchanged 71% floor. The isolated
frontend suite passed 44 tests and its build passed. Independent review approved
the production and test corrections. An initial local frontend image build used
the wrong build context and failed; rerunning with the correct isolated context
passed, with current static assets included. No tracked Dockerfile changed.

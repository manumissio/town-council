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
semantic labels were invented. Median fallback time was 4.4 ms in the final replay; it
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

The first corrective CI run failed the scoped Ruff formatter on the new resolver
payload layout. Formatting that file resolved the failure without changing
behavior. A later review found that page splitting dropped blank attachment
pages before the cancellation check counted them. The check now counts source
boundaries before empty text is removed. Four regression cases cover empty and
whitespace-only attachment pages through provider and public resolver output;
all failed before the repair. The provider fixture was corrected to the actual
prompt-continuation format without changing its expected business title. The
final focused extraction suite passed 72 tests, and the same-sample payloads
and quality counts remained unchanged. Fresh CI is required for this follow-up.

## Preserving Business After Inconclusive Extraction

A later review found that always persisting an empty proposal could delete
valid older items after a provider failure or low-signal extraction. An empty
proposal alone does not prove that a document has no business.

All three writers now validate replacement before calling persistence. When
stored items exist, an empty or whitespace-title-only proposal raises a specific
error unless the source is a confirmed cancellation-only notice. Stored rows
and their agenda hash survive. The existing Celery wrapper can still record a
failed attempt and retry; its status is not frozen at the previous success.
Catalogs without stored items can still record an empty result. The generic
persistence function remains an explicit replacement operation.

Eight regression cases failed before the guard was added: empty and blank-title
proposals through the task family, real Celery task wrapper, worker, and
maintenance entrypoints. Positive tests also confirm those entrypoints can
clear confirmed cancellations. The focused extraction, persistence, docs-link,
and profile-alignment command above passed 116 tests after this correction.

A fresh frozen replay retained the same 199 candidates, 141 false items, and
48 missed business units. The guard changes write safety, not those candidates.
The live backfill was not repeated unnecessarily: a read-only audit checks the
existing corrected state, while the public-entrypoint tests exercise the new
guard. No frontend code or displayed agenda content changed in this follow-up.
The complete coverage command passed 2,079 tests with 20 skipped and 84.68%
coverage against the unchanged 71% floor. Ruff, scoped formatter, Mypy, and
docs-link/profile-alignment checks passed. Fresh CI and independent review are
required before merging it.

## Complete-Source Evidence and Batch Continuation

Fresh review identified two more boundary gaps. Counting page markers was not
enough: a lone `Page 2` or `[PAGE 2]` still proves that the source is incomplete.
Cancellation recognition now abstains if any recognized page number is not 1,
while retaining the raw multiple-marker check for blank attachments.

The preservation error also escaped the normal and maintenance backfill
entrypoints. Both now handle that specific error through their existing
rollback and per-catalog failure paths. Stored rows and hash survive, failed
attempt metadata is recorded, and later selected catalogs still run. The
batch loop and Celery retry behavior are unchanged.

Tests-first evidence was 14 failures and 32 passes: eight page-marker cases,
two updated direct-worker cases, and four actual-workload continuation cases.
After the repair, all 46 cancellation tests passed. The workload tests use the
real selector, resolver, persistence, and loop, with database, inference, and
search boundaries controlled. In both modes they check an inconclusive first
record, a later cancellation, and later genuine business, including persisted
rows/hash and aggregate failed/empty/complete outcomes.

The same frozen 24-document replay retains 199 candidates, 141 false items,
and 48 missed business units, with no previously covered business lost. This
follow-up changes neither model settings nor item limits. A read-only audit
confirmed 228 stored items and all 82 unaffected matter associations. Playwright
reopened all 24 records after restarting the local API: the four cancellation
sources show zero cards and neutral empty wording, with original source links
and no guessed page anchors. The catalog 3034 mismatch remains deferred.

Final checks passed: 193 focused tests, 153 API/orchestration/frontend-contract
tests, Ruff, scoped formatter, Mypy, docs links, and independent code review.
The complete coverage command passed 2,091 tests with 20 skipped and 84.71%
coverage against the unchanged 71% floor. The reviewer independently reproduced
the prior code's 14 failures and passed 200 focused checks. Fresh PR CI and
current-head review are still required before merging.

## Declared Page Totals and Cancellation Spelling

Review identified a further supported-page gap: `Page 1 of 2` was not counted
by the existing inline page-marker parser. The cancellation check now inspects
declared current/total page numbers separately and abstains unless both are 1.
It does not change page splitting. Explicit single-page totals remain eligible;
zero or contradictory numeric declarations cannot confirm a cancellation.
Unsupported pagination formats and unmarked partial sources remain a limit,
not a claim that every incomplete packet can be detected.

The candidate-only exclusions now also recognize `MEETING CANCELLED`. Public
extraction and Legistar resolver tests retain live business while removing
unbacked headings. Business titles that mention canceled or cancelled hearings
remain. No shared procedural rule, model setting, item limit, or source field
changed.

Tests-first evidence was 18 failures and 66 passes. After the repair, all 84
focused cancellation/notice checks passed, including empty and blank-title
proposals on a source declaring two pages through the task family, real Celery
wrapper, worker, and maintenance persistence entrypoint. Existing rows and
their hash survive; prior batch-continuation tests remain in the suite. The
positive single-page path is tested separately from incomplete-page rejection.

The frozen 24-document replay still has 199 candidates, 141 false items,
48 missed business units, and no previously covered business lost. The live
read-only audit confirms 228 items and all 82 unaffected matter associations.
Playwright reopened all 24 sources and agenda panels after restarting the API:
the four notices still display zero cards, neutral empty wording, and original
source links. The catalog 3034 mismatch remains explicitly deferred.

The complete coverage command passed 2,117 tests with 20 skipped and 84.71%
coverage against the unchanged 71% floor. The focused matrix passed 219 tests;
the API/orchestration/frontend-contract matrix passed 153. Ruff, scoped
formatter, Mypy, and docs-link/profile checks passed. Independent review approved
the final diff and reproduced the 18 failures using prior production modules.
An extra formatter probe targeting files outside the configured scope reported
formatting differences; it was not an applicable gate, and no unrelated
formatting sweep was made. Fresh current-head CI and PR review must pass before
merging this follow-up.

## Current Item Counts Versus Attempt Metadata

Review found that a preserved agenda could still be reported as having zero
items: the derived-status API preferred a failed attempt's recorded count over
the actual rows. That confused last-attempt metadata with current stored
business. The API now always uses its existing catalog-filtered database count
query for `agenda_items_count`. Attempt count, status, timestamp, error, stored
rows, and hash remain unchanged. No writer, retry, model, or item-limit change
is needed.

The real-HTTP regression uses synthetic SQLite records. Its first setup crossed
SQLite's thread boundary; the final fixture follows the repository's isolated
StaticPool/check_same_thread pattern with request-local sessions and serialized
requests. SQLite's stored timestamp representation is compared before and after
the request, rather than assuming that SQLite preserves a timezone suffix.
SQLAlchemy 2.0 documentation was checked through Context7 for this test setup.

With that fixture, three stale-count cases failed before implementation and
three controls passed. After deleting the shortcut, all six pass. They cover
failed attempts retaining business, stale overcounts, zero rows, missing
metadata, complete/empty/unattempted statuses, and unrelated-catalog exclusion.
Counts agree with the actual agenda-items endpoint, while stored rows/hash and
attempt metadata are unchanged. Two existing database mocks now supply the
counts represented by their fixtures and assert those response values.

The API/query suite passed 69 checks; the focused agenda/orchestration/docs
matrix passed 219. Full coverage passed 2,123 tests with 20 skipped and 84.71%
coverage against the unchanged 71% floor. Ruff, configured formatter, Mypy, and
docs/profile checks passed.

After restarting the local API, Playwright read both endpoints for the same 24
catalogs. Every status count matched its returned agenda rows, totaling 228
items. The read-only audit still confirms all 82 unaffected matter associations.
This follow-up does not change extraction, so the prior candidate replay is not
relabelled as a new extraction run. It adds one COUNT execution where integer
metadata previously bypassed it; no API performance improvement is claimed.
Independent review and fresh current-head PR checks remain required before merge.

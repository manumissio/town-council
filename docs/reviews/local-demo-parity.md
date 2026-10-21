# Local App and Sample Preview

Last updated: 2026-10-21

## Scope and Checkpoints

Improve the shared local search journey without changing model settings, item
limits, security controls, live records, or baseline policy. The initial brief
required uncommitted changes; separate operator approval now authorizes PR
delivery. The local demo parity brief defines T0–T6.

- T0: baseline and gap matrix — complete
- T1: local first launch and browsing — complete locally
- T2: search and capability behavior — complete locally
- T3: record tabs and recovery — complete locally; actual inference not run
- T4: optional sample preview — complete locally
- T5: setup documentation — complete for tested paths; full bootstrap not run
- T6: final verification and handoff — complete locally; limits recorded below

## T0: Baseline

Started on clean `codex/agenda-notice-provenance` at
`233bd90307b5a52e2cec00aa23d585e36256c71b`. Fetched origin and created
`codex/local-demo-parity` from `origin/master` at
`ef523207e1a25079ce22a05251e94ca498e2f776`. No existing changes discarded.

The latest successful Pages workflow reports that same source revision:
[Pages run](https://github.com/manumissio/town-council/actions/runs/39529106276).
This identifies the workflow revision, not an independent browser asset hash.
The Pages builds API returned 404; the Actions deployment evidence is used instead.

Canonical references consulted: AGENTS verification matrix and permissions;
architecture read/write boundaries; security proxy and secret controls; testing
filesystem, HTTP, search-client and task boundaries; governance roster authority;
roadmap paused features; operations startup/sample preview; guardrail scope.

| Expectation | Observed baseline and owner | Intended behavior | Evidence/status |
|---|---|---|---|
| Useful first screen | `app/page.js` clears local blank queries; API requires q | Recent meetings, 20 per page | Source confirmed; browser local landing blank |
| Honest empty/error states | Search errors can also show no matches | Separate pending, outage, empty corpus, no matches | T1 tests pending |
| Filter choices | Metadata errors become cached empty lists; sample bodies incomplete | Retry errors; preserve city identifiers | API/source confirmed |
| Search ownership | Requests can overwrite newer results | Ignore canceled searches and serialize page loads | T2 regression pending |
| Semantic availability | Toggle offered without capability evidence | Disabled explanation or real service request | T2 pending |
| Trust labels | Summary freshness becomes “Grounded” | Freshness is not factual verification | T3 pending |
| Sample safety | Unknown fixture routes fall through to backend; fictional source links | Local failure; synthetic sources labeled | T4 pending |
| Setup | Startup does not ingest/index; sample serve command misses base path | Explain both and verify separate preview | T5 pending |

Playwright opened the deployed sample and local app. The sample shows ten
records, source links on example.com, three organization choices, and no result
count on blank browse. At 390px its document width was 390px. Shared controls
and cards remain the visual starting point. Desktop local screenshot:
`.cache/local-demo-parity-20261021/local-before.png` (ignored).

Host Node is 20.20.0, below the declared ^24.20.0 engine. Existing isolated
frontend dependencies have the identical lockfile SHA-256
`6b8907d8f9ae0693512112ab981e6d655aa5c03819d2aa46505678349cc56ba1`.
Use the already present Node 24.20.0 image and those dependencies, not an install.

## Implementation Boundaries

T1 extends only lexical blank reads, preserves semantic validation, and uses
shared page states. T2 extends metadata with stable city IDs and a nonsecret
semantic flag, adds request ownership to the existing search flow, and labels
controls. T3 reuses existing task polling/proxies and corrects unsupported labels
and refresh feedback. T4 confines fixture reads and fixes sample metadata/source
presentation. T5 updates README and operations. T6 runs applicable matrix rows,
builds sequentially, and inspects isolated runtime and static preview.

No new framework, dependency, migration, dashboard, runtime mode switch, or
production validator is planned. HTTP/Meilisearch/task fakes are contract tests,
not evidence that real inference ran. Runtime isolation must be checked before
starting any test service; the running town-council project is not test data.

## Verification Log

- PASS: `git status --short` — clean before work.
- PASS: `git fetch origin --prune`.
- PASS: `git switch -c codex/local-demo-parity origin/master`.
- PASS: `gh run list --workflow pages-demo.yml --limit 1 --json headSha,conclusion,url`.
- FAIL: `gh api repos/manumissio/town-council/pages/builds/latest` — HTTP 404.
- PASS: lockfile hash comparison; existing isolated dependencies match.
- NOT RUN: implementation tests, builds, isolated runtime checks, final review.

Next: T1 tests first. Runtime, CI, and external source availability are not yet verified.

## T1: Recent Browsing and Honest First-Load States

Changed `api/search_read_routes.py`, `api/search_semantic_routes.py`,
`frontend/app/page.js`, new `frontend/state/use-record-search.js`,
`tests/test_api.py`, and new `RecordSearch.behavior.test.js`. The focused hook
owns the search lifecycle formerly embedded in the page; it is not a second
implementation. Blank lexical queries browse recent meetings. Semantic queries
still require meaningful text. The page separates pending, errors, empty corpus,
and filtered no matches. A zero meeting count is checked with item inclusion
before describing the entire searchable corpus as empty.

- FAIL expected: `PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py -k 'lexical_browse or semantic_browse'` — 5 failed, 1 passed before implementation.
- PASS: same command after implementation — 6 passed.
- PASS: `PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py tests/test_query_builder_filters.py tests/test_query_builder_parity_search_vs_trends.py` — 75 passed.
- FAIL then PASS: Node 24 isolated hook tests. Initial missing hook, then corrected
  test DOM setup; final `node --test components/__tests__/RecordSearch.behavior.test.js` — 3 passed.

Isolation: scratch Compose uses only new `tc-parity_parity_db` and
`tc-parity_parity_search` volumes, loopback ports 13000/18000/17700, and no live
network or worker. API source mounts are read-only. No model service is started.
An initial relative-mount calculation was wrong; it created empty directories,
not live mounts. Those empty directories were removed, paths corrected, and
the disposable containers recreated. No live service was restarted.
The first browser read correctly shows an outage rather than an empty corpus:
the isolated frontend origin was not in the normal API CORS allowlist. The
scratch Compose configuration now uses the existing `ALLOWED_ORIGINS` setting
for its own loopback origin. No production CORS code or configuration changed.

Review 1: independent reviewer APPROVE on scope; runtime evidence remains
separate. Next: T2 metadata and search-ownership regressions.

## T2: Controls and Request Ownership

Changed search metadata routes/tests, `SearchHub.js`, the shared page, and hook
tests. Added `/search/capabilities`, returning only configured semantic enablement
without calling a provider. Metadata retains its existing city-label field and
adds identifier/label options; failures return 503 and are not cached as empty.
The UI retries filters/capabilities separately from search, disables unavailable
semantic mode, labels selects/toggles, and omits relevance during blank browsing.
The hook aborts obsolete searches and prevents overlapping page appends. Sample
search remains a bounded client-side keyword filter, not a semantic emulator.

- FAIL expected: `PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py -k 'metadata or capabilities'` — 4 failed, 8 passed.
- PASS: `PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py` — 71 passed.
- PASS: isolated Node 24 `node --test components/__tests__/RecordSearch.behavior.test.js` — 7 passed, including late responses, duplicate page requests, filtered reset, item-only corpus, and semantic failure.
- NOT RUN yet: final browser interaction matrix and complete gates.

Next: T3 record tabs and recovery. Existing task polling and same-origin routes
are retained, not replaced.

## T3: Record Feedback and Recovery

Changed `ResultCard.js` and its disclaimer tests. Reproduced “Grounded” in
Playwright using a synthetic cached summary with only freshness evidence. It is
now “Freshness unknown” for saved non-stale text. Status alone cannot prove the
version of a search-index summary. The hardcoded model attribution is
now “Saved summary.” Pending, failed, and unavailable segmentation have different
messages. Text/status loads have retry controls and abort on collapse/unmount.
Cached text and agenda rows remain visible after failed refreshes. Source links
require a real HTTP(S) URL. Saved page references are text, not invented PDF
fragment links; HTML sources and unknown page totals remain safe.
Sample records cannot link invented content to a municipal source.

- FAIL expected: isolated `node --test components/__tests__/ResultCard.ai-disclaimer.test.js` — 2 failed, 3 passed.
- PASS: same disclaimer test plus `ResultCard.polling-contract.test.js` — 15 passed.
  Existing polling tests cover success, provider/HTTP failure, bounded timeout,
  canceled pending work, and unmount cleanup. Polling implementation unchanged.
- NOT RUN yet: completed card/browser matrix and actual inference (no model run planned).

Disposable migration attempt failed because the API image does not include the
Alembic CLI package. No live schema was touched. Disposable ORM test fixtures
will use the approved database test boundary instead; this is not a new
production schema-creation path.

Next: T4 explicit sample preview and fixture isolation.

## T4: Explicit Synthetic Preview

Changed `lib/api.js`, sample metadata, shared page/card labels, and new
`SampleIsolation.test.js`. Only exact supported fixture routes resolve; unknown
reads and mutations throw locally. No backend fallback through sample helpers.
Existing sample action guards remain disabled. Metadata covers all fixture
bodies/types with readable city labels. Missing/stale records 706 and 710 remain
unchanged. Synthetic sources are not clickable originals. Missing-text examples
no longer suggest an unavailable re-extraction. No semantic emulation is offered.

- FAIL expected: isolated `node --test components/__tests__/SampleIsolation.test.js` — 2 failed before correction.
- FAIL during integration: full frontend suite found missing `Other` metadata;
  corrected from fixtures without weakening the assertion.
- PASS: isolated Node 24 `npm test` — 55 passed before additional >20/item scenario.
- NOT RUN yet: final sample export and expanded fixture scenario.

Next: T5 setup wording, then T6 complete local verification.

## T5: Setup Guidance

Changed README and operations startup/search/sample sections. They now separate
service startup from ingestion, explain browse/error/empty/processing states,
and describe optional semantic search. Sample export uses the existing build
wrapper with webpack, a base-path-aware standard-library HTTP server, and an
explicit return to a separate live build. No dependency files, Compose defaults,
proxy controls, models, item limits, or corpus maintenance changed.

- PASS: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py` — 2 passed.
- PASS: expanded sample tests — 3 passed, including 23 meetings plus one item.
- NOT RUN yet: production/live and sample build walkthrough.

Next: T6. Preliminary Ruff and Mypy pass. Four old source-inspection frontend
contracts fail because search moved from the page into its owning hook; update
their targets, retaining their sort/error/semantic/pagination intent. Behavioral
hook tests already cover those outcomes. This is not a compatibility facade.

## T6: Local Verification

### Independent Review

Review 2 initially BLOCKED with three P2 findings, all Class 1 within T3:

1. Database freshness did not certify the displayed index summary. Removed
   certification rather than adding another contract or validator.
2. Empty stored rows did not prove a processed document had no items. The
   message now requires positive existing `agenda_is_empty` evidence.
3. A late enqueue response could begin polling after unmount. All four enqueue
   handlers now use the card lifetime signal and stop before starting polling.

Tests first: `ResultCard.people-projection.test.js` reproduced all three
(3 failed, 10 passed). After correction, card/disclaimer tests passed (18).
Reviewer rechecked the fixes: APPROVE, no remaining P1/P2. This is a source
review verdict, not independent execution of the test suite.

Exact review evidence command:

```bash
grep -lE 'search|frontend|agenda|documentation|trust|evidence' docs/postmortems/*.md
```

Output:

```text
docs/postmortems/2026-08-02-remediation-program-prs-108-220.md
docs/postmortems/2026-08-03-pr-224-speculative-follow-up-plan.md
docs/postmortems/2026-08-13-baseline-v2-evidence-program-prs-230-262.md
```

### Automated Evidence

- PASS: `./.venv/bin/ruff check .` — all checks passed.
- PASS: `./.venv/bin/mypy` — 64 configured source files.
- PASS: `PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py tests/test_query_builder_filters.py tests/test_query_builder_parity_search_vs_trends.py tests/test_frontend_pages_config.py tests/test_resultcard_agenda_status_refresh.py tests/test_search_sort_ui_guardrails.py tests/test_semantic_search_ui_guardrails.py tests/test_demo_mode_ui_guardrails.py tests/test_docs_links.py` — 94 passed.
- PASS: `PYTHONPATH=. .venv/bin/pytest -q tests/test_demo_mode_ui_guardrails.py tests/test_repository_guardrails.py` — 565 passed.
- PASS: `COMPOSE_DISABLE_ENV_FILE=1 PYTHONPATH=. .venv/bin/pytest -q` — 2,132 passed, 20 skipped. This prevents test subprocesses from loading personal Compose secrets; it does not change application settings.
- PASS: isolated Node 24.20.0 `npm test` — 67 passed. Exact wrapper below.
- PASS: `git diff --check` after whitespace correction.

First full suite: FAIL (2 failed, 2,130 passed, 20 skipped). One source test
still required the old sample banner/page-local search. Its target was updated
to the hook and synthetic label. The other failure came from coverage discovery
including the ignored scratch `seed.py`; renamed the scratch note `seed.py.txt`
instead of weakening coverage policy. The full suite then passed.

Frontend test command, from the repository root:

```bash
docker run --rm \
  -v "$PWD/frontend:/src:ro" \
  -v "$PWD/.cache/agenda-quality-20261019/frontend/node_modules:/src/node_modules:ro" \
  -w /src node:24.20.0-alpine npm test
```

Dependencies were reused from the matching lockfile; no package installed.
Host Node 20 was not used for frontend evidence. Existing module-type and
dependency deprecation warnings remain. Local checks are not CI merge evidence.

### Browser Evidence

Playwright used the built live frontend on loopback port 13000, API 18000,
and fresh disposable Meilisearch/Postgres volumes. Source fixtures were labeled
synthetic and never inserted into the user's live index. Scratch Compose was
resolved to confirm ports and mounts; the project shares no live storage/network.
No worker, inference runtime, crawler, or live index-maintenance command was run.

| Scenario | Outcome and boundary |
|---|---|
| Healthy empty index | PASS: ingestion guidance, no no-match or sample hits |
| First indexed visit | PASS: 20 newest meetings; estimated count 25 |
| Load More | PASS: 25 unique meetings; no duplicates |
| Standalone items | PASS: excluded by default; explicit toggle shows item first |
| Filters and order | PASS: city/body/type filter, 12 matching meetings, oldest starts at meeting 02 |
| Query and reset | PASS: no-match message, reset restores 20 recent meetings |
| Service outage | PASS: request aborted through approved HTTP boundary; retry shown, neither empty nor no-match shown; retry restored results |
| Canonical content | PASS: Full Text contains seeded catalog 925 text through the existing protected proxy |
| Cached summary failure | PASS: controlled 503 leaves saved summary visible with error; no “Grounded” badge |
| Confirmed empty agenda | PASS: actual disposable DB status yields no-items feedback |
| Semantic disabled | PASS: actual configured-disabled API makes toggle unavailable |
| Semantic enabled/failing | PASS at mocked HTTP boundary: blank sends zero requests, failed query sends one semantic request, retry shows semantic result without changing mode |
| Mobile/keyboard | PASS: document width 390 at 390px viewport; Tab from named search input reaches Municipality |
| Partial, stale, blocked, processing summary | PASS: rendered component fixtures plus bounded existing task polling; no actual inference claim |
| Actual inference/semantic runtime | NOT RUN: intentionally no model download or generation; contract and browser boundary evidence only |

Two earlier content probes selected a different collapsed result and reported
false negatives. The corrected probe targeted the expanded `div.prose` and
verified the expected catalog text. Do not treat the earlier probes as passes.
An initial post-restart navigation returned connection reset; the subsequent
complete walkthrough ran after the disposable server was ready.

Evidence artifacts: `.cache/local-demo-parity-20261021/` contains live/sample
build logs, full pytest log, frontend test log, review red-test log, scratch
Compose definition, disposable seed note, and screenshots. None contains a
private corpus export. Model settings and item limits are unchanged.

### Builds and Sample Walkthrough

PASS: live and sample production builds with the existing wrapper, Node 24.20.0,
and webpack. The final builds ran sequentially while the test frontend was
stopped, avoiding shared `.next` output. An earlier live build overlapped its
development server; that result was discarded and repeated after stopping it.

```bash
# From the repository root; existing matching dependencies, no install.
docker run --rm -e NEXT_PUBLIC_API_URL=http://localhost:18000 \
  -e NEXT_TELEMETRY_DISABLED=1 \
  -v "$PWD/.cache/local-demo-parity-20261021/frontend:/app" \
  -v "$PWD/.cache/agenda-quality-20261019/frontend/node_modules:/app/node_modules:ro" \
  -w /app node:24.20.0-alpine npm run build -- --webpack

# Stop the disposable frontend before replacing its output with the sample.
docker run --rm -e NEXT_PUBLIC_DEMO_MODE=true -e STATIC_EXPORT=true \
  -e NEXT_TELEMETRY_DISABLED=1 \
  -v "$PWD/.cache/local-demo-parity-20261021/frontend:/app" \
  -v "$PWD/.cache/agenda-quality-20261019/frontend/node_modules:/app/node_modules:ro" \
  -w /app node:24.20.0-alpine npm run build -- --webpack
```

The runtime walkthrough also reused unchanged `docker/Caddyfile` in the isolated
project: Caddy -> Next.js -> protected API content returned HTTP 200 and the
expected catalog 925 text. API/search origins and same-origin reads work without
changing auth, CORS, or credential handling in tracked code. Test-origin CORS
configuration exists only in the ignored scratch Compose definition.

The first sample browser run caught a real regression: URL mapping occurred
before query assembly, producing `search.json&sort=newest` and HTTP 404. Tightened
the fake to require exactly `./demo/search.json` (red), assembled the API query
before the existing mapping (green), rebuilt, and repeated the browser check.
This is a T4 defect, not a new capability. A rendered missing-summary test also
failed before its impossible generation instruction was replaced with explicit
read-only guidance. Final source review APPROVE includes both corrections.

PASS: static HTTP preview at `http://localhost:13001/town-council/` displayed
10 fixture records, all eight body options, working tabs and disclaimers,
the missing summary in 706 and stale example in 710. Browser request capture
showed only fixture GETs for data: zero backend requests, zero mutations, and
zero fictional source links. Both desktop and 390px screenshots were inspected;
the mobile document width was 390px and keyboard Tab reached Municipality.
The wrapper restored its scratch `app/api` directory and left no backup;
tracked `frontend/app/api` is unchanged.

Sample preview commands tested with the isolated output:

```bash
mkdir -p .cache/local-demo-parity-20261021/sample-preview/town-council
cp -R .cache/local-demo-parity-20261021/frontend/out/. \
  .cache/local-demo-parity-20261021/sample-preview/town-council/
.venv/bin/python -m http.server 13001 --bind 127.0.0.1 \
  --directory .cache/local-demo-parity-20261021/sample-preview
```

### Final Parity and Limits

| Outcome | Disposition |
|---|---|
| Search-first layout, filters, cards, tabs, recent browse, reset, pagination | Met locally; API + component + browser evidence above |
| Empty/error/loading and cached-content feedback | Met locally; actual empty/disposable data plus approved HTTP/task fakes |
| Semantic service and inference execution | Intentionally not run; unavailable mode explained and HTTP/task boundaries tested, not real model quality |
| Optional sample | Met; separate build, synthetic/read-only label, no backend fallthrough |
| Startup documentation | Tested build/read path; `dev_up.sh` itself NOT RUN because it starts the live stack and bootstraps models |
| Public demo deployment | NOT RUN; deployed site inspected as baseline only, no push or deployment |
| External document uptime, extraction accuracy, related/lineage data absent from test corpus | Not established by this UI task; no new dashboard or research added |
| Existing date-only display | Residual pre-existing issue observed: locale formatting may display the prior calendar day. Not changed in this search/state assignment |

Security impact: no tracked security-sensitive route, proxy, Compose file, key,
or policy changed. Protected reads/actions keep the existing server-side proxy;
no browser credential added. New capability output contains a boolean only.
Sample routing is more restrictive. No schema, migration, dependency, model,
item-limit, people-policy, or baseline change.

The implementation was initially delivered uncommitted for review. The operator
subsequently authorized atomic commits, push, and PR creation. For the normal app after review,
use the existing `bash scripts/dev_up.sh` startup path and open port 3000;
expect recent indexed meetings or explicit empty-index guidance, not samples.
That startup command was not executed against the preserved live stack.
Use the operations sample-preview instructions for a separate read-only build.
CI was NOT RUN during local implementation. PR delivery now follows under the
operator's separate authorization; deployment remains outside this task.

## Handoff

PASS: final full Python rerun — 2,132 passed, 20 skipped. Final frontend run —
67 passed. Final source review APPROVE; report-only checks repeated afterward.
PASS: sample metadata failure retains ten cards; retry restores all eight body
choices. Missing metadata does not become an empty-corpus claim.

Only the `tc-parity` test services and its preview HTTP server were stopped.
Disposable named volumes were retained for inspection. The original live
services remain running. Browser snapshots/logs were moved under the ignored
`.cache/local-demo-parity-20261021/playwright/` directory, not committed.

At the implementation handoff, the working tree was dirty by design. PR delivery
groups the following paths into API, frontend, and documentation commits:

```text
README.md
api/search_read_routes.py
api/search_semantic_routes.py
docs/OPERATIONS.md
docs/reviews/local-demo-parity.md
frontend/app/page.js
frontend/components/ResultCard.js
frontend/components/SearchHub.js
frontend/components/__tests__/RecordSearch.behavior.test.js
frontend/components/__tests__/ResultCard.ai-disclaimer.test.js
frontend/components/__tests__/ResultCard.people-projection.test.js
frontend/components/__tests__/SampleIsolation.test.js
frontend/lib/api.js
frontend/public/demo/metadata.json
frontend/state/use-record-search.js
tests/test_api.py
tests/test_demo_mode_ui_guardrails.py
tests/test_frontend_pages_config.py
tests/test_search_sort_ui_guardrails.py
tests/test_semantic_search_ui_guardrails.py
```

No tracked file was deleted, moved, or renamed. Existing live data, model
settings, item limits, secrets, dependency pins, and baseline policy were not
modified. Review and local tests establish the changed UI/read contracts, not
extraction accuracy, external-source uptime, or actual inference availability.

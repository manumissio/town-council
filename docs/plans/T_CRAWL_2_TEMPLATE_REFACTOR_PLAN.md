# T-CRAWL-2: Fold Fork-Style Spiders onto the Template Layer

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** Belmont, Fremont, and Moraga each repeat the same archive-table
algorithm: request one listing, select rows, parse a date, apply the delta
boundary, build agenda/minutes documents, and emit an event. The duplication
makes source-specific fixes drift and preserves 15 crawler-specific Ruff
exceptions. T-CRAWL-2 moves that shared algorithm into the existing
`BaseCitySpider` module while retaining each city's selectors, date parsing,
URL handling, and byte-identical item contract.

**b) Canonical documents consulted.**

- `AGENTS.md`: crawler-politeness work requires Full planning, tests first,
  exact verification, and no test-seam compatibility layers.
- `docs/TESTING.MD`: characterization tests use recorded HTML and patch the
  implementation-owned database factory only.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff configuration owns exception scope;
  removed exceptions may not be replaced with inline suppressions.
- `SECURITY.md`: MD5 is retained only for non-security URL fingerprint
  compatibility and must be labeled accordingly.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-CRAWL-2 requires thin
  subclasses, byte-identical items, timezone-aware dates, and removal of every
  crawler-specific Ruff entry.
- `docs/reviews/architecture-review-2026-07-19.html`: duplicated spiders are a
  Phase 1 concern independent of the G3-blocked facade work.

**c) Remediation alignment.** This is T-CRAWL-2 in the crawler lane. Expand its
ownership before implementation to:

- `docs/plans/T_CRAWL_2_TEMPLATE_REFACTOR_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `ruff.toml`
- `tests/test_crawler_refactor_contract.py`
- `tests/test_repository_guardrails.py`
- `council_crawler/council_crawler/pipelines.py`
- `council_crawler/council_crawler/utils.py`
- `council_crawler/council_crawler/spiders/base.py`
- `council_crawler/council_crawler/spiders/ca_belmont.py`
- `council_crawler/council_crawler/spiders/ca_berkeley.py`
- `council_crawler/council_crawler/spiders/ca_cupertino.py`
- `council_crawler/council_crawler/spiders/ca_dublin.py`
- `council_crawler/council_crawler/spiders/ca_fremont.py`
- `council_crawler/council_crawler/spiders/ca_hayward.py`
- `council_crawler/council_crawler/spiders/ca_moraga.py`
- `council_crawler/council_crawler/spiders/ca_mtn_view.py`
- `council_crawler/council_crawler/spiders/ca_san_leandro.py`
- `council_crawler/council_crawler/spiders/ca_san_mateo.py`
- `council_crawler/council_crawler/spiders/ca_sunnyvale.py`
- `council_crawler/templates/legistar_cms.py`

No other tracked file may change. The repository guardrail contract was added
after the first implementation pass proved that clearing the crawler BLE001
entries also requires removing their stale exact-inventory rows.

**d) Decision-gate check.** T-CRAWL-2 does not depend on or foreclose G1-G5.
It does not alter crawler delay, robots behavior, concurrency, runtime
defaults, or soak policy.

## 2. Design

**e) Step-by-step approach.**

1. Register the Full plan, ownership, and active status before implementation.
2. Add characterization tests that execute the existing Belmont, Fremont, and
   Moraga parsers against fixed HTML and assert complete event/document values,
   excluding only the generated scrape timestamp while asserting it is aware
   UTC.
3. Add database-boundary tests proving expected SQLAlchemy failures retain the
   current full-crawl or rollback behavior while unexpected programming errors
   propagate.
4. Run the characterization tests green against the duplicated implementation
   before refactoring.
5. Add `TableArchiveSpider` to `spiders/base.py`. Its sole responsibility is
   the common listing request, row iteration, selector extraction, delta check,
   document construction, and event emission algorithm. It imports no city
   spider or facade.
6. Keep source deltas declarative through class attributes for start URL,
   container/row selectors, date text selectors, meeting-type selector, agenda
   selector, and minutes selector.
7. Keep only genuine behavior overrides:
   - Fremont parses its composed date with the city timezone.
   - Moraga percent-encodes relative agenda paths before `urljoin`.
8. Replace the three duplicated spiders with thin subclasses and rerun the
   characterization tests to prove item parity.
9. Clear the remaining crawler lint debt:
   - remove unused imports;
   - order positional splats before fixed template arguments;
   - use city-aware current dates in San Mateo;
   - pass `usedforsecurity=False` to the existing MD5 URL fingerprint;
   - narrow database handlers to `SQLAlchemyError`.
10. Remove all 15 `council_crawler` per-file-ignore entries from `ruff.toml`.
11. Run focused crawler tests, guardrail tests, Ruff, Mypy, docs links, and the
    complete Python suite with coverage.
12. Run simplification and independent review, apply eligible findings,
    commit, push, open one PR, and watch CI and review to a decided state.

New functions remain focused:

- `TableArchiveSpider.start_requests`: emit the configured listing request.
- `TableArchiveSpider._iter_archive_rows`: pair each row with an optional
  container-level meeting type.
- `TableArchiveSpider._extract_date_text`: compose configured date fragments.
- `TableArchiveSpider._parse_record_date`: parse a listing date.
- `TableArchiveSpider._resolve_agenda_url`: normalize an agenda link.
- `TableArchiveSpider._build_documents`: build agenda/minutes document maps.
- `TableArchiveSpider.parse_archive`: coordinate the shared algorithm.

`base.py` remains below 300 lines after the extraction. No new template file is
created.

**f) Reuse audit.** Extend `BaseCitySpider`, `parse_date_string`,
`url_to_md5`, `create_event_item`, and `should_skip_meeting`. Do not add a
second document schema, item factory, parser registry, middleware, or
compatibility wrapper. The duplicated city parser bodies are deleted in the
same change.

Rejected alternatives:

- Add a new CivicPlus template module: rejected because the task forbids new
  template files and Moraga is not the same source family.
- Keep three parsers and extract only document construction: rejected because
  most duplicate control flow and selector handling would remain.
- Convert these cities to Legistar templates: rejected because their checked-in
  HTML contracts are not Legistar API/CMS contracts.
- Silence Ruff inline: rejected because it would bypass the ratchet.

**g) Data contracts.** Existing Scrapy `Event` and document dictionaries remain
unchanged. Characterization tests assert names, division IDs, dates, sources,
source URLs, meeting types, document order, categories, resolved URLs, and URL
hashes. No new external payload model is introduced.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None under `AGENTS.md`. `url_to_md5` retains
MD5 solely for stable URL identifiers and adds `usedforsecurity=False`; hash
bytes do not change.

**j) Secrets.** None.

**k) Person data.** None created, linked, aggregated, or exposed.

**l) Untrusted input.** Municipal HTML, dates, and links remain untrusted at
Scrapy response callbacks. Existing XPath extraction, `parse_date_string`,
strict Fremont parsing, `Response.urljoin`, and Moraga quoting remain the
sanitization and normalization boundaries. No HTML is rendered.

## 4. Code Health

**m) GED conformance sweep.** Shared methods remain below 40 lines and two
nesting levels. Selectors and source URLs are named class constants. Database
handlers catch `SQLAlchemyError`, roll back or fall back with context, and
preserve documented invariants. City dates use `ZoneInfo` and aware
`datetime.now`. No inline environment read or naive timestamp is introduced.

**n) Antipattern scan, plan pass.**

- A1/H1: Context7 `/scrapy/scrapy` verified Scrapy 2.16-compatible request
  callbacks, callback item yields, XPath selectors, and `Response.urljoin`.
- B1: `TableArchiveSpider` is required by the explicit template-refactor task
  and replaces three implementations; no registry or manager is added.
- C1/F1: the three old parser bodies are deleted, not retained as fallbacks.
- D1-D3: tests characterize external item values and error outcomes; no skip,
  tolerance, private-state assertion, or patched facade is added.
- E1/E2: one-line thin-spider lint repairs are explicitly authorized; no broad
  formatting sweep occurs.
- A2-A4, B2-B3, C2, E3, F2, H2-H4: no planned violation.

**o) Ratchet interaction.**

- Old crawler per-file-ignore entries: 15.
- New crawler per-file-ignore entries: 0.
- Old isolated violation count for F401/B026/DTZ007/DTZ011/S324: 18.
- Added or widened exceptions: none.
- `BaseCitySpider` and crawler pipelines leave the BLE001 boundary list by
  catching `SQLAlchemyError`.

**p) Dead code and duplication audit.** Delete the three duplicate
`start_requests`/`parse_archive` bodies, unused imports, and all crawler Ruff
exceptions. Reuse existing item/date/hash helpers. Expected net production
delta is negative despite the shared base implementation.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Relative and absolute agenda URLs resolve exactly as before.
2. Moraga paths containing spaces retain percent-encoded agenda URLs.
3. Missing agenda or minutes links omit only that document.
4. Missing or malformed dates remain skipped.
5. Delta-boundary dates remain skipped.
6. Fremont container-level meeting types and composed dates remain intact.
7. Document order stays agendas first, then minutes.
8. URL hash values remain byte-identical.
9. Expected SQLAlchemy failures preserve full-crawl/rollback behavior.
10. Unexpected programming errors are no longer swallowed.
11. San Mateo date windows use the configured city timezone.
12. Every former crawler Ruff exception is genuinely unnecessary.
13. Existing Legistar and thin-spider behavior remains unchanged.

**r) Tests.**

| Test | Scenarios |
|---|---|
| Belmont characterization | 1, 3-5, 7-8 |
| Fremont characterization | 1, 3-8 |
| Moraga characterization | 1-5, 7-8 |
| Base database-boundary tests | 9-10 |
| Crawler pipeline failure tests | 9-10 |
| Existing `test_url_to_md5` | 8 |
| Isolated and configured Ruff checks | 11-12 |
| Existing crawler/spider suites | 5, 11, 13 |
| Complete coverage suite | 1-13 regression check |

Characterization tests are committed before production refactoring and must
pass both before and after it.

**s) Fakes and mocks.** Fixed `HtmlResponse` objects use the approved recorded
HTML boundary. Tests patch `council_crawler.spiders.base.db_connect` or replace
the pipeline's session factory, both approved database boundaries. No facade,
re-export, or unit-under-test method is patched.

**t) Verification rows.** Apply guardrail/tooling because `ruff.toml` changes,
docs-only because the remediation docs change, and the full cross-cutting
suite because crawler base and persistence boundaries change.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-crawl-2-template-refactor
```

Baseline and characterization:

```bash
./.venv/bin/ruff check --isolated \
  --select F401,B026,DTZ007,DTZ011,S324 council_crawler
PYTHONPATH=. .venv/bin/pytest -q tests/test_crawler_refactor_contract.py
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff check --isolated \
  --select F401,B026,DTZ007,DTZ011,S324,BLE001 council_crawler
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_crawler_refactor_contract.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_spiders.py \
  tests/test_cupertino_spider.py \
  tests/test_dublin_spider.py \
  tests/test_legistar_api_spider_contract.py \
  tests/test_san_mateo_spider.py \
  tests/test_utils.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q \
  --cov --cov-config=.coveragerc --cov-report=term-missing:skip-covered tests/
git diff --check
git status --short
```

**v) Rollback.** Revert the T-CRAWL-2 merge commit and rerun Ruff, Mypy,
focused crawler tests, repository guardrails, docs links, and the complete
coverage suite. No migration, data remediation, cache purge, or external-state
cleanup is required. Rollback restores duplicated spiders and 15 Ruff
exceptions.

**w) Docs sync.** Update only the remediation plan and this implementation
plan. README, ADR, operations, performance, testing, architecture, security,
API, and data-governance docs do not change because crawler behavior and
operator commands remain stable.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject new template files,
surviving parser copies, inline suppressions, expanded exception lists,
changed item fields/order, crawler-setting drift, facade patch targets,
unrelated formatting, or files outside the owned set.

**y) Evidence.** Report characterization-before/after outcomes, old/new line
and Ruff-exception counts, all commands in 6u, item-parity evidence,
independent-review findings, commits, PR URL, unresolved-thread count, and CI
state. Mark unrun checks `NOT VERIFIED`.

**z) Deviations.** The operator approved adding
`tests/test_repository_guardrails.py` after the guardrail suite proved that
the exact BLE001 inventory must ratchet with `ruff.toml`. The required local
planning and pre-commit subagent could not start because the agent thread limit
was reached; an independent local Codex review ran against the uncommitted diff
instead, with current-head GitHub review retained as the delivery backstop. Any
other changed path, retained crawler exception, changed item contract, skipped
test, unresolved P1/P2, or unrun required check is a blocker.

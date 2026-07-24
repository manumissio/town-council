# T-CRAWL-1: Use an Honest Crawler Identity

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** Town Council currently sends a Chrome browser identity while
crawling municipal sites. That conflicts with the crawler's responsibility
comment and prevents site operators from identifying or contacting the
project. T-CRAWL-1 replaces only that identity with a project-specific user
agent while preserving robots.txt compliance, request delay, concurrency, and
all crawler output contracts.

**b) Canonical documents consulted.**

- `AGENTS.md`: crawler politeness changes require operator approval, Full
  planning, tests first, and complete verification.
- `SECURITY.md`: no listed trust boundary changes, but outbound identity must
  not disclose a secret.
- `docs/TESTING.md`: tests assert settings exposed by the crawler module without
  adding a runtime seam.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff owns repository lint scope; no
  exception may be added.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-CRAWL-1 owns honest crawler
  identity and must preserve `ROBOTSTXT_OBEY` and `DOWNLOAD_DELAY`.
- `docs/reviews/architecture-review-2026-07-19.html`: crawler work is an
  independent Phase 1 lane and does not depend on Phase 2.

**c) Remediation alignment.** This is T-CRAWL-1 in the crawler lane. Its
operator-approved ownership is:

- `docs/plans/T_CRAWL_1_HONEST_CRAWLER_IDENTITY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `council_crawler/council_crawler/settings.py`
- `council_crawler/council_crawler_readme.md`
- `tests/test_crawler_settings_contract.py`

No other tracked file may change.

**d) Decision-gate check.** T-CRAWL-1 does not depend on or foreclose G1-G5.
The operator's instruction to continue the approved remediation plan
authorizes this crawler-politeness change. T-SEC-4 remains deferred because G2
is unresolved.

## 2. Design

**e) Step-by-step approach.**

1. Register this plan, mark merged T-SEC-3 complete, and mark T-CRAWL-1 active.
2. Add a failing settings-contract test before changing crawler settings.
3. Assert the crawler uses
   `TownCouncilBot/1.0 (+https://github.com/manumissio/town-council)`.
4. Assert `ROBOTSTXT_OBEY is True` and `DOWNLOAD_DELAY == 2` so the identity
   change cannot silently weaken politeness.
5. Replace the browser user agent and correct its adjacent intent comment.
6. Add one crawler-readme note that identifies the bot and preserved
   politeness settings.
7. Verify the effective project settings with Scrapy's `settings --get`
   command, run targeted crawler tests, then run all required repository gates.
8. Obtain an independent pre-commit review, apply eligible findings, commit,
   push, open a PR, and watch CI and current-head review to a decided state.

No new function or module is introduced.

**f) Reuse audit.** Extend the existing Scrapy settings module and crawler
readme. The new test uses Scrapy's existing settings CLI in a subprocess so it
does not contaminate the package state used by older spider tests. No
production wrapper, settings registry, environment variable, custom
middleware, or duplicate configuration is added. No existing runtime path is
superseded beyond the single browser user-agent literal.

**g) Data contracts.** No item, API, database, task, or provider contract
changes. The only outbound HTTP metadata change is the default `User-Agent`
header populated by Scrapy's existing `UserAgentMiddleware`.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path is touched.
Municipal servers gain truthful project identity and a public repository
contact URL. No additional internal information is exposed.

**j) Secrets.** None. The user agent contains only a public project URL.

**k) Person data.** None created, linked, aggregated, or exposed. G4 is
unaffected.

**l) Untrusted input.** No new input is parsed or rendered. Scraped responses
continue through existing spider and pipeline boundaries.

## 4. Code Health

**m) GED conformance sweep.** The change replaces one constant and two nearby
comments. It adds no function, nesting, exception handler, timestamp,
environment read, or magic operational threshold. Existing single-quoted
settings style is preserved to avoid unrelated formatting.

**n) Antipattern scan, plan pass.**

- A1/H1: Context7 verified Scrapy's `USER_AGENT`, `ROBOTSTXT_OBEY`,
  `DOWNLOAD_DELAY`, and `scrapy settings --get` behavior against current Scrapy
  documentation; the repository pins Scrapy 2.16.0.
- D3: exact user-agent text is the externally observable crawler identity and
  is therefore an appropriate contract.
- B1/F1: no middleware, wrapper, helper, or duplicate settings source.
- D1: robots and delay assertions preserve, rather than weaken, current policy.
- E1/E2: only the five owned files may change.
- A2-A4, B2-B3, C1-C2, D2, E3, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, formatter scope,
Mypy scope, or coverage threshold changes. The touched settings file has no
task-specific exception to clear.

**p) Dead code and duplication audit.** Delete the spoofed Chrome literal and
its inaccurate implication that the browser string identifies Town Council.
Reuse all existing Scrapy machinery. Expected runtime delta is one changed
setting line and concise comment cleanup.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. The user agent remains a browser impersonation.
2. The project identity lacks a public contact or repository URL.
3. `ROBOTSTXT_OBEY` changes from `True`.
4. `DOWNLOAD_DELAY` changes from two seconds.
5. An unrelated crawler setting changes in the same task.
6. Scrapy resolves a different effective project setting than the imported
   module exposes.
7. Existing spider output or parser behavior regresses.

**r) Tests.**

| Test or command | Scenarios |
|---|---|
| New `test_crawler_identifies_town_council_and_preserves_politeness` | 1-5 |
| `scrapy settings --get USER_AGENT/ROBOTSTXT_OBEY/DOWNLOAD_DELAY` | 1-4, 6 |
| Existing crawler and spider tests | 7 |
| Complete Python suite | 1-7 regression check |

The new test is written and run red before changing `settings.py`.

**s) Fakes and mocks.** None. The unit test uses the approved subprocess
boundary and Scrapy's existing CLI. No network request is made and no
application symbol is patched.

**t) Verification rows.** Crawler politeness is not a named matrix row, so run
Ruff, the new contract, existing crawler/spider tests, docs links, and the
complete Python suite. CI's complete Python and frontend gates remain
authoritative for merge.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-crawl-1-honest-crawler-identity
```

Tests-first evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_crawler_settings_contract.py
```

Expected before implementation: failure showing the Chrome user agent.

Effective settings:

```bash
cd council_crawler
../.venv/bin/scrapy settings --get USER_AGENT
../.venv/bin/scrapy settings --get ROBOTSTXT_OBEY
../.venv/bin/scrapy settings --get DOWNLOAD_DELAY
cd ..
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_crawler_settings_contract.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_spiders.py \
  tests/test_cupertino_spider.py \
  tests/test_dublin_spider.py \
  tests/test_legistar_api_spider_contract.py \
  tests/test_san_mateo_spider.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/
git diff --check
git status --short
```

**v) Rollback.** Revert the T-CRAWL-1 merge commit and rerun Ruff, the crawler
settings contract, crawler/spider tests, docs links, and the complete suite.
No migration, data remediation, secret rotation, or external-state cleanup is
required. Rollback knowingly restores browser impersonation.

**w) Docs synchronization.**

- Remediation plan: mark T-SEC-3 complete, register T-CRAWL-1 ownership and
  active status, and add the implementation-plan link.
- Crawler readme: identify the bot and preserved robots/delay policy.
- README, ADR, operations, architecture, security, testing, and data-governance
  docs: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject any middleware,
environment option, alternate identity path, changed delay/concurrency/robots
setting, unrelated formatter churn, test weakening, secret, or file outside
the five-file ownership set.

**y) Evidence.** Report the tests-first failure; effective Scrapy settings;
Ruff, Mypy, focused crawler tests, docs links, complete-suite counts;
independent-review findings; commits; PR URL; unresolved-thread count; and CI
state. Mark anything unrun as `NOT VERIFIED`.

**z) Deviations.** The planned direct settings import was replaced with the
Scrapy settings CLI after full-suite evidence showed that the direct import
cached the outer namespace package and broke older spider imports. Any
additional file, crawler setting change beyond `USER_AGENT`, network crawl,
skipped test, unresolved P1/P2, or unrun required check is a blocker.

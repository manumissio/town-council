# T-DD-1B: Consolidate City Event-Graph Mutation

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** The full city flush and verification-window reset independently
implement the same live event-graph accounting, shared-catalog protection, and
deletion policy. Their event selection, stage-table behavior, safety defaults,
validation, and reports are intentionally different. T-DD-1B removes only the
proven duplicate mutation policy so future fixes cannot protect shared catalogs
in one command but not the other.

**b) Canonical documents consulted.**

- `AGENTS.md`: preserve command behavior, use the database boundary, avoid
  facade compatibility seams, and run complete verification for cross-cutting
  refactors.
- `docs/TESTING.MD`: assert persisted database and CLI outcomes; do not add
  helper-call assertions or production seams for tests.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff owns lint scope and exception policy.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: DEDUP-D owns the two commands
  and requires proof of identical policy before extraction.
- `docs/reviews/architecture-review-2026-07-19.html`, Candidate 05: separate
  city mutation from health probes, keep CLI interfaces stable, and extract
  only the identical reference-deletion invariant.
- `docs/OPERATIONS.md`: flush is dry-run by default and deletes stage state;
  pending-city rewind is dry-run through its supported wrapper and preserves
  stage state.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md`: no security-sensitive or person
  data boundary is affected.

**c) Remediation alignment.** T-DD-1B owns exactly:

- `docs/plans/T_DD_1B_CITY_STATE_MUTATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/OPERATIONS.md` (pending-city rewind deletion list only)
- `scripts/city_state_mutation.py` (new)
- `scripts/flush_city_pipeline_state.py`
- `scripts/reset_city_verification_state.py`
- `tests/test_city_state_mutation_cli.py` (new)
- `tests/test_flush_city_pipeline_state.py`
- `tests/test_reset_city_verification_baseline.py` (new)
- `tests/test_reset_city_verification_state.py`

T-PLAT-3 is complete, so the former runbook serialization constraint is
satisfied. No task with overlapping ownership may run concurrently.

**d) Decision-gate check.** No G1-G5 gate is required or foreclosed. Runtime
defaults, city rollout policy, schema, and soak comparability remain unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan, exact ownership, T-PLAT-3 completion, and T-DD-1B
   activation in the remediation ledger before implementation edits.
2. Decompose the touched reset test file before adding cases: move its
   timestamp formatting, baseline capture, and record-date anchor tests into
   `tests/test_reset_city_verification_baseline.py`. Keep local database setup
   in each focused file rather than creating a fixture framework.
3. Add characterization tests before refactoring. Prove both command defaults
   and JSON contracts through subprocess execution against a temporary SQLite
   database.
4. Strengthen persisted-state tests for catalogs shared outside the selected
   event set, linked and unrelated data issues, documents without catalogs,
   stage-row asymmetry, idempotency, and transactional rollback. Use a SQLite
   `BEFORE DELETE ON catalog` trigger that raises `ABORT` to prove a late
   failure restores every earlier stage/live/data-issue mutation.
5. Add `scripts/city_state_mutation.py` as the single owner of:
   - the selected event-graph ID contract;
   - total-versus-selected catalog reference accounting;
   - deletion of selected data issues, events/documents, and catalogs no
     longer referenced outside the selected event set.
6. Keep event selection in each command. Flush selects every city event;
   reset retains its `scraped_datetime` and optional `record_date` anchor.
7. Keep stage discovery and deletion only in the flush command.
8. Keep city validation, CLI flags, dry-run defaults, output fields, remaining
   summaries, and transaction commit in their current command owners.
9. The shared mutation function changes the caller-owned SQLAlchemy session
   but never commits. This keeps flush stage and live deletion atomic.
10. Delete both duplicate live-graph implementations and their duplicate
   dataclasses in the same change.
11. Run simplification, a fresh independent pre-commit review, all verification,
    atomic commits, PR delivery, and bounded review/CI repair.

New functions have one responsibility:

- `city_ocd_division_id(city)`: build the existing California place ID.
- `collect_event_graph_mutation(session, selected_events)`: collect affected
  IDs and determine which catalogs have no references outside the selection.
- `delete_event_graph(session, mutation)`: apply the shared live-row mutation
  without committing.

The shared module imports models and SQLAlchemy only. It never imports either
CLI. Both CLIs import the shared module rather than copied symbols.

**f) Reuse audit.** Move the existing reference-count and deletion blocks
rather than rewriting them. Existing SQLAlchemy `Session.query`,
`selectinload`, grouped counts, `Query.delete(synchronize_session=False)`,
`Session.delete`, and `Session.commit` behavior remains unchanged. No existing
module owns this maintenance mutation policy; metrics and generic city-scope
modules do not own database deletion.

Rejected alternatives:

- Extract all command logic: rejected because stage and temporal policies
  differ materially.
- Share only the OCD identifier helper: rejected as too shallow to justify a
  module.
- Put mutation logic in one CLI and import it from the other: rejected because
  it makes one command a facade for another.
- Generalize a maintenance framework: rejected as unrequested machinery.

**g) Data contracts.** A frozen `CityEventGraphMutation` dataclass carries
event, document, referenced-catalog, unreferenced-catalog, and data-issue IDs.
Each command retains its existing JSON dictionary contract. No raw external
input crosses a new boundary.

**h) Schema/migration impact.** None. Existing cascade and transaction behavior
remain authoritative.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None. The commands remain local maintenance
tools and add no endpoint or privilege. Apply operations retain the documented
writer-quiescence requirement.

**j) Secrets.** No credentials, keys, environment variables, or defaults
change.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** City slugs and timestamp strings remain parsed by the
same command boundaries. Database content remains trusted only after SQLAlchemy
model loading. No scraped content is rendered or newly parsed.

## 4. Code Health

**m) GED conformance sweep.** New functions use domain names, complete type
annotations, at most two parameters, one responsibility, and no nesting beyond
two levels. The shared module adds no environment reads, timestamps, broad
handlers, or import-time side effects. Callers retain commit and rollback
ownership.

**n) Antipattern scan, plan pass.**

- A1/H1: SQLAlchemy 2.0.38 is pinned. Context7 `/websites/sqlalchemy_en_20_orm`
  verifies the retained legacy query, eager-load, bulk-delete, object-delete,
  and commit semantics.
- B1/F1: one focused mutation owner replaces two proven duplicate blocks; no
  manager, registry, base class, or `utils` module.
- B2/C1/C2: no compatibility export, wrapper, old implementation, or new patch
  seam survives.
- D1-D3: tests assert CLI JSON and persisted rows; no skip, tolerance change,
  helper call count, or private-symbol assertion.
- E1-E3: only ten owned files change; no unrelated formatting.
- A2-A4, B3, F2, H2-H4: no planned violation.

**o) Ratchet interaction.** Neither command has a dedicated Ruff exception.
No rule, allowlist, source scope, coverage floor, or typed-subtree boundary
changes.

**p) Dead code and duplication audit.** Delete `RewindCounts`, duplicate live
fields from `FlushCounts`, both repeated reference-count blocks, both repeated
live deletion blocks, and one duplicate city-ID helper. Event selection,
stage mutation, reports, and timestamp helpers remain local. Production lines
should decrease overall despite the new focused module.

## 5. Testing

**q) Edge and failure scenarios.**

1. A selected event shares a catalog with an unselected event in the same city.
2. A selected event shares a catalog with another city.
3. A selected document has no catalog.
4. Selected data issues are deleted; unrelated issues remain.
5. Flush deletes stage rows; reset preserves them.
6. Flush defaults to dry-run; direct reset defaults to apply.
7. Reset timestamp and record-date boundaries remain exact.
8. Both commands remain idempotent.
9. A late database error rolls back the complete caller-owned transaction.
10. Empty selections return zero counts and stable JSON fields.

**r) Test mapping.**

| Test area | Scenarios |
|---|---|
| New subprocess CLI characterization | 6, 10 |
| Updated flush database tests | 2-5, 8-9 |
| Updated reset database tests | 1, 3-5, 7-9 |
| Split reset baseline tests | 7 |
| Existing onboarding runner contracts | 5-8 |
| Ruff, Mypy, coverage, and complete suite | 1-10 regression check |

Tests are committed to the working tree and run before implementation.
Characterization is expected to pass because this is a behavior-preserving
refactor; failures stop implementation.

**s) Fakes and mocks.** Database tests use the approved SQLite/sessionmaker
boundary. CLI tests use real subprocesses and a temporary database. No facade,
re-export, helper-call patch, or injectable callable is introduced.

**t) Verification rows.** No named row covers these maintenance scripts. Run
focused command tests, affected onboarding orchestration tests, Ruff, Mypy,
docs links, the coverage gate because a production module is added, and the
complete suite before handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-dd-1b-city-state-mutation

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_city_state_mutation_cli.py \
  tests/test_flush_city_pipeline_state.py \
  tests/test_reset_city_verification_baseline.py \
  tests/test_reset_city_verification_state.py

./.venv/bin/ruff check .
./.venv/bin/mypy
./.venv/bin/mypy scripts/city_state_mutation.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_city_state_mutation_cli.py \
  tests/test_flush_city_pipeline_state.py \
  tests/test_reset_city_verification_baseline.py \
  tests/test_reset_city_verification_state.py \
  tests/test_city_onboarding_runner.py \
  tests/test_city_onboarding_wave_script_contract.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery:

```bash
git push -u origin codex/t-dd-1b-city-state-mutation
gh pr create --base master --head codex/t-dd-1b-city-state-mutation \
  --title "T-DD-1B: Consolidate city event-graph mutation"
```

**v) Rollback.** Revert the T-DD-1B merge commit and rerun focused command
tests, onboarding contracts, Ruff, Mypy, docs links, coverage, and the complete
suite. No migration, data repair, config restoration, or external cleanup is
required.

**w) Docs sync.** Update this plan, the remediation ledger, and only the
pending-city rewind deletion list in `docs/OPERATIONS.md` so its existing
`data_issue` deletion is explicit. Command names, flags, defaults, and safety
requirements remain unchanged. README, ADR, architecture review, testing
policy, guardrails, API contracts, security, and governance docs remain
unchanged.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject shared stage or event
selection, helper commits, compatibility exports, CLI-to-CLI imports, generic
frameworks, changed flags/defaults/JSON, widened exceptions, weakened tests,
or edits outside ownership.

**y) Evidence.** Report characterization results, all commands in 6u,
planning/pre-commit findings, applied fixes, commit hashes, PR URL, unresolved
threads, and final CI state. Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any additional file, altered
operator contract, schema/runtime change, unowned refactor, skipped review,
unresolved P1/P2, or unrun required check is a blocker.

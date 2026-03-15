# City Onboarding Status

Last updated: 2026-03-15

This sheet tracks rollout readiness and quality gates per city.
Machine-readable rollout truth lives in `city_metadata/city_rollout_registry.csv`; this page mirrors that registry for operator review.

| city_slug | provider | spider_exists | enabled | quality_gate | last_verified |
|---|---|---:|---:|---|---|
| berkeley | native | yes | yes | pass | 2026-02-17 |
| cupertino | legistar | yes | yes | pass | 2026-02-17 |
| fremont | existing | yes | no | pending | - |
| hayward | existing | yes | yes | pass | 2026-03-15 |
| san_mateo | existing | yes | yes | pass | 2026-03-14 |
| sunnyvale | existing | yes | yes | pass | 2026-03-15 |
| san_leandro | existing | yes | no | pending | - |
| mtn_view | existing | yes | no | pending | - |
| moraga | existing | yes | no | pending | - |
| belmont | existing | yes | no | pending | - |
| orinda | iqm2 | no | no | pending | - |
| brisbane | tbd | no | no | pending | - |
| danville | tbd | no | no | pending | - |
| los_gatos | tbd | no | no | pending | - |
| los_altos | tbd | no | no | pending | - |
| palo_alto | tbd | no | no | pending | - |
| san_bruno | tbd | no | no | pending | - |
| east_palo_alto | tbd | no | no | pending | - |
| santa_clara | sire/custom | no | no | pending | - |

Quality gate policy (per city):
- crawl success >=95% over 3 runs
- non-empty extraction >=90%
- segmentation complete/empty >=95% (failed <5%)
- searchable in API and Meilisearch facets

Activation workflow note:
- Hayward + San Mateo wave-1 activation uses `scripts/onboard_city_wave.sh` plus `scripts/evaluate_city_onboarding.py`.
- Wave membership and `enabled` state are sourced from `city_metadata/city_rollout_registry.csv`.
- Extraction and segmentation gates are now evaluated against the onboarding run's touched catalog corpus for that city; full historical totals remain diagnostic only.
- `runs.jsonl` now records `verification_mode` so first-time onboarding attempts are distinguishable from confirmation attempts in the same artifact shape.
- A previously passing city may also confirm as `pass` through a stable delta no-op path when the crawler exits successfully, stages no newer rows, and the rollout registry records a prior fresh-evidence pass for that city.
- Stable delta no-op confirmation is not allowed for first-time onboarding cities; they still need fresh staged evidence.
- First-time onboarding still uses 3 runs, but the runner now restores city-scoped verification state between runs 2 and 3 so delta crawlers are compared against the same baseline instead of failing because run 1 advanced the anchor.
- Latest evidence runs:
  - `city_wave1_hayward_sanmateo_20260314_211707`
    - Hayward: `crawler_empty` in all 3 runs under the old confirmation policy; this run is now treated as the motivating regression for the new stable delta no-op path
  - `city_wave1_hayward_sanmateo_20260313_210210`
    - Hayward: last fresh-evidence passing baseline and the audit anchor for stable delta no-op eligibility
  - `city_wave1_san_mateo_20260314_004358`
    - San Mateo: onboarding run completed `success` for crawl, pipeline, segmentation, and search smoke
    - Gate result: `pass`; rollout registry now marks `enabled=yes`
    - The evaluator now grades extraction and segmentation against the run's touched San Mateo catalog set, while still reporting full historical totals as diagnostic backlog context

Current rollout interpretation:
- San Mateo remains `enabled=yes` on the strength of its latest fresh-evidence passing run.
- Hayward is now back to `enabled=yes` after proving the stable delta no-op confirmation path in a fresh paired wave-1 run.
- Sunnyvale is now promoted in `city_metadata/city_rollout_registry.csv` after the passing first-time rerun `city_wave1_sunnyvale_20260315_113626`.

Latest wave-1 confirmation:
- `city_wave1_hayward_sanmateo_20260314_213301`
  - Hayward: `crawler_stable_noop` in all 3 runs, downstream work correctly skipped, evaluator result `pass` with reason `stable_delta_noop:city_wave1_hayward_sanmateo_20260313_210210`
  - San Mateo: all 3 runs `success`, evaluator result `pass` with reason `fresh_evidence`
  - Result: both wave-1 cities currently verify as passing

Pending-city rewind notes:
- Sunnyvale contamination anchor:
  - operator rewind baseline: `2026-03-15T02:08:17Z`
  - source: earliest contaminated Sunnyvale `event.scraped_datetime` currently in the DB
  - note: the original run directory `city_wave1_sunnyvale_20260314_220801` exists, but its `runs.jsonl` is empty because the run failed before artifact write
- San Leandro contamination anchor:
  - operator rewind baseline: `2026-03-15T02:14:18Z`
  - source: `city_wave1_san_leandro_20260314_221300` run-1 `started_at_utc`
- Rewind recovery applied on `2026-03-15`:
  - Sunnyvale: dry-run and apply deleted `20` events, `20` documents, and `20` unreferenced catalogs; DB anchor is now clean again
  - San Leandro: dry-run and apply deleted `95` events, `23` documents, and `23` unreferenced catalogs; DB anchor is now clean again
- Post-rewind rerun status:
  - Sunnyvale rerun `city_wave1_sunnyvale_20260315_090331` proved the new first-time reset loop into run 2, but the run was interrupted after a pre-existing `scripts/segment_city_corpus.py --city sunnyvale` stall prevented a clean artifact write
  - Sunnyvale rerun `city_wave1_sunnyvale_20260315_092108` completed end to end after city segmentation was updated to bound per-catalog work and mark timeouts as explicit catalog failures instead of hanging the city
    - run 1: `success` for crawl, pipeline, segmentation, and search smoke
    - segmentation touched `10` agenda catalogs and terminated with `8` complete, `0` empty, `0` failed, `2` timed_out
    - evaluator result: `fail`
    - failed gates: `crawl_success_rate_gte_95pct`, `segmentation_complete_empty_rate_gte_95pct`, `segmentation_failed_rate_lt_5pct`, `searchability_smoke_pass`
    - interpretation: Sunnyvale is no longer blocked by a segmentation hang; it is now blocked by real first-time gate failures under the current verification policy
  - Sunnyvale rerun `city_wave1_sunnyvale_20260315_095618` proved the baseline-aware first-time reset fix
    - captured baseline artifact: `baseline_event_count=0`, `baseline_max_record_date=null`, `baseline_max_scraped_datetime=null`
    - run 1: `success`
    - run 2: `success` with `state_reset_applied=true`
    - run 3: `success` with `state_reset_applied=true`
    - evaluator result: `fail`
    - failed gates: `segmentation_complete_empty_rate_gte_95pct`, `segmentation_failed_rate_lt_5pct`
    - interpretation: the self-advanced delta-anchor bug is fixed; Sunnyvale now fails only on real segmentation quality thresholds
  - Pending shared fix after `city_wave1_sunnyvale_20260315_095618`:
    - root cause identified: `pipeline/agenda_resolver.py` eagerly invoked `LLM` agenda extraction even though the intended priority order is `Legistar -> HTML -> LLM`
  - Sunnyvale rerun `city_wave1_sunnyvale_20260315_104124` validated the lazy resolver-order fix
    - all 3 runs: `crawl_success_rate=1.000`, `extraction_non_empty_rate=1.000`
    - evaluator result: `fail`
    - failed gates: `segmentation_complete_empty_rate_gte_95pct`, `segmentation_failed_rate_lt_5pct`
    - live catalog outcomes still end at `8` complete / `2` timed_out
    - the remaining timeout pair is still the same two agenda dates:
      - `2026-03-09` Planning Commission
      - `2026-03-10` City Council
    - interpretation: lazy source ordering reduced unnecessary LLM work but did not remove the remaining slow-path timeout class, so the next blocker is now the residual LLM fallback latency on those two Sunnyvale catalogs
  - Sunnyvale rerun `city_wave1_sunnyvale_20260315_113626` validated the Legistar acceptance root-cause fix
    - all 3 runs: `success`
    - segmentation touched `10` agenda catalogs and terminated with `10` complete, `0` empty, `0` failed, `0` timed_out
    - evaluator result: `pass`
    - gate reason: `fresh_evidence`
    - former timeout pair now resolve deterministically as `complete`:
      - `2026-03-09` Planning Commission: `agenda_segmentation_item_count=25`
      - `2026-03-10` City Council: `agenda_segmentation_item_count=40`
    - interpretation: filtering procedural Legistar wrapper rows before quality acceptance keeps these agendas on the deterministic source path and clears the residual Sunnyvale timeout class without changing evaluator thresholds
  - San Leandro runtime follow-up on `2026-03-15`:
    - attempted rerun `city_wave1_san_leandro_20260315_125245` validated two operator-facing runtime changes:
      - crawler launch now uses an explicit prebuilt-image check instead of relying on an implicit rebuild during the run
      - onboarding pipeline now uses the `onboarding_fast` profile, which skips non-gating enrichment steps after extraction
    - the live trace also sharpened the shared Legistar finding:
      - San Leandro's tenant-specific `400` is raised during the Legistar `events` lookup itself, not only during `EventItems`
      - result: the first Legistar capability-miss cache landed, but it was initially too narrow for San Leandro's actual failure boundary
    - `pipeline/agenda_legistar.py` is now broadened so the same tenant-specific `400` is memoized at both the `events` lookup and `EventItems` lookup stages
    - lightweight live probe after the patch:
      - first call for `sanleandro` on `2026-03-16`: `item_count=0`, cache learned as `{'sanleandro': False}`
      - second call for `sanleandro` on `2026-03-17`: `item_count=0`, returned immediately from cache without repeating the failed network lookup
    - status: San Leandro still needs one fresh full rerun after the broadened capability cache patch before rollout promotion can be considered

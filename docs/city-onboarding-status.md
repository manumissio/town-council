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
| sunnyvale | existing | yes | no | pending | - |
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
  - San Leandro has been rewound successfully but not yet rerun after the cleanup window

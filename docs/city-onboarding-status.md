# City Onboarding Status

Last updated: 2026-03-06

This sheet tracks rollout readiness and quality gates per city.

| city_slug | provider | spider_exists | enabled | quality_gate | last_verified |
|---|---|---:|---:|---|---|
| berkeley | native | yes | yes | pass | 2026-02-17 |
| cupertino | legistar | yes | yes | pass | 2026-02-17 |
| fremont | existing | yes | no | pending | - |
| hayward | existing | yes | no | fail | 2026-03-06 |
| san_mateo | existing | yes | no | pending (insufficient_data) | 2026-03-06 |
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
- Keep `enabled=no` until gate artifacts show pass (`city_gate_eval.json`/`city_gate_eval.md`).
- Latest evidence run: `city_wave1_hayward_sanmateo_20260305_224127`
  - Hayward: `fail` (segmentation complete/empty gate)
  - San Mateo: `insufficient_data` (no city corpus yet)

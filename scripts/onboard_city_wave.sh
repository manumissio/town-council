#!/usr/bin/env bash
set -euo pipefail

# Why this script exists: city onboarding is intentionally wave-based so a single
# failing city does not block the whole rollout and can be paused independently.

WAVE="${1:-wave1}"
DRY_RUN="${DRY_RUN:-1}"

wave1=(
  fremont
  hayward
  san_mateo
  sunnyvale
  san_leandro
  mtn_view
  moraga
  belmont
)

wave2=(
  orinda
  brisbane
  danville
  los_gatos
  los_altos
  palo_alto
  san_bruno
  east_palo_alto
  santa_clara
)

if [[ "$WAVE" != "wave1" && "$WAVE" != "wave2" ]]; then
  echo "usage: $0 [wave1|wave2]"
  exit 2
fi

if [[ "$WAVE" == "wave1" ]]; then
  cities=("${wave1[@]}")
else
  cities=("${wave2[@]}")
fi

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] $*"
  else
    eval "$*"
  fi
}

for city in "${cities[@]}"; do
  echo "=== onboarding city: $city ($WAVE) ==="

  run_cmd "docker compose run --rm crawler scrapy crawl $city"
  run_cmd "docker compose run --rm pipeline python run_pipeline.py"
  run_cmd "curl -fsS \"http://localhost:8000/search?q=zoning&city=$city\" > /dev/null"

  echo "gate checklist for $city"
  echo "- crawl success >=95% over 3 runs"
  echo "- non-empty extraction >=90%"
  echo "- segmentation complete/empty >=95% (failed <5%)"
  echo "- searchable in API and Meilisearch facets"
  echo ""
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Completed dry-run wave plan: $WAVE"
else
  echo "Completed wave execution: $WAVE"
fi

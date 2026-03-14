#!/usr/bin/env bash
set -euo pipefail

# Why this script exists: city onboarding is intentionally wave-based so a single
# failing city does not block the whole rollout and can be paused independently.

DRY_RUN="${DRY_RUN:-1}"
RUNS=3
RUN_ID=""
OUTPUT_DIR="experiments/results/city_onboarding"
WAVE="${1:-wave1}"
shift || true

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

usage() {
  cat <<EOF
usage: $0 [wave1|wave2] [--cities city1,city2] [--runs N] [--run-id ID] [--output-dir PATH]
EOF
}

if [[ "$WAVE" != "wave1" && "$WAVE" != "wave2" ]]; then
  usage
  exit 2
fi

SELECTED_CITIES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cities)
      SELECTED_CITIES="${2:-}"
      shift 2
      ;;
    --runs)
      RUNS="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

if ! [[ "$RUNS" =~ ^[0-9]+$ ]] || [[ "$RUNS" -lt 1 ]]; then
  echo "--runs must be a positive integer"
  exit 2
fi

if [[ "$WAVE" == "wave1" ]]; then
  wave_cities=("${wave1[@]}")
else
  wave_cities=("${wave2[@]}")
fi

city_allowed() {
  local city="$1"
  local allowed
  for allowed in "${wave_cities[@]}"; do
    if [[ "$allowed" == "$city" ]]; then
      return 0
    fi
  done
  return 1
}

cities=()
if [[ -n "$SELECTED_CITIES" ]]; then
  IFS=',' read -r -a requested <<< "$SELECTED_CITIES"
  for city in "${requested[@]}"; do
    city="${city// /}"
    if [[ -z "$city" ]]; then
      continue
    fi
    if ! [[ "$city" =~ ^[a-z0-9_]+$ ]]; then
      echo "Invalid city slug: $city"
      exit 2
    fi
    if ! city_allowed "$city"; then
      echo "City '$city' is not in $WAVE"
      exit 2
    fi
    cities+=("$city")
  done
else
  cities=("${wave_cities[@]}")
fi

if [[ ${#cities[@]} -eq 0 ]]; then
  echo "No cities selected"
  exit 2
fi

if [[ -z "$RUN_ID" ]]; then
  RUN_ID="city_onboarding_$(date +%Y%m%d_%H%M%S)"
fi

RUN_DIR="${OUTPUT_DIR%/}/${RUN_ID}"
RESULTS_JSONL="${RUN_DIR}/runs.jsonl"

mkdir -p "$RUN_DIR"
: > "$RESULTS_JSONL"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "python interpreter not found (set PYTHON_BIN)"
    exit 127
  fi
fi

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] $*"
    return 0
  fi
  "$@"
}

check_crawl_evidence() {
  local city="$1"
  local started_at="$2"
  local ended_at="$3"

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] docker compose run --rm -w /app pipeline python scripts/check_city_crawl_evidence.py --city $city --start-at $started_at --end-at $ended_at"
    return 0
  fi

  docker compose run --rm -w /app pipeline python scripts/check_city_crawl_evidence.py --city "$city" --start-at "$started_at" --end-at "$ended_at"
}

write_result() {
  local city="$1"
  local run_index="$2"
  local started_at="$3"
  local finished_at="$4"
  local crawler_status="$5"
  local pipeline_status="$6"
  local segmentation_status="$7"
  local search_status="$8"
  local error_message="$9"
  local overall_status

  if [[ "$crawler_status" == "success" && "$pipeline_status" == "success" && "$segmentation_status" == "success" && "$search_status" == "success" ]]; then
    overall_status="success"
  else
    overall_status="failed"
  fi

  "$PYTHON_BIN" - "$RESULTS_JSONL" "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$overall_status" "$error_message" "$WAVE" "$RUN_ID" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
row = {
    "city": sys.argv[2],
    "run_index": int(sys.argv[3]),
    "started_at_utc": sys.argv[4],
    "finished_at_utc": sys.argv[5],
    "crawler_status": sys.argv[6],
    "pipeline_status": sys.argv[7],
    "segmentation_status": sys.argv[8],
    "search_status": sys.argv[9],
    "overall_status": sys.argv[10],
    "error": sys.argv[11] or None,
    "wave": sys.argv[12],
    "run_id": sys.argv[13],
}
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
PY
}

for city in "${cities[@]}"; do
  echo "=== onboarding city: $city ($WAVE) ==="
  for ((run_index=1; run_index<=RUNS; run_index++)); do
    started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    crawler_status="failed"
    pipeline_status="failed"
    segmentation_status="failed"
    search_status="failed"
    error_message=""

    if run_cmd docker compose run --rm crawler scrapy crawl "$city"; then
      crawl_finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      set +e
      crawl_evidence_json="$(check_crawl_evidence "$city" "$started_at" "$crawl_finished_at")"
      crawl_evidence_status=$?
      set -e
      echo "$crawl_evidence_json"
      if [[ "$crawl_evidence_status" -eq 0 ]]; then
        crawler_status="success"
        # Onboarding gates need city-specific stability signals. Keep derived state
        # intact between attempts to avoid full-dataset reprocessing on each run.
        if run_cmd docker compose run --rm -e STARTUP_PURGE_DERIVED=false pipeline python run_pipeline.py; then
          pipeline_status="success"
          # Onboarding quality gates are only meaningful after segmentation has been
          # attempted for the city's agenda corpus.
          if run_cmd docker compose run --rm -w /app -e STARTUP_PURGE_DERIVED=false pipeline python scripts/segment_city_corpus.py --city "$city"; then
            segmentation_status="success"
            if run_cmd curl -fsS "http://localhost:8000/search?q=zoning&city=$city" >/dev/null; then
              search_status="success"
            else
              search_status="failed"
              error_message="search_smoke_failed"
            fi
          else
            segmentation_status="failed"
            error_message="segmentation_failed"
          fi
        else
          pipeline_status="failed"
          error_message="pipeline_failed"
        fi
      else
        crawler_status="failed"
        error_message="crawler_empty"
      fi
    else
      crawler_status="failed"
      error_message="crawler_failed"
    fi

    finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message"
  done

  echo "gate checklist for $city"
  echo "- crawl success >=95% over 3 runs"
  echo "- non-empty extraction >=90%"
  echo "- segmentation complete/empty >=95% (failed <5%)"
  echo "- searchable in API and Meilisearch facets"
  echo ""
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Completed dry-run wave plan: $WAVE ($RUN_ID)"
else
  echo "Completed wave execution: $WAVE ($RUN_ID)"
fi

echo "wrote run artifacts: $RUN_DIR"

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

usage() {
  cat <<EOF
usage: $0 [wave1|wave2] [--cities city1,city2] [--runs N] [--run-id ID] [--output-dir PATH]
EOF
}

if [[ "$WAVE" != "wave1" && "$WAVE" != "wave2" ]]; then
  usage
  exit 2
fi

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

ROLLOUT_REGISTRY_PATH="city_metadata/city_rollout_registry.csv"

wave_cities_text="$("$PYTHON_BIN" scripts/rollout_registry.py --wave "$WAVE")" || {
  echo "Failed to load rollout registry from $ROLLOUT_REGISTRY_PATH"
  exit 2
}
mapfile -t wave_cities <<< "$wave_cities_text"

if [[ ${#wave_cities[@]} -eq 0 ]]; then
  echo "No cities configured for $WAVE in $ROLLOUT_REGISTRY_PATH"
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
BASELINE_DIR="${RUN_DIR}/baselines"
PREFLIGHT_DIR="${RUN_DIR}/preflight"

mkdir -p "$RUN_DIR"
mkdir -p "$BASELINE_DIR"
mkdir -p "$PREFLIGHT_DIR"
: > "$RESULTS_JSONL"

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] $*"
    return 0
  fi
  "$@"
}

ensure_crawler_image_present() {
  local crawler_image
  crawler_image="$(docker compose config --images | grep 'crawler$' | head -n 1 || true)"
  if [[ -z "$crawler_image" ]]; then
    echo "unable to resolve crawler image name from docker compose config --images"
    return 2
  fi
  if ! docker image inspect "$crawler_image" >/dev/null 2>&1; then
    echo "crawler image '$crawler_image' is missing; build it explicitly with: docker compose build crawler"
    return 2
  fi
  return 0
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

reset_city_verification_state() {
  local city="$1"
  local since="$2"
  local baseline_record_date="${3:-}"

  if [[ "$DRY_RUN" == "1" ]]; then
    local baseline_json='null'
    if [[ -n "$baseline_record_date" ]]; then
      baseline_json="\"$baseline_record_date\""
      echo "[dry-run] docker compose run --rm -w /app pipeline python scripts/reset_city_verification_state.py --city $city --since $since --baseline-record-date $baseline_record_date" >&2
    else
      echo "[dry-run] docker compose run --rm -w /app pipeline python scripts/reset_city_verification_state.py --city $city --since $since" >&2
    fi
    printf '{"city":"%s","since":"%s","baseline_record_date":%s,"deleted_event_count":0,"deleted_document_count":0,"deleted_catalog_count":0,"catalog_reference_count":0,"deleted_data_issue_count":0,"remaining_event_count":0,"remaining_max_record_date":null,"remaining_max_scraped_datetime":null}\n' "$city" "$since" "$baseline_json"
    return 0
  fi

  local args=(docker compose run --rm -w /app pipeline python scripts/reset_city_verification_state.py --city "$city" --since "$since")
  if [[ -n "$baseline_record_date" ]]; then
    args+=(--baseline-record-date "$baseline_record_date")
  fi
  "${args[@]}"
}

flush_city_pipeline_state() {
  local city="$1"
  local apply_mode="${2:-dry-run}"

  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ "$apply_mode" == "apply" ]]; then
      echo "[dry-run] docker compose run --rm -w /app pipeline python scripts/flush_city_pipeline_state.py --city $city --apply" >&2
    else
      echo "[dry-run] docker compose run --rm -w /app pipeline python scripts/flush_city_pipeline_state.py --city $city" >&2
    fi
    printf '{"city":"%s","dry_run":true,"deleted_event_stage_count":0,"deleted_url_stage_count":0,"deleted_url_stage_hist_count":0,"deleted_event_count":0,"deleted_document_count":0,"deleted_catalog_count":0,"catalog_reference_count":0,"deleted_data_issue_count":0,"remaining_event_stage_count":0,"remaining_url_stage_count":0,"remaining_url_stage_hist_count":0,"remaining_event_count":0,"remaining_document_count":0,"remaining_catalog_count":0}\n' "$city"
    return 0
  fi

  local args=(docker compose run --rm -w /app pipeline python scripts/flush_city_pipeline_state.py --city "$city")
  if [[ "$apply_mode" == "apply" ]]; then
    args+=(--apply)
  fi
  "${args[@]}"
}

registry_field() {
  local city="$1"
  local field="$2"
  "$PYTHON_BIN" scripts/rollout_registry.py --city "$city" --field "$field"
}

capture_city_baseline() {
  local city="$1"
  local baseline_path="$2"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '{"city":"%s","baseline_event_count":0,"baseline_max_record_date":null,"baseline_max_scraped_datetime":null}\n' "$city" > "$baseline_path"
    echo "[dry-run] captured baseline for $city at $baseline_path"
    return 0
  fi

  docker compose run --rm -w /app pipeline python scripts/reset_city_verification_state.py --city "$city" --print-baseline > "$baseline_path"
}

baseline_json_field() {
  local baseline_path="$1"
  local field="$2"
  "$PYTHON_BIN" - "$baseline_path" "$field" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload.get(sys.argv[2])
print("" if value is None else value)
PY
}

reset_matches_baseline() {
  local baseline_path="$1"
  local reset_json="$2"
  "$PYTHON_BIN" - "$baseline_path" "$reset_json" <<'PY'
import json
import sys
from pathlib import Path

baseline = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
reset = json.loads(sys.argv[2])

if baseline.get("baseline_event_count") != reset.get("remaining_event_count"):
    raise SystemExit(1)
if baseline.get("baseline_max_record_date") != reset.get("remaining_max_record_date"):
    raise SystemExit(1)
if baseline.get("baseline_max_scraped_datetime") != reset.get("remaining_max_scraped_datetime"):
    raise SystemExit(1)
PY
}

flush_output_has_mutations() {
  local flush_json="$1"
  "$PYTHON_BIN" - "$flush_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
keys = [
    "deleted_event_stage_count",
    "deleted_url_stage_count",
    "deleted_url_stage_hist_count",
    "deleted_event_count",
    "deleted_document_count",
    "deleted_catalog_count",
    "deleted_data_issue_count",
]
raise SystemExit(0 if any(int(payload.get(key, 0) or 0) > 0 for key in keys) else 1)
PY
}

augment_flush_payload() {
  local flush_json="$1"
  local mode="$2"
  local auto_flush_applied="$3"
  "$PYTHON_BIN" - "$flush_json" "$mode" "$auto_flush_applied" <<'PY'
import json
import sys
from datetime import datetime, timezone

payload = json.loads(sys.argv[1])
payload["mode"] = sys.argv[2]
payload["auto_flush_applied"] = sys.argv[3] == "yes"
payload["timestamp_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print(json.dumps(payload, sort_keys=True))
PY
}

write_preflight_artifact() {
  local artifact_path="$1"
  local flush_json="$2"
  printf '%s\n' "$flush_json" > "$artifact_path"
  echo "wrote onboarding preflight artifact: $artifact_path"
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
  local verification_mode="${10}"
  local state_reset_applied="${11}"
  local overall_status

  if [[ "$crawler_status" == "success" && "$pipeline_status" == "success" && "$segmentation_status" == "success" && "$search_status" == "success" ]]; then
    overall_status="success"
  elif [[ "$crawler_status" == "crawler_stable_noop" && "$pipeline_status" == "skipped" && "$segmentation_status" == "skipped" && "$search_status" == "skipped" ]]; then
    overall_status="success"
  else
    overall_status="failed"
  fi

  "$PYTHON_BIN" - "$RESULTS_JSONL" "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$overall_status" "$error_message" "$verification_mode" "$state_reset_applied" "$WAVE" "$RUN_ID" <<'PY'
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
    "verification_mode": sys.argv[12],
    "state_reset_applied": sys.argv[13] == "yes",
    "wave": sys.argv[14],
    "run_id": sys.argv[15],
}
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
PY
}

for city in "${cities[@]}"; do
  echo "=== onboarding city: $city ($WAVE) ==="
  echo "using rollout registry: $ROLLOUT_REGISTRY_PATH"
  city_enabled="$(registry_field "$city" enabled)"
  city_quality_gate="$(registry_field "$city" quality_gate)"
  stable_noop_eligible="$(registry_field "$city" stable_noop_eligible)"
  last_fresh_pass_run_id="$(registry_field "$city" last_fresh_pass_run_id)"
  if [[ "$city_quality_gate" == "pass" ]]; then
    verification_mode="confirmation"
  else
    verification_mode="first_time_onboarding"
  fi
  echo "verification mode for $city: $verification_mode"
  campaign_started_at=""
  baseline_path="${BASELINE_DIR}/${city}.json"
  preflight_artifact_path="${PREFLIGHT_DIR}/${city}_flush.json"
  prior_run_had_fresh_evidence="no"
  for ((run_index=1; run_index<=RUNS; run_index++)); do
    started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    crawler_status="failed"
    pipeline_status="failed"
    segmentation_status="failed"
    search_status="failed"
    error_message=""
    state_reset_applied="no"
    if [[ -z "$campaign_started_at" ]]; then
      campaign_started_at="$started_at"
      if [[ "$verification_mode" == "first_time_onboarding" ]]; then
        if [[ "$city_enabled" == "no" ]]; then
          # First-time onboarding must start from a clean city footprint. Stale
          # stage rows can silently repopulate live tables and poison the baseline.
          if flush_output="$(flush_city_pipeline_state "$city")"; then
            if flush_output_has_mutations "$flush_output"; then
              if flush_apply_output="$(flush_city_pipeline_state "$city" apply)"; then
                write_preflight_artifact "$preflight_artifact_path" "$(augment_flush_payload "$flush_apply_output" "apply" "yes")"
              else
                finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
                error_message="city_preflight_flush_failed"
                write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
                break
              fi
            else
              preflight_mode="clean_noop"
              if [[ "$DRY_RUN" == "1" ]]; then
                preflight_mode="dry_run_only"
              fi
              write_preflight_artifact "$preflight_artifact_path" "$(augment_flush_payload "$flush_output" "$preflight_mode" "no")"
            fi
          else
            finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
            error_message="city_preflight_flush_failed"
            write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
            break
          fi
        fi
        if capture_city_baseline "$city" "$baseline_path"; then
          echo "captured first-time baseline for $city at $baseline_path"
          cat "$baseline_path"
        else
          finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
          error_message="baseline_capture_failed"
          write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
          break
        fi
      fi
    fi

    if [[ "$verification_mode" == "first_time_onboarding" && "$run_index" -gt 1 && "$prior_run_had_fresh_evidence" == "yes" ]]; then
      echo "restoring first-time verification state for $city before run $run_index via baseline $campaign_started_at"
      baseline_record_date="$(baseline_json_field "$baseline_path" baseline_max_record_date)"
      if reset_output="$(reset_city_verification_state "$city" "$campaign_started_at" "$baseline_record_date")"; then
        if reset_matches_baseline "$baseline_path" "$reset_output"; then
          state_reset_applied="yes"
        else
          finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
          error_message="verification_state_reset_failed"
          echo "$reset_output"
          write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
          break
        fi
        echo "$reset_output"
      else
        finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        error_message="verification_state_reset_failed"
        write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
        break
      fi
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
      echo "launching crawler for $city with explicit prebuilt-image check"
      echo "[dry-run] docker compose config --images | grep 'crawler$' | head -n 1"
      echo "[dry-run] docker image inspect <crawler-image>"
    elif ensure_crawler_image_present; then
      echo "launching crawler for $city with explicit prebuilt-image check"
    else
      crawler_status="failed"
      error_message="crawler_image_missing"
      prior_run_had_fresh_evidence="no"
      finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
      break
    fi

    if run_cmd docker compose run --rm crawler scrapy crawl "$city"; then
      crawl_finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      set +e
      crawl_evidence_json="$(check_crawl_evidence "$city" "$started_at" "$crawl_finished_at")"
      crawl_evidence_status=$?
      set -e
      echo "$crawl_evidence_json"
      if [[ "$crawl_evidence_status" -eq 0 ]]; then
        crawler_status="success"
        prior_run_had_fresh_evidence="yes"
        # First-time verification restores only the city's crawl anchor between
        # attempts, so downstream processing still runs against fresh staged input.
        if run_cmd docker compose run --rm \
          -e STARTUP_PURGE_DERIVED=false \
          -e PIPELINE_ONBOARDING_CITY="$city" \
          -e PIPELINE_ONBOARDING_STARTED_AT_UTC="$started_at" \
          -e PIPELINE_RUNTIME_PROFILE=onboarding_fast \
          -e PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE=5 \
          -e PIPELINE_ONBOARDING_MAX_WORKERS=1 \
          -e TIKA_OCR_FALLBACK_ENABLED=false \
          pipeline python run_pipeline.py; then
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
      elif [[ "$crawl_evidence_status" -eq 3 && "$stable_noop_eligible" == "yes" ]]; then
        # A previously passing city may have nothing newer than its delta anchor.
        # Keep this distinct from a true empty onboarding city so rollout confirmation
        # can remain strict for new cities without penalizing healthy no-op deltas.
        crawler_status="crawler_stable_noop"
        pipeline_status="skipped"
        segmentation_status="skipped"
        search_status="skipped"
        error_message="stable_delta_noop:${last_fresh_pass_run_id}"
        echo "stable delta no-op confirmation for $city via $last_fresh_pass_run_id"
      else
        crawler_status="failed"
        error_message="crawler_empty"
        if [[ "$verification_mode" == "first_time_onboarding" ]]; then
          prior_run_had_fresh_evidence="no"
        fi
      fi
    else
      crawler_status="failed"
      error_message="crawler_failed"
      prior_run_had_fresh_evidence="no"
    fi

    finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    write_result "$city" "$run_index" "$started_at" "$finished_at" "$crawler_status" "$pipeline_status" "$segmentation_status" "$search_status" "$error_message" "$verification_mode" "$state_reset_applied"
    if [[ "$verification_mode" == "first_time_onboarding" && "$run_index" -eq 1 && "$error_message" == "crawler_empty" ]]; then
      echo "stopping first-time verification for $city after run 1: no fresh crawl evidence"
      break
    fi
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

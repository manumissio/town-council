#!/usr/bin/env bash
set -euo pipefail

ARM=""
CATALOG_FILE=""
RUN_ID=""
API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-dev_secret_key_change_me}"
WAIT_SECONDS="${WAIT_SECONDS:-2}"
ARM_MODEL="${LOCAL_AI_HTTP_MODEL:-}"

usage() {
  echo "usage: $0 --arm <A|B> --catalog-file <path> --run-id <id> [--api-url <url>] [--api-key <key>] [--wait-seconds <n>] [--arm-model <model>]"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arm) ARM="$2"; shift 2 ;;
    --catalog-file) CATALOG_FILE="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --api-url) API_URL="$2"; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    --wait-seconds) WAIT_SECONDS="$2"; shift 2 ;;
    --arm-model) ARM_MODEL="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$ARM" || -z "$CATALOG_FILE" || -z "$RUN_ID" ]] && usage
[[ "$ARM" != "A" && "$ARM" != "B" ]] && usage
[[ ! -f "$CATALOG_FILE" ]] && { echo "catalog file not found: $CATALOG_FILE"; exit 2; }

RESULT_DIR="experiments/results/${RUN_ID}"
mkdir -p "$RESULT_DIR"
TASKS_JSONL="$RESULT_DIR/tasks.jsonl"
: > "$TASKS_JSONL"

# Parse CID manifest (one numeric ID per line; '#' comments allowed).
mapfile -t CIDS < <(awk '{gsub(/#.*/,"",$0); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0); if ($0 ~ /^[0-9]+$/) print $0}' "$CATALOG_FILE")
if [[ ${#CIDS[@]} -eq 0 ]]; then
  echo "no CIDs parsed from $CATALOG_FILE"
  exit 2
fi

# Why this gate exists: decision-grade runs require broad, fixed coverage; smoke runs can be smaller.
if [[ "${AB_REQUIRE_60:-0}" == "1" && ${#CIDS[@]} -lt 60 ]]; then
  echo "AB_REQUIRE_60=1 but only ${#CIDS[@]} CIDs provided"
  exit 2
fi

until curl -fsS "$API_URL/health" >/dev/null; do sleep 1; done

if [[ -n "$ARM_MODEL" ]]; then
  export LOCAL_AI_HTTP_MODEL="$ARM_MODEL"
fi

echo "run_id=$RUN_ID arm=$ARM model=${LOCAL_AI_HTTP_MODEL:-unknown} cids=${#CIDS[@]}" | tee "$RESULT_DIR/run_meta.txt"

run_endpoint() {
  local cid="$1"
  local phase="$2"
  local ep="$3"

  local t_start t_end tid status payload
  t_start=$(python3 - <<'PY'
import time
print(f"{time.time():.6f}")
PY
)

  tid=$(curl -fsS -X POST "$API_URL/$ep" -H "X-API-Key: $API_KEY" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("task_id",""))')
  if [[ -z "$tid" ]]; then
    payload=$(printf '{"run_id":"%s","arm":"%s","catalog_id":%s,"phase":"%s","status":"failed","task_failed":true,"error":"missing_task_id"}' "$RUN_ID" "$ARM" "$cid" "$phase")
    echo "$payload" >> "$TASKS_JSONL"
    return 1
  fi

  while true; do
    status=$(curl -fsS "$API_URL/tasks/$tid" -H "X-API-Key: $API_KEY" | python3 -c 'import sys,json; print((json.load(sys.stdin).get("status") or "").lower())')
    if [[ "$status" == "complete" || "$status" == "completed" || "$status" == "failed" ]]; then
      break
    fi
    sleep "$WAIT_SECONDS"
  done

  t_end=$(python3 - <<'PY'
import time
print(f"{time.time():.6f}")
PY
)

  local duration
  duration=$(python3 - <<PY
start=float("$t_start")
end=float("$t_end")
print(f"{(end-start):.6f}")
PY
)

  local failed="false"
  [[ "$status" == "failed" ]] && failed="true"

  payload=$(printf '{"run_id":"%s","arm":"%s","catalog_id":%s,"phase":"%s","task_id":"%s","status":"%s","duration_s":%s,"task_failed":%s}' \
    "$RUN_ID" "$ARM" "$cid" "$phase" "$tid" "$status" "$duration" "$failed")
  echo "$payload" >> "$TASKS_JSONL"

  if [[ "$status" == "failed" ]]; then
    return 1
  fi
  return 0
}

failures=0
processed=0
for cid in "${CIDS[@]}"; do
  echo "=== cid=$cid ==="
  run_endpoint "$cid" "extract" "extract/$cid?force=true&ocr_fallback=false" || failures=$((failures + 1))
  run_endpoint "$cid" "segment" "segment/$cid?force=true" || failures=$((failures + 1))
  run_endpoint "$cid" "summarize" "summarize/$cid?force=true" || failures=$((failures + 1))

  processed=$((processed + 1))

  # Abort rule: failures >5% in first 15 CIDs.
  if [[ $processed -le 15 ]]; then
    max_allowed=$(python3 - <<PY
print(int((15 * 3) * 0.05))
PY
)
    if [[ "$failures" -gt "$max_allowed" ]]; then
      echo "abort: failures=$failures exceeded first-15 threshold=$max_allowed" | tee -a "$RESULT_DIR/run_meta.txt"
      exit 1
    fi
  fi

done

echo "completed run_id=$RUN_ID arm=$ARM failures=$failures processed_cids=$processed" | tee -a "$RESULT_DIR/run_meta.txt"

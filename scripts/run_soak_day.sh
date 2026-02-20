#!/usr/bin/env bash
set -euo pipefail

RUN_ID=""
CATALOG_FILE=""
OUTPUT_DIR="experiments/results/soak"
API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-dev_secret_key_change_me}"
WAIT_SECONDS="${WAIT_SECONDS:-2}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-60}"
TASK_MAX_WAIT_SECONDS="${TASK_MAX_WAIT_SECONDS:-900}"

usage() {
  echo "usage: $0 --run-id <id> --catalog-file <path> [--output-dir <path>] [--api-url <url>] [--api-key <key>] [--task-max-wait-seconds <n>]"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID="$2"; shift 2 ;;
    --catalog-file) CATALOG_FILE="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --api-url) API_URL="$2"; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    --wait-seconds) WAIT_SECONDS="$2"; shift 2 ;;
    --health-timeout-seconds) HEALTH_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --task-max-wait-seconds) TASK_MAX_WAIT_SECONDS="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$RUN_ID" || -z "$CATALOG_FILE" ]] && usage
[[ ! -f "$CATALOG_FILE" ]] && { echo "catalog file not found: $CATALOG_FILE"; exit 2; }

mkdir -p "$OUTPUT_DIR"
RUN_DIR="$OUTPUT_DIR/$RUN_ID"
mkdir -p "$RUN_DIR"
TASKS_JSONL="$RUN_DIR/tasks.jsonl"
DAY_SUMMARY_JSON="$RUN_DIR/day_summary.json"
: > "$TASKS_JSONL"

CIDS=()
while IFS= read -r cid; do
  CIDS+=("$cid")
done < <(awk '{gsub(/#.*/,"",$0); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0); if ($0 ~ /^[0-9]+$/) print $0}' "$CATALOG_FILE")
if [[ ${#CIDS[@]} -eq 0 ]]; then
  echo "no CIDs parsed from $CATALOG_FILE"
  exit 2
fi

health_ok() {
  local elapsed=0
  while [[ "$elapsed" -lt "$HEALTH_TIMEOUT_SECONDS" ]]; do
    if curl -fsS "$API_URL/health" >/dev/null; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

preflight_status="healthy"
if ! health_ok; then
  preflight_status="recovering"
  # Prefer a fast, no-build recovery path for scheduled soak runs.
  # Full dev_up rebuilds are slower and increase false stack_offline failures.
  if ! docker compose up -d inference worker api pipeline frontend; then
    if [[ -f "scripts/dev_up.sh" ]]; then
      bash scripts/dev_up.sh || true
    fi
  fi
  if ! health_ok; then
    preflight_status="stack_offline"
    python3 - <<'PY' "$RUN_ID" "$API_URL" "$preflight_status" "$DAY_SUMMARY_JSON"
import json
import sys
run_id, api_url, status, out = sys.argv[1:]
payload = {
    "run_id": run_id,
    "status": "failed",
    "failure_reason": status,
    "api_url": api_url,
    "preflight_status": status,
    "cids_total": 0,
    "phases_total": 0,
    "phases_failed": 0,
    "extract_failures": 0,
    "segment_failures": 0,
    "summarize_failures": 0,
    "gating_failures": 0,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
PY
    echo "stack offline after preflight recovery"
    exit 1
  fi
fi

run_endpoint() {
  local cid="$1"
  local phase="$2"
  local ep="$3"

  local t_start t_end tid status payload task_resp post_resp
  t_start=$(python3 - <<'PY'
import time
print(f"{time.time():.6f}")
PY
)

  post_resp="$(curl -sS -X POST "$API_URL/$ep" -H "X-API-Key: $API_KEY" || true)"
  tid="$(python3 - <<'PY' "$post_resp"
import json
import sys
raw = sys.argv[1]
try:
    obj = json.loads(raw) if raw else {}
except Exception:
    obj = {}
print(obj.get("task_id", "") if isinstance(obj, dict) else "")
PY
)"
  if [[ -z "$tid" ]]; then
    payload=$(printf '{"run_id":"%s","catalog_id":%s,"phase":"%s","status":"failed","task_failed":true,"error":"missing_task_id"}' "$RUN_ID" "$cid" "$phase")
    echo "$payload" >> "$TASKS_JSONL"
    return 1
  fi

  local waited_seconds=0
  while true; do
    task_resp="$(curl -sS "$API_URL/tasks/$tid" -H "X-API-Key: $API_KEY" || true)"
    status="$(python3 - <<'PY' "$task_resp"
import json
import sys
raw = sys.argv[1]
try:
    obj = json.loads(raw) if raw else {}
except Exception:
    obj = {}
print((obj.get("status") or "").lower() if isinstance(obj, dict) else "")
PY
)"
    if [[ "$status" == "complete" || "$status" == "completed" || "$status" == "failed" ]]; then
      break
    fi
    if [[ "$waited_seconds" -ge "$TASK_MAX_WAIT_SECONDS" ]]; then
      status="failed"
      task_resp='{"status":"failed","error":"task_poll_timeout"}'
      break
    fi
    sleep "$WAIT_SECONDS"
    waited_seconds=$((waited_seconds + WAIT_SECONDS))
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

  payload=$(python3 - <<'PY' "$RUN_ID" "$cid" "$phase" "$tid" "$status" "$duration" "$failed" "$task_resp"
import json
import sys

run_id, cid, phase, tid, status, duration, failed, task_resp = sys.argv[1:]
row = {
    "run_id": run_id,
    "catalog_id": int(cid),
    "phase": phase,
    "task_id": tid,
    "status": status,
    "duration_s": float(duration),
    "task_failed": failed.lower() == "true",
}
try:
    task_obj = json.loads(task_resp)
except Exception:
    task_obj = {}
result = task_obj.get("result") if isinstance(task_obj, dict) else None
if isinstance(result, dict):
    row["task_result"] = result
print(json.dumps(row, separators=(",", ":")))
PY
)
  echo "$payload" >> "$TASKS_JSONL"

  [[ "$status" == "failed" ]] && return 1
  return 0
}

extract_failures=0
segment_failures=0
summarize_failures=0
phases=0
for cid in "${CIDS[@]}"; do
  run_endpoint "$cid" "extract" "extract/$cid?force=true&ocr_fallback=false" || extract_failures=$((extract_failures + 1))
  phases=$((phases + 1))
  run_endpoint "$cid" "segment" "segment/$cid?force=true" || segment_failures=$((segment_failures + 1))
  phases=$((phases + 1))
  run_endpoint "$cid" "summarize" "summarize/$cid?force=true" || summarize_failures=$((summarize_failures + 1))
  phases=$((phases + 1))
done

gating_failures=$((segment_failures + summarize_failures))
all_phase_failures=$((extract_failures + gating_failures))

python3 - <<'PY' "$RUN_ID" "$API_URL" "$preflight_status" "$DAY_SUMMARY_JSON" "$TASKS_JSONL" "${#CIDS[@]}" "$phases" "$all_phase_failures" "$extract_failures" "$segment_failures" "$summarize_failures" "$gating_failures"
import json
import statistics
import sys
from pathlib import Path

(
    run_id,
    api_url,
    preflight_status,
    out_path,
    tasks_path,
    cids_total,
    phases_total,
    all_phase_failures,
    extract_failures,
    segment_failures,
    summarize_failures,
    gating_failures,
) = sys.argv[1:]
rows = []
for raw in Path(tasks_path).read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    rows.append(json.loads(raw))
phase_durations = [float(r.get("duration_s") or 0.0) for r in rows]
segment = [float(r.get("duration_s") or 0.0) for r in rows if r.get("phase") == "segment"]
summary = [float(r.get("duration_s") or 0.0) for r in rows if r.get("phase") == "summarize"]

def p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, int((0.95 * len(ordered)) + 0.999999) - 1)
    return float(ordered[idx])

payload = {
    "run_id": run_id,
    "status": "failed" if int(gating_failures) > 0 else "complete",
    "failure_reason": "gating_phase_failures" if int(gating_failures) > 0 else "",
    "api_url": api_url,
    "preflight_status": preflight_status,
    "cids_total": int(cids_total),
    "phases_total": int(phases_total),
    "phases_failed": int(all_phase_failures),
    "extract_failures": int(extract_failures),
    "segment_failures": int(segment_failures),
    "summarize_failures": int(summarize_failures),
    "gating_failures": int(gating_failures),
    "duration_total_s": float(sum(phase_durations)),
    "phase_duration_p95_s": p95(phase_durations),
    "segment_p95_s": p95(segment),
    "summary_p95_s": p95(summary),
    "segment_median_s": float(statistics.median(segment)) if segment else 0.0,
    "summary_median_s": float(statistics.median(summary)) if summary else 0.0,
}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
PY

if [[ "$extract_failures" -gt 0 ]]; then
  echo "run completed with non-gating extract_failures=$extract_failures"
fi
if [[ "$gating_failures" -gt 0 ]]; then
  echo "run completed with gating_failures=$gating_failures"
  exit 1
fi

echo "run completed successfully: $RUN_ID"

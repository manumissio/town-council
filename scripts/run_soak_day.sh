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
RUN_MANIFEST_JSON="$RUN_DIR/run_manifest.json"
: > "$TASKS_JSONL"
LAST_FAILURE_REASON=""
PREFLIGHT_RECOVERY_ATTEMPTED="false"
PREFLIGHT_RECOVERY_RESULT="not_needed"
PREFLIGHT_RECOVERY_LOG="$RUN_DIR/preflight_recovery.log"
PREFLIGHT_COMPOSE_PS_LOG="$RUN_DIR/preflight_compose_ps.log"
: > "$PREFLIGHT_RECOVERY_LOG"
: > "$PREFLIGHT_COMPOSE_PS_LOG"

CIDS=()
while IFS= read -r cid; do
  CIDS+=("$cid")
done < <(awk '{gsub(/#.*/,"",$0); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0); if ($0 ~ /^[0-9]+$/) print $0}' "$CATALOG_FILE")
if [[ ${#CIDS[@]} -eq 0 ]]; then
  echo "no CIDs parsed from $CATALOG_FILE"
  exit 2
fi

python3 - <<'PY' "$RUN_MANIFEST_JSON" "$RUN_ID" "$CATALOG_FILE" "${CIDS[@]}"
import json
import os
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
run_id = sys.argv[2]
catalog_file = sys.argv[3]
catalog_ids = [int(value) for value in sys.argv[4:] if str(value).strip()]

def _env_int(name: str, default: int | None = None) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

manifest = {
    "run_id": run_id,
    "catalog_file": catalog_file,
    "catalog_ids": catalog_ids,
    "catalog_count": len(catalog_ids),
    "profile": {
        "LOCAL_AI_BACKEND": (os.getenv("LOCAL_AI_BACKEND") or "").strip().lower() or "http",
        "LOCAL_AI_HTTP_PROFILE": (os.getenv("LOCAL_AI_HTTP_PROFILE") or "").strip().lower() or "conservative",
        "LOCAL_AI_HTTP_MODEL": (os.getenv("LOCAL_AI_HTTP_MODEL") or "").strip() or "gemma-3-270m-custom",
        "WORKER_CONCURRENCY": _env_int("WORKER_CONCURRENCY", 3),
        "WORKER_POOL": (os.getenv("WORKER_POOL") or "").strip().lower() or "prefork",
        "OLLAMA_NUM_PARALLEL": _env_int("OLLAMA_NUM_PARALLEL", 1),
    },
}
out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
PY

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
  PREFLIGHT_RECOVERY_ATTEMPTED="true"
  # Prefer a fast, no-build recovery path for scheduled soak runs.
  # Full dev_up rebuilds are slower and increase false stack_offline failures.
  if docker compose up -d inference worker api pipeline frontend >"$PREFLIGHT_RECOVERY_LOG" 2>&1; then
    PREFLIGHT_RECOVERY_RESULT="docker_compose_succeeded"
  else
    PREFLIGHT_RECOVERY_RESULT="docker_compose_failed"
    if [[ -f "scripts/dev_up.sh" ]]; then
      if bash scripts/dev_up.sh >>"$PREFLIGHT_RECOVERY_LOG" 2>&1; then
        PREFLIGHT_RECOVERY_RESULT="dev_up_succeeded"
      else
        PREFLIGHT_RECOVERY_RESULT="dev_up_failed"
      fi
    fi
  fi
  if ! health_ok; then
    preflight_status="stack_offline"
    docker compose ps >"$PREFLIGHT_COMPOSE_PS_LOG" 2>&1 || true
    python3 - <<'PY' "$RUN_ID" "$API_URL" "$preflight_status" "$DAY_SUMMARY_JSON" "$PREFLIGHT_RECOVERY_ATTEMPTED" "$PREFLIGHT_RECOVERY_RESULT"
import json
import sys
from pathlib import Path
run_id, api_url, status, out, recovery_attempted, recovery_result = sys.argv[1:]
run_dir = Path(out).parent


def _tail_text(path: Path, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


payload = {
    "run_id": run_id,
    "status": "failed",
    "failure_reason": status,
    "api_url": api_url,
    "preflight_status": status,
    "preflight_recovery_attempted": recovery_attempted.lower() == "true",
    "preflight_recovery_result": recovery_result,
    "preflight_recovery_output": _tail_text(run_dir / "preflight_recovery.log"),
    "preflight_compose_ps": _tail_text(run_dir / "preflight_compose_ps.log"),
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

python3 - <<'PY' "$RUN_MANIFEST_JSON"
import json
import re
import subprocess
import sys
import time
from pathlib import Path

manifest_path = Path(sys.argv[1])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
pattern = re.compile(r'^(?P<name>tc_provider_(?:requests|timeouts|retries)_total)(?:\{[^}]*\})?\s+(?P<value>-?[0-9]+(?:\.[0-9]+)?)$')
strategies = [
    (
        "worker_http",
        (
            "import urllib.request; "
            "print(urllib.request.urlopen('http://localhost:8001/metrics', timeout=10)"
            ".read().decode('utf-8', errors='replace'))"
        ),
    ),
    (
        "worker_registry",
        (
            "from prometheus_client import CollectorRegistry, generate_latest; "
            "from pipeline.metrics import RedisProviderMetricsCollector; "
            "registry = CollectorRegistry(); "
            "registry.register(RedisProviderMetricsCollector()); "
            "print(generate_latest(registry).decode('utf-8', errors='replace'))"
        ),
    ),
]
baseline = {
    "provider_requests_total": 0.0,
    "provider_timeouts_total": 0.0,
    "provider_retries_total": 0.0,
}
errors = []
try:
    saw_provider_series = False
    baseline_source = "worker_http_error"
    for strategy_name, script in strategies:
        for attempt in range(1, 3):
            try:
                raw = subprocess.check_output(
                    ["docker", "compose", "exec", "-T", "worker", "python", "-c", script],
                    text=True,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                )
                current = {
                    "provider_requests_total": 0.0,
                    "provider_timeouts_total": 0.0,
                    "provider_retries_total": 0.0,
                }
                current_has_provider_series = False
                for line in raw.splitlines():
                    match = pattern.match(line.strip())
                    if not match:
                        continue
                    current_has_provider_series = True
                    current[match.group("name")] = float(current.get(match.group("name")) or 0.0) + float(match.group("value"))
                if strategy_name == "worker_http" and not current_has_provider_series:
                    errors.append(f"{strategy_name}[attempt={attempt}] missing_provider_series")
                    if attempt < 2:
                        time.sleep(0.5)
                    continue
                baseline = current
                saw_provider_series = current_has_provider_series
                baseline_source = strategy_name if current_has_provider_series else "zero_baseline_no_provider_series"
                raise StopIteration
            except StopIteration:
                raise
            except Exception as exc:
                errors.append(f"{strategy_name}[attempt={attempt}] {exc}")
                if attempt < 2:
                    time.sleep(0.5)
    manifest["provider_counters_before_run"] = baseline
    manifest["provider_counters_before_run_available"] = True
    manifest["provider_counters_before_run_source"] = baseline_source
except StopIteration:
    manifest["provider_counters_before_run"] = baseline
    manifest["provider_counters_before_run_available"] = True
    manifest["provider_counters_before_run_source"] = baseline_source
except Exception as exc:
    manifest["provider_counters_before_run"] = baseline
    manifest["provider_counters_before_run_available"] = False
    manifest["provider_counters_before_run_source"] = "worker_http_error"
    manifest["provider_counters_before_run_error"] = str(exc)
else:
    if not saw_provider_series and baseline_source == "worker_http_error":
        manifest["provider_counters_before_run"] = baseline
        manifest["provider_counters_before_run_available"] = False
        manifest["provider_counters_before_run_source"] = "worker_http_error"
        manifest["provider_counters_before_run_error"] = "; ".join(errors) if errors else "worker baseline scrape failed"
    elif errors:
        manifest["provider_counters_before_run_error"] = "; ".join(errors)

manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
PY

run_endpoint() {
  local cid="$1"
  local phase="$2"
  local ep="$3"

  local t_start t_end tid status payload task_resp post_resp error_detail endpoint_status task_id_valid
  t_start=$(python3 - <<'PY'
import time
print(f"{time.time():.6f}")
PY
)

  post_resp="$(curl -sS -X POST "$API_URL/$ep" -H "X-API-Key: $API_KEY" || true)"
  tid="$(python3 scripts/parse_task_launch.py --raw "$post_resp" --field task_id)"
  task_id_valid="$(python3 scripts/parse_task_launch.py --raw "$post_resp" --field task_id_valid)"
  endpoint_status="$(python3 scripts/parse_task_launch.py --raw "$post_resp" --field status)"
  error_detail="$(python3 scripts/parse_task_launch.py --raw "$post_resp" --field detail)"
  if [[ "$task_id_valid" != "true" || -z "$tid" ]]; then
    if [[ "$endpoint_status" == "cached" || "$endpoint_status" == "stale" || "$endpoint_status" == "blocked_low_signal" ]]; then
      LAST_FAILURE_REASON="task_submission_failure"
      payload=$(printf '{"run_id":"%s","catalog_id":%s,"phase":"%s","status":"failed","task_failed":true,"error":"unexpected_non_processing_status:%s"}' "$RUN_ID" "$cid" "$phase" "$endpoint_status")
    elif [[ -n "$error_detail" ]]; then
      LAST_FAILURE_REASON="task_submission_failure"
      payload=$(python3 - <<'PY' "$RUN_ID" "$cid" "$phase" "$error_detail"
import json
import sys
run_id, cid, phase, detail = sys.argv[1:]
print(json.dumps({
    "run_id": run_id,
    "catalog_id": int(cid),
    "phase": phase,
    "status": "failed",
    "task_failed": True,
    "error": "task_submission_error",
    "error_detail": detail,
}, separators=(",", ":")))
PY
)
    else
      LAST_FAILURE_REASON="task_submission_failure"
      payload=$(printf '{"run_id":"%s","catalog_id":%s,"phase":"%s","status":"failed","task_failed":true,"error":"invalid_task_id"}' "$RUN_ID" "$cid" "$phase")
    fi
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
      LAST_FAILURE_REASON="task_poll_timeout"
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

  if [[ "$status" == "failed" ]]; then
    if [[ -z "$LAST_FAILURE_REASON" ]]; then
      LAST_FAILURE_REASON="task_failed"
    fi
    return 1
  fi
  return 0
}

extract_failures=0
segment_failures=0
summarize_failures=0
task_submission_failures=0
task_poll_timeouts=0
phases=0
for cid in "${CIDS[@]}"; do
  if ! run_endpoint "$cid" "extract" "extract/$cid?force=true&ocr_fallback=false"; then
    extract_failures=$((extract_failures + 1))
    [[ "$LAST_FAILURE_REASON" == "task_submission_failure" ]] && task_submission_failures=$((task_submission_failures + 1))
    [[ "$LAST_FAILURE_REASON" == "task_poll_timeout" ]] && task_poll_timeouts=$((task_poll_timeouts + 1))
  fi
  phases=$((phases + 1))
  if ! run_endpoint "$cid" "segment" "segment/$cid?force=true"; then
    segment_failures=$((segment_failures + 1))
    [[ "$LAST_FAILURE_REASON" == "task_submission_failure" ]] && task_submission_failures=$((task_submission_failures + 1))
    [[ "$LAST_FAILURE_REASON" == "task_poll_timeout" ]] && task_poll_timeouts=$((task_poll_timeouts + 1))
  fi
  phases=$((phases + 1))
  if ! run_endpoint "$cid" "summarize" "summarize/$cid?force=true"; then
    summarize_failures=$((summarize_failures + 1))
    [[ "$LAST_FAILURE_REASON" == "task_submission_failure" ]] && task_submission_failures=$((task_submission_failures + 1))
    [[ "$LAST_FAILURE_REASON" == "task_poll_timeout" ]] && task_poll_timeouts=$((task_poll_timeouts + 1))
  fi
  phases=$((phases + 1))
done

gating_failures=$((segment_failures + summarize_failures))
all_phase_failures=$((extract_failures + gating_failures))

python3 - <<'PY' "$RUN_ID" "$API_URL" "$preflight_status" "$DAY_SUMMARY_JSON" "$TASKS_JSONL" "${#CIDS[@]}" "$phases" "$all_phase_failures" "$extract_failures" "$segment_failures" "$summarize_failures" "$gating_failures" "$task_submission_failures" "$task_poll_timeouts" "$TASK_MAX_WAIT_SECONDS"
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
    task_submission_failures,
    task_poll_timeouts,
    task_max_wait_seconds,
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
cap_seconds = float(task_max_wait_seconds)

def p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, int((0.95 * len(ordered)) + 0.999999) - 1)
    return float(ordered[idx])

failure_reason = ""
if int(gating_failures) > 0:
    if int(task_submission_failures) > 0:
        failure_reason = "task_submission_failures"
    elif int(task_poll_timeouts) > 0:
        failure_reason = "task_poll_timeout"
    else:
        failure_reason = "gating_phase_failures"

payload = {
    "run_id": run_id,
    "status": "failed" if int(gating_failures) > 0 else "complete",
    "failure_reason": failure_reason,
    "api_url": api_url,
    "preflight_status": preflight_status,
    "cids_total": int(cids_total),
    "phases_total": int(phases_total),
    "phases_failed": int(all_phase_failures),
    "extract_failures": int(extract_failures),
    "segment_failures": int(segment_failures),
    "summarize_failures": int(summarize_failures),
    "gating_failures": int(gating_failures),
    "task_submission_failures": int(task_submission_failures),
    "task_poll_timeouts": int(task_poll_timeouts),
    "duration_total_s": float(sum(phase_durations)),
    "phase_duration_p95_s": p95(phase_durations),
    # Keep raw phase p95 and a capped variant for queue proxy drift analysis.
    "phase_duration_p95_s_capped": p95([min(v, cap_seconds) for v in phase_durations]),
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

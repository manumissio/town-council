#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROFILE_PATH="${PROFILE_PATH:-env/profiles/gemma3_270m_host_metal_conservative.env}"
APP_SERVICES=(postgres redis meilisearch tika semantic semantic-worker api worker enrichment-worker monitor frontend)

if [[ ! -f "$PROFILE_PATH" ]]; then
  echo "[dev_up_host_metal] Missing profile: $PROFILE_PATH" >&2
  exit 2
fi

# shellcheck disable=SC1090
source "$PROFILE_PATH"

echo "[dev_up_host_metal] Using profile: $PROFILE_PATH"
echo "[dev_up_host_metal] Target inference endpoint: ${LOCAL_AI_HTTP_BASE_URL:-<unset>}"

echo "[dev_up_host_metal] Bootstrapping host Ollama alias..."
PROFILE_PATH="$PROFILE_PATH" HOST_OLLAMA_BASE_URL="${HOST_OLLAMA_BASE_URL:-http://localhost:11434}" MODEL_NAME="${LOCAL_AI_HTTP_MODEL:-gemma-3-270m-custom}" bash ./scripts/bootstrap_host_ollama_270m.sh

echo "[dev_up_host_metal] Ensuring Docker inference is stopped..."
docker compose stop inference >/dev/null 2>&1 || true
if docker compose ps --services --status running | grep -qx "inference"; then
  echo "[dev_up_host_metal] Docker inference is still running; aborting to avoid backend ambiguity." >&2
  exit 2
fi

echo "[dev_up_host_metal] Building and starting host-Metal app services..."
docker compose --env-file "$PROFILE_PATH" up -d --build "${APP_SERVICES[@]}"

echo "[dev_up_host_metal] Initializing database schema..."
docker compose --env-file "$PROFILE_PATH" run --rm pipeline python db_init.py

echo "[dev_up_host_metal] Verifying worker readiness against host Ollama..."
docker compose --env-file "$PROFILE_PATH" exec -T worker python scripts/worker_healthcheck.py

echo "[dev_up_host_metal] Verifying worker backend provenance..."
docker compose --env-file "$PROFILE_PATH" exec -T worker python -c "import os,sys; actual=os.getenv('LOCAL_AI_HTTP_BASE_URL','').strip(); expected='${LOCAL_AI_HTTP_BASE_URL:-}'; print(actual); sys.exit(0 if actual == expected else 1)"

echo "[dev_up_host_metal] Smoke check: verify API health endpoint..."
curl -fsS http://localhost:8000/health >/dev/null
echo "[dev_up_host_metal] OK"

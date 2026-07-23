#!/usr/bin/env bash
set -euo pipefail

# Dev helper: start the stack in a way that avoids "stale image" surprises.
#
# Why this exists:
# Docker Compose will happily start containers from an old image if you forget `--build`.
# When requirements change, that can look like "the API is broken" (missing imports).

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "[dev_up] Missing .env. Create it from .env.example before starting the stack." >&2
  exit 1
fi

CORE_SERVICES=(postgres redis meilisearch tika inference semantic semantic-worker api worker enrichment-worker monitor frontend)
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)

echo "[dev_up] Building and starting core services..."
"${COMPOSE[@]}" up -d --build "${CORE_SERVICES[@]}"

echo "[dev_up] Bootstrapping local model artifacts..."
bash ./scripts/bootstrap_local_models.sh

echo "[dev_up] Initializing database schema..."
"${COMPOSE[@]}" run --rm pipeline python db_init.py

echo "[dev_up] Smoke check: verify API container can import BeautifulSoup (bs4)..."
"${COMPOSE[@]}" run --rm api python -c "import bs4; print('bs4', bs4.__version__)"

echo "[dev_up] Smoke check: verify API health endpoint..."
curl -fsS http://localhost:8000/health >/dev/null
echo "[dev_up] OK"

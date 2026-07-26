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

MIGRATION_PREREQUISITES=(postgres)
CORE_SERVICES=(postgres redis meilisearch tika inference semantic semantic-worker api worker enrichment-worker monitor frontend ingress)
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)
POSTGRES_READY_ATTEMPTS=30
POSTGRES_READY_DELAY_SECONDS=1

echo "[dev_up] Building and starting migration prerequisites..."
"${COMPOSE[@]}" up -d --build "${MIGRATION_PREREQUISITES[@]}"

echo "[dev_up] Waiting for PostgreSQL..."
postgres_ready=false
for ((postgres_ready_attempt = 1; postgres_ready_attempt <= POSTGRES_READY_ATTEMPTS; postgres_ready_attempt++)); do
  if "${COMPOSE[@]}" exec -T postgres pg_isready \
    -U "${POSTGRES_USER:-town_council}" \
    -d "${POSTGRES_DB:-town_council_db}"; then
    postgres_ready=true
    break
  fi
  sleep "$POSTGRES_READY_DELAY_SECONDS"
done
if [[ "$postgres_ready" != "true" ]]; then
  echo "[dev_up] PostgreSQL did not become ready." >&2
  exit 1
fi

echo "[dev_up] Migrating database schema..."
"${COMPOSE[@]}" run --rm --build --no-deps pipeline python db_migrate.py

echo "[dev_up] Bootstrapping local model artifacts..."
bash ./scripts/bootstrap_local_models.sh

echo "[dev_up] Building and starting schema consumers..."
"${COMPOSE[@]}" up -d --build "${CORE_SERVICES[@]}"

echo "[dev_up] Smoke check: verify API container can import BeautifulSoup (bs4)..."
"${COMPOSE[@]}" run --rm api python -c "import bs4; print('bs4', bs4.__version__)"

echo "[dev_up] Smoke check: verify API health endpoint..."
curl -fsS http://localhost:8000/health >/dev/null
echo "[dev_up] OK"

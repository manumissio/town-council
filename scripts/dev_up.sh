#!/usr/bin/env bash
set -euo pipefail

# Dev helper: start the stack in a way that avoids "stale image" surprises.
#
# Why this exists:
# Docker Compose will happily start containers from an old image if you forget `--build`.
# When requirements change, that can look like "the API is broken" (missing imports).

cd "$(dirname "$0")/.."

echo "[dev_up] Building and starting services..."
docker compose up -d --build

echo "[dev_up] Initializing database schema..."
docker compose run --rm pipeline python db_init.py

echo "[dev_up] Smoke check: verify API container can import BeautifulSoup (bs4)..."
docker compose run --rm api python -c "import bs4; print('bs4', bs4.__version__)"

echo "[dev_up] Smoke check: verify API health endpoint..."
curl -fsS http://localhost:8000/health >/dev/null
echo "[dev_up] OK"


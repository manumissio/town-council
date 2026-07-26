#!/usr/bin/env bash
set -euo pipefail

USAGE_EXIT_CODE=64
DESTINATION_EXIT_CODE=73
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)

usage() {
  printf 'Usage: %s OUTPUT_PATH\n' "$(basename "$0")"
}

cleanup_backup() {
  if [[ -n "${backup_temp_path:-}" && -e "$backup_temp_path" ]]; then
    rm -f "$backup_temp_path"
  fi
}

if [[ $# -eq 1 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit "$USAGE_EXIT_CODE"
fi

backup_path="$1"
if [[ "$backup_path" != /* ]]; then
  backup_path="$PWD/$backup_path"
fi
backup_parent="$(dirname "$backup_path")"

if [[ ! -d "$backup_parent" ]]; then
  printf '[backup_db] Parent directory does not exist: %s\n' "$backup_parent" >&2
  exit "$DESTINATION_EXIT_CODE"
fi
if [[ -e "$backup_path" ]]; then
  printf '[backup_db] Destination already exists: %s\n' "$backup_path" >&2
  exit "$DESTINATION_EXIT_CODE"
fi

cd "$(dirname "$0")/.."
umask 077
backup_temp_path="$(mktemp "${backup_path}.partial.XXXXXX")"
trap cleanup_backup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '[backup_db] Creating PostgreSQL archive: %s\n' "$backup_path" >&2
"${COMPOSE[@]}" exec -T postgres sh -ec '
  exec pg_dump \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --format=custom \
    --no-owner \
    --no-privileges
' > "$backup_temp_path"

if [[ ! -s "$backup_temp_path" ]]; then
  printf '[backup_db] PostgreSQL produced an empty archive.\n' >&2
  exit 1
fi

"${COMPOSE[@]}" exec -T postgres pg_restore --list \
  < "$backup_temp_path" >/dev/null
ln "$backup_temp_path" "$backup_path"
unlink "$backup_temp_path"
backup_temp_path=""
trap - EXIT INT TERM

printf '[backup_db] Verified archive written: %s\n' "$backup_path" >&2

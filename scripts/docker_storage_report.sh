#!/usr/bin/env bash
set -euo pipefail

echo "== Docker image sizes =="
if command -v rg >/dev/null 2>&1; then
  docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | rg '^town-council'
else
  docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | grep '^town-council'
fi

echo
echo "== Docker storage usage =="
docker system df -v

echo
echo "== Notes =="
echo "- The largest local storage consumers are usually persistent data volumes and build cache."
echo "- Use this report before deciding whether a manual prune is necessary."
echo "- This helper does not delete images, cache, or volumes."

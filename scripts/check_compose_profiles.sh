#!/usr/bin/env bash
set -euo pipefail

default_services="$(docker compose config --services)"
batch_services="$(docker compose --profile batch-tools config --services)"

echo "== Default Compose services =="
printf '%s\n' "$default_services"

echo
echo "== batch-tools Compose services =="
printf '%s\n' "$batch_services"

echo
echo "== Contract checks =="

for svc in monitor enrichment-worker; do
  if ! printf '%s\n' "$default_services" | grep -qx "$svc"; then
    echo "missing default service: $svc" >&2
    exit 1
  fi
done

for svc in pipeline-batch nlp tables topics; do
  if printf '%s\n' "$default_services" | grep -qx "$svc"; then
    echo "batch-only service leaked into default config: $svc" >&2
    exit 1
  fi
  if ! printf '%s\n' "$batch_services" | grep -qx "$svc"; then
    echo "missing batch-tools service: $svc" >&2
    exit 1
  fi
done

echo "profile contract OK"

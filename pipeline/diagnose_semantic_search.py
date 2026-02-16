"""
Diagnose semantic search readiness and retrieval behavior.

Usage:
  docker compose run --rm pipeline python diagnose_semantic_search.py --query zoning --limit 10
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

from pipeline.semantic_index import get_semantic_backend


def _fetch_json(url: str, headers: dict[str, str]) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        status = resp.status
        data = json.loads(resp.read().decode("utf-8"))
        return status, data


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose semantic search behavior.")
    parser.add_argument("--query", default="zoning")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--base-url", default="http://api:8000")
    parser.add_argument("--api-key", default="dev_secret_key_change_me")
    parser.add_argument("--city", default=None)
    args = parser.parse_args()

    backend = get_semantic_backend()
    health = backend.health()
    print("=== backend health ===")
    print(json.dumps(health, indent=2))

    params = {"q": args.query, "limit": str(args.limit), "offset": "0"}
    if args.city:
        params["city"] = args.city
    url = f"{args.base_url.rstrip('/')}/search/semantic?{urllib.parse.urlencode(params)}"

    print("\n=== api probe ===")
    print(url)
    try:
        status, payload = _fetch_json(url, headers={"X-API-Key": args.api_key})
        print(f"status={status}")
        print(f"estimatedTotalHits={payload.get('estimatedTotalHits')}")
        print(f"diagnostics={payload.get('semantic_diagnostics')}")
        for hit in (payload.get("hits") or [])[: args.limit]:
            print(
                f"{hit.get('id')}  score={hit.get('semantic_score')}  date={hit.get('date')}  "
                f"type={hit.get('result_type')}  {(hit.get('event_name') or hit.get('title') or '')[:100]}"
            )
    except Exception as exc:
        print(f"probe_error={exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

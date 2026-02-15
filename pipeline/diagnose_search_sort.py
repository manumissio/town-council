"""
Diagnose whether /search sorting is working (newest/oldest/relevance).

Usage (Docker):
  docker compose run --rm pipeline python diagnose_search_sort.py --query zoning --limit 10

Default base URL is the Docker network name for the API service.
Override with --base-url when running on the host.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        # record_date is expected to be YYYY-MM-DD (ISO-8601 date).
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _fetch_hits(base_url: str, query: str, sort: str, limit: int) -> list[dict]:
    params = {
        "q": query,
        "limit": str(limit),
        "offset": "0",
        "sort": sort,
    }
    url = f"{base_url.rstrip('/')}/search?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    payload = json.loads(body)
    return payload.get("hits") or []


def _is_monotonic(values: list[datetime], direction: str) -> bool:
    if len(values) <= 1:
        return True
    if direction == "desc":
        return all(values[i] >= values[i + 1] for i in range(len(values) - 1))
    return all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose /search sorting behavior.")
    parser.add_argument("--query", default="zoning", help="Search query string.")
    parser.add_argument("--limit", type=int, default=10, help="Number of hits to print per sort mode.")
    parser.add_argument(
        "--base-url",
        default="http://api:8000",
        help="API base URL (Docker default: http://api:8000). Use http://localhost:8000 on host.",
    )
    args = parser.parse_args()

    sorts = ["relevance", "newest", "oldest"]
    results = {}
    for s in sorts:
        try:
            results[s] = _fetch_hits(args.base_url, args.query, s, args.limit)
        except Exception as e:
            print(f"[{s}] ERROR fetching hits: {e}", file=sys.stderr)
            return 2

    for s in sorts:
        print(f"\n=== sort={s} ===")
        hits = results[s]
        null_dates = 0
        parsed_dates = []
        for h in hits:
            dt = _parse_iso_date(h.get("date"))
            if dt is None:
                null_dates += 1
            else:
                parsed_dates.append(dt)
            label = (h.get("title") or h.get("event_name") or "").strip()
            if len(label) > 80:
                label = label[:77] + "..."
            print(f"{h.get('id')}  date={h.get('date')}  type={h.get('result_type')}  {label}")
        print(f"null_date_hits={null_dates}/{len(hits)}")

        if s == "newest":
            newest_ok = _is_monotonic([d for d in parsed_dates], 'desc')
            print(f"monotonic_desc={newest_ok}")
        if s == "oldest":
            oldest_ok = _is_monotonic([d for d in parsed_dates], 'asc')
            print(f"monotonic_asc={oldest_ok}")

    # Heuristic warning: if either monotonic check fails and dates are present, sorting
    # is likely not dominating relevance (common when rankingRules doesn't prioritize "sort").
    newest_dates = [_parse_iso_date(h.get("date")) for h in results["newest"]]
    oldest_dates = [_parse_iso_date(h.get("date")) for h in results["oldest"]]
    newest_dates = [d for d in newest_dates if d is not None]
    oldest_dates = [d for d in oldest_dates if d is not None]

    if newest_dates and not _is_monotonic(newest_dates, "desc"):
        print(
            "\nWARNING: newest results are not monotonically descending by date. Sorting may be ineffective.",
            file=sys.stderr,
        )
        return 1
    if oldest_dates and not _is_monotonic(oldest_dates, "asc"):
        print(
            "\nWARNING: oldest results are not monotonically ascending by date. Sorting may be ineffective.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

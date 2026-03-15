#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.db_session import db_session
from pipeline.models import EventStage, UrlStage


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_iso_utc(value: str) -> datetime:
    dt = datetime.strptime(value, ISO_FMT)
    return dt.replace(tzinfo=timezone.utc).replace(tzinfo=None)


def _source_aliases_for_city(city: str) -> set[str]:
    aliases = {city}
    legacy_aliases = {
        "san_mateo": {"san mateo"},
        "san_leandro": {"san leandro"},
        "mtn_view": {"mountain view"},
    }
    aliases.update(legacy_aliases.get(city, set()))
    return aliases


def _ocd_division_id_for_city(city: str) -> str:
    return f"ocd-division/country:us/state:ca/place:{city}"


def _collect_crawl_evidence(city: str, start_at: str, end_at: str) -> dict[str, int | bool | str]:
    start_dt = _parse_iso_utc(start_at)
    # The runner records second-precision timestamps, while staging rows keep
    # microseconds. Treat end-at as inclusive for the whole trailing second.
    end_dt_exclusive = _parse_iso_utc(end_at) + timedelta(seconds=1)
    aliases = sorted(_source_aliases_for_city(city))
    ocd_division_id = _ocd_division_id_for_city(city)

    with db_session() as session:
        event_stage_count = (
            session.query(EventStage)
            .filter(
                EventStage.scraped_datetime >= start_dt,
                EventStage.scraped_datetime < end_dt_exclusive,
                or_(
                    EventStage.ocd_division_id == ocd_division_id,
                    EventStage.source.in_(aliases),
                ),
            )
            .count()
        )
        url_stage_count = (
            session.query(UrlStage)
            .filter(
                UrlStage.created_at >= start_dt,
                UrlStage.created_at < end_dt_exclusive,
                UrlStage.ocd_division_id == ocd_division_id,
            )
            .count()
        )

    return {
        "city": city,
        "start_at_utc": start_at,
        "end_at_utc": end_at,
        "event_stage_count": int(event_stage_count),
        "url_stage_count": int(url_stage_count),
        "has_evidence": bool(event_stage_count > 0 or url_stage_count > 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a city crawl produced staging evidence")
    parser.add_argument("--city", required=True)
    parser.add_argument("--start-at", required=True)
    parser.add_argument("--end-at", required=True)
    args = parser.parse_args()

    payload = _collect_crawl_evidence(args.city, args.start_at, args.end_at)
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["has_evidence"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

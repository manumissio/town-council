from datetime import UTC, datetime

from pipeline.models import EventStage, UrlStage
from scripts import check_city_crawl_evidence as mod


def test_crawl_evidence_parser_returns_aware_utc():
    parsed_at = mod._parse_iso_utc("2026-03-15T02:14:23Z")

    assert parsed_at == datetime(2026, 3, 15, 2, 14, 23, tzinfo=UTC)
    assert parsed_at.utcoffset().total_seconds() == 0


def test_collect_crawl_evidence_includes_rows_in_end_second(db_session):
    db_session.add(
        EventStage(
            ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
            source="san_leandro",
            scraped_datetime=datetime(2026, 3, 15, 2, 14, 23, 157000),
            record_date=datetime(2026, 3, 15).date(),
            name="City Council",
            source_url="https://sanleandro.legistar.com/Calendar.aspx",
        )
    )
    db_session.add(
        UrlStage(
            ocd_division_id="ocd-division/country:us/state:ca/place:san_leandro",
            created_at=datetime(2026, 3, 15, 2, 14, 23, 157000),
            url="https://example.com/agenda.pdf",
            url_hash="abc123",
            category="agenda",
            event="City Council",
            event_date=datetime(2026, 3, 15).date(),
        )
    )
    db_session.commit()

    payload = mod._collect_crawl_evidence(
        "san_leandro",
        "2026-03-15T02:14:18Z",
        "2026-03-15T02:14:23Z",
    )

    assert payload["event_stage_count"] == 1
    assert payload["url_stage_count"] == 1
    assert payload["has_evidence"] is True

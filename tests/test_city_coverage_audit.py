import importlib.util
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.city_coverage_audit import (
    build_city_coverage_audit,
    build_month_window,
    compute_expected_monthly_event_baseline,
)
from pipeline.models import Base, Catalog, Document, Event, Place


spec = importlib.util.spec_from_file_location(
    "audit_city_coverage",
    Path("scripts/audit_city_coverage.py"),
)
script_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = script_mod
spec.loader.exec_module(script_mod)


def _build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_build_month_window_includes_zero_months_in_order():
    months = build_month_window(4, as_of=date(2026, 3, 28))

    assert [value.isoformat() for value in months] == [
        "2025-12-01",
        "2026-01-01",
        "2026-02-01",
        "2026-03-01",
    ]


def test_compute_expected_monthly_event_baseline_is_conservative_for_small_counts():
    baseline, threshold = compute_expected_monthly_event_baseline([0, 1, 2, 4])

    assert baseline == 1.5
    assert threshold is None


def test_build_city_coverage_audit_rolls_up_months_and_flags_gaps():
    session = _build_session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
    )
    session.add(place)
    session.flush()

    jan_event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="January Council",
        source="san_mateo",
        record_date=date(2026, 1, 10),
    )
    feb_event_1 = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="February Council A",
        source="san mateo",
        record_date=date(2026, 2, 3),
    )
    feb_event_2 = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="February Council B",
        source="san_mateo",
        record_date=date(2026, 2, 17),
    )
    mar_event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="March Council",
        source="san_mateo",
        record_date=date(2026, 3, 14),
    )
    foreign_event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="Ignore Me",
        source="berkeley",
        record_date=date(2026, 2, 4),
    )
    session.add_all([jan_event, feb_event_1, feb_event_2, mar_event, foreign_event])
    session.flush()

    feb_catalog_empty = Catalog(url_hash="feb-empty", location="/tmp/feb-empty.pdf", content=None, summary=None)
    feb_catalog_empty_2 = Catalog(url_hash="feb-empty-2", location="/tmp/feb-empty-2.pdf", content="", summary=None)
    mar_catalog_content = Catalog(
        url_hash="mar-content",
        location="/tmp/mar-content.pdf",
        content="Agenda extracted text",
        summary=None,
    )
    mar_catalog_summary = Catalog(
        url_hash="mar-summary",
        location="/tmp/mar-summary.pdf",
        content="Agenda extracted text",
        summary="Summary exists",
    )
    foreign_catalog = Catalog(url_hash="foreign", location="/tmp/foreign.pdf", content="x", summary="y")
    session.add_all([feb_catalog_empty, feb_catalog_empty_2, mar_catalog_content, mar_catalog_summary, foreign_catalog])
    session.flush()

    session.add_all(
        [
            Document(
                place_id=place.id,
                event_id=feb_event_1.id,
                catalog_id=feb_catalog_empty.id,
                url="https://example.com/feb-empty",
                url_hash="feb-empty",
                category="agenda",
            ),
            Document(
                place_id=place.id,
                event_id=feb_event_2.id,
                catalog_id=feb_catalog_empty_2.id,
                url="https://example.com/feb-empty-2",
                url_hash="feb-empty-2",
                category="agenda",
            ),
            Document(
                place_id=place.id,
                event_id=mar_event.id,
                catalog_id=mar_catalog_content.id,
                url="https://example.com/mar-content",
                url_hash="mar-content",
                category="agenda",
            ),
            Document(
                place_id=place.id,
                event_id=mar_event.id,
                catalog_id=mar_catalog_summary.id,
                url="https://example.com/mar-summary",
                url_hash="mar-summary",
                category="agenda",
            ),
            Document(
                place_id=place.id,
                event_id=foreign_event.id,
                catalog_id=foreign_catalog.id,
                url="https://example.com/foreign",
                url_hash="foreign",
                category="agenda",
            ),
        ]
    )
    session.commit()

    audit = build_city_coverage_audit(
        session,
        city="san_mateo",
        months=4,
        as_of=date(2026, 3, 28),
    )

    assert audit.city == "san_mateo"
    assert audit.date_from == "2025-12-01"
    assert audit.date_to == "2026-03-28"
    assert audit.source_counts == {"san mateo": 1, "san_mateo": 3}
    assert audit.totals == {
        "event_count": 4,
        "meeting_count": 4,
        "agenda_document_count": 4,
        "agenda_catalog_count": 4,
        "agenda_catalogs_with_content": 2,
        "agenda_catalogs_with_summary": 1,
    }

    monthly = {row.month: row for row in audit.monthly}
    assert monthly["2025-12"].flags == ["no_events"]
    assert monthly["2026-01"].flags == ["events_but_no_agendas"]
    assert monthly["2026-02"].event_count == 2
    assert monthly["2026-02"].agenda_document_count == 2
    assert monthly["2026-02"].agenda_catalogs_with_content == 0
    assert monthly["2026-02"].flags == ["agendas_but_no_content"]
    assert monthly["2026-02"].meeting_count == 2
    assert monthly["2026-03"].agenda_catalogs_with_content == 2
    assert monthly["2026-03"].agenda_catalogs_with_summary == 1


def test_build_city_coverage_audit_flags_low_cadence_and_content_without_summaries():
    session = _build_session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
    )
    session.add(place)
    session.flush()

    counts = {
        date(2025, 12, 5): 4,
        date(2026, 1, 5): 4,
        date(2026, 2, 5): 1,
        date(2026, 3, 5): 4,
    }
    counter = 0
    for record_date, event_total in counts.items():
        created_events = []
        for _ in range(event_total):
            counter += 1
            event = Event(
                place_id=place.id,
                ocd_division_id=place.ocd_division_id,
                name=f"Event {counter}",
                source="san_mateo",
                record_date=record_date,
            )
            session.add(event)
            session.flush()
            created_events.append(event)
            if record_date.month != 2:
                catalog = Catalog(
                    url_hash=f"catalog-{counter}",
                    location=f"/tmp/catalog-{counter}.pdf",
                    content="Agenda text",
                    summary="Summary" if len(created_events) == 1 else None,
                )
                session.add(catalog)
                session.flush()
                session.add(
                    Document(
                        place_id=place.id,
                        event_id=event.id,
                        catalog_id=catalog.id,
                        url=f"https://example.com/{counter}",
                        url_hash=f"catalog-{counter}",
                        category="agenda",
                    )
                )
        if record_date.month == 2:
            catalog = Catalog(
                url_hash="low-cadence-catalog",
                location="/tmp/low-cadence.pdf",
                content="Agenda text",
                summary=None,
            )
            session.add(catalog)
            session.flush()
            session.add(
                Document(
                    place_id=place.id,
                    event_id=created_events[0].id,
                    catalog_id=catalog.id,
                    url="https://example.com/low-cadence",
                    url_hash="low-cadence-catalog",
                    category="agenda",
                )
            )

    session.commit()

    audit = build_city_coverage_audit(
        session,
        city="san_mateo",
        months=4,
        as_of=date(2026, 3, 28),
    )

    assert audit.expected_monthly_event_baseline == 4.0
    assert audit.below_expected_cadence_threshold == 2
    assert audit.expected_monthly_meeting_baseline == 4.0
    assert audit.below_expected_meeting_cadence_threshold == 2
    monthly = {row.month: row for row in audit.monthly}
    assert monthly["2026-02"].flags == ["content_but_no_summaries", "below_expected_cadence"]


def test_build_city_coverage_audit_dedupes_same_day_event_rows_for_cadence():
    session = _build_session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
    )
    session.add(place)
    session.flush()

    jan_duplicate_1 = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="Regular City Council Meeting",
        source="san_mateo",
        record_date=date(2026, 1, 5),
    )
    jan_duplicate_2 = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="  Regular   City Council   Meeting  ",
        source="san_mateo",
        record_date=date(2026, 1, 5),
    )
    feb_event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="Regular City Council Meeting",
        source="san_mateo",
        record_date=date(2026, 2, 2),
    )
    mar_event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="Regular City Council Meeting",
        source="san_mateo",
        record_date=date(2026, 3, 2),
    )
    session.add_all([jan_duplicate_1, jan_duplicate_2, feb_event, mar_event])
    session.commit()

    audit = build_city_coverage_audit(
        session,
        city="san_mateo",
        months=3,
        as_of=date(2026, 3, 28),
    )

    monthly = {row.month: row for row in audit.monthly}
    assert monthly["2026-01"].event_count == 2
    assert monthly["2026-01"].meeting_count == 1
    assert monthly["2026-01"].flags == ["events_but_no_agendas"]
    assert audit.totals["event_count"] == 4
    assert audit.totals["meeting_count"] == 3


def test_build_city_coverage_audit_skips_below_expected_cadence_for_current_month():
    session = _build_session()
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
    )
    session.add(place)
    session.flush()

    counts = {
        date(2025, 12, 5): 4,
        date(2026, 1, 5): 4,
        date(2026, 2, 5): 4,
        date(2026, 3, 5): 1,
    }
    counter = 0
    for record_date, event_total in counts.items():
        for _ in range(event_total):
            counter += 1
            session.add(
                Event(
                    place_id=place.id,
                    ocd_division_id=place.ocd_division_id,
                    name=f"Event {counter}",
                    source="san_mateo",
                    record_date=record_date,
                )
            )
    session.commit()

    audit = build_city_coverage_audit(
        session,
        city="san_mateo",
        months=4,
        as_of=date(2026, 3, 28),
    )

    monthly = {row.month: row for row in audit.monthly}
    assert audit.expected_monthly_meeting_baseline == 4.0
    assert audit.below_expected_meeting_cadence_threshold == 2
    assert "below_expected_cadence" not in monthly["2026-03"].flags


def test_audit_city_coverage_cli_labels_coverage_audit(mocker, capsys):
    audit = mocker.Mock()
    audit.city = "san_mateo"
    audit.date_from = "2025-04-01"
    audit.date_to = "2026-03-28"
    audit.months = 12
    audit.expected_monthly_event_baseline = 2.5
    audit.below_expected_cadence_threshold = 2
    audit.expected_monthly_meeting_baseline = 2.0
    audit.below_expected_meeting_cadence_threshold = 1
    audit.totals = {
        "event_count": 24,
        "meeting_count": 20,
        "agenda_document_count": 24,
        "agenda_catalog_count": 24,
        "agenda_catalogs_with_content": 22,
        "agenda_catalogs_with_summary": 20,
    }
    audit.source_counts = {"san_mateo": 20, "san mateo": 4}
    audit.monthly = [
        mocker.Mock(
            month="2026-03",
            event_count=2,
            meeting_count=1,
            agenda_document_count=2,
            agenda_catalog_count=2,
            agenda_catalogs_with_content=2,
            agenda_catalogs_with_summary=1,
            source_event_counts={"san_mateo": 2},
            source_meeting_counts={"san_mateo": 1},
            flags=["content_but_no_summaries"],
        )
    ]
    audit.suspicious_months = [{"month": "2026-03", "flags": ["content_but_no_summaries"]}]
    mocker.patch.object(script_mod, "db_session")
    mocker.patch.object(script_mod, "build_city_coverage_audit", return_value=audit)
    mocker.patch.object(sys, "argv", ["audit_city_coverage.py", "--city", "san_mateo"])

    exit_code = script_mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "City Coverage Audit" in captured.out
    assert "window: 2025-04-01 -> 2026-03-28 (12 months)" in captured.out
    assert "expected_monthly_meeting_baseline: 2.00" in captured.out
    assert "Suspicious months" in captured.out
    assert "This audit measures source and downstream artifact coverage" in captured.out

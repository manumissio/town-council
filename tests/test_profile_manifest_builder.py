from contextlib import contextmanager
import ast
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline import profile_manifest, profile_manifest_builder, profile_manifest_candidates
from pipeline.agenda_worker import select_catalog_ids_for_agenda_segmentation
from pipeline.content_hash import compute_content_hash
from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Organization, Place
from pipeline.profile_manifest_preconditioning import apply_preconditioning
from pipeline.summary_backfill_queries import select_catalog_ids_for_summary_hydration
from pipeline.summary_freshness import compute_agenda_items_hash


V1_JSON_SHA256 = "862d8dd0b8297463d4f19f0ea2590183d5a78d9cf6477a530fd7dc73f445f16c"
V1_TEXT_SHA256 = "9867bea1aa140317d4a84ebb3670fbacd76b37bf163e4e66963e8d15cfcfa17b"
V1_JSON_PATH = Path("profiling/manifests/baseline_representative_v1.json")
V1_TEXT_PATH = Path("profiling/manifests/baseline_representative_v1.txt")
V2_JSON_PATH = Path("profiling/manifests/baseline_representative_v2.json")
V2_TEXT_PATH = Path("profiling/manifests/baseline_representative_v2.txt")


def _valid_manifest_package() -> dict[str, object]:
    return {
        "schema_version": 3,
        "manifest_name": "replay_contract",
        "catalog_ids": [1, 2, 3, 4, 5],
        "strata": {"extract": [1], "segment": [2], "summary": [3], "entity": [4], "org": [5]},
        "extract_source_sha256": {"1": "a" * 64},
        "org_event_resets": [{"catalog_id": 5, "event_id": 50}],
        "expected_phase_coverage": {"extract": 1, "segment": 1, "summary": 1, "entity": 1, "org": 1},
        "safety": {"org_reset_requires_single_document_event": True},
    }


def _extract_reset_package(catalog_ids: list[int], source_digests: dict[int, str]) -> dict[str, object]:
    return {
        "schema_version": 3,
        "manifest_name": "extract_replay",
        "catalog_ids": catalog_ids,
        "strata": {"extract": catalog_ids, "segment": [], "summary": [], "entity": [], "org": []},
        "extract_source_sha256": {str(catalog_id): source_digests[catalog_id] for catalog_id in catalog_ids},
        "org_event_resets": [],
        "expected_phase_coverage": {"extract": len(catalog_ids), "segment": 0, "summary": 0, "entity": 0, "org": 0},
        "safety": {"org_reset_requires_single_document_event": True},
    }


def test_profile_manifest_facade_exports_current_contract():
    expected_names = [
        "MANIFEST_PACKAGE_SCHEMA_VERSION",
        "DEFAULT_PHASE_QUOTAS",
        "utc_now_iso",
        "sidecar_path_for_manifest",
        "load_manifest_package",
        "validate_manifest_package",
        "build_manifest_package",
        "preconditioning_report",
        "apply_preconditioning",
        "db_session",
    ]
    retired_test_seams = [
        "_extract_candidates",
        "_segment_reset_candidates",
        "_summary_reset_candidates",
        "_entity_reset_candidates",
        "_org_reset_candidates",
        "select_catalog_ids_for_entity_backfill",
        "select_catalog_ids_for_processing",
    ]

    missing_names = [name for name in expected_names if not hasattr(profile_manifest, name)]
    retained_test_seams = [name for name in retired_test_seams if hasattr(profile_manifest, name)]

    assert missing_names == []
    assert retained_test_seams == []
    assert not hasattr(profile_manifest, "_people_reset_candidates")
    assert not hasattr(profile_manifest, "_is_safe_people_reset_name")


def test_profile_manifest_implementation_modules_do_not_import_facade():
    module_paths = [
        Path("pipeline/profile_manifest_contracts.py"),
        Path("pipeline/profile_manifest_io.py"),
        Path("pipeline/profile_manifest_candidates.py"),
        Path("pipeline/profile_manifest_builder.py"),
        Path("pipeline/profile_manifest_preconditioning.py"),
    ]
    offenders: list[str] = []

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pipeline.profile_manifest":
                offenders.append(str(module_path))
            if isinstance(node, ast.Import):
                if any(alias.name == "pipeline.profile_manifest" for alias in node.names):
                    offenders.append(str(module_path))

    assert offenders == []


def test_build_manifest_package_honors_phase_quotas(tmp_path: Path):
    @contextmanager
    def fake_db_session():
        yield object()

    selected_source = tmp_path / "selected.pdf"
    selected_source.write_bytes(b"selected source")
    package = profile_manifest_builder.build_manifest_package(
        "baseline_demo",
        quotas={"extract": 1, "segment": 1, "summary": 1, "entity": 1, "org": 1},
        session_factory=fake_db_session,
        candidate_loaders={
            "extract": lambda session: [
                {"catalog_id": 1, "source_location": str(selected_source)},
                {"catalog_id": 2, "source_location": str(tmp_path / "unselected-missing.pdf")},
            ],
            "segment": lambda session: [{"catalog_id": 3}, {"catalog_id": 4}],
            "summary": lambda session: [{"catalog_id": 5}, {"catalog_id": 6}],
            "entity": lambda session: [{"catalog_id": 7}, {"catalog_id": 8}],
            "org": lambda session: [{"catalog_id": 9, "event_id": 90}],
        },
        generated_at_factory=lambda: "2026-08-09T00:00:00+00:00",
    )

    assert package["schema_version"] == 3
    assert package["catalog_ids"] == [1, 3, 5, 7, 9]
    assert set(package["strata"]) == {"extract", "segment", "summary", "entity", "org"}
    assert package["org_event_resets"] == [{"catalog_id": 9, "event_id": 90}]
    assert package["expected_phase_coverage"]["entity"] == 1
    assert package["extract_source_sha256"] == {"1": hashlib.sha256(b"selected source").hexdigest()}
    assert "people_reset_names" not in package


def test_build_manifest_package_rejects_empty_extract_source(tmp_path: Path):
    @contextmanager
    def fake_db_session():
        yield object()

    empty_source = tmp_path / "empty.pdf"
    empty_source.write_bytes(b"")

    with pytest.raises(ValueError, match="empty extract source"):
        profile_manifest_builder.build_manifest_package(
            "baseline_empty_source",
            quotas={"extract": 1, "segment": 0, "summary": 0, "entity": 0, "org": 0},
            session_factory=fake_db_session,
            candidate_loaders={
                "extract": lambda session: [{"catalog_id": 1, "source_location": str(empty_source)}],
                "segment": lambda session: [],
                "summary": lambda session: [],
                "entity": lambda session: [],
                "org": lambda session: [],
            },
            generated_at_factory=lambda: "2026-08-09T00:00:00+00:00",
        )


def test_extract_candidates_require_fresh_single_agenda_document(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    source_path = tmp_path / "agenda.pdf"

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo")
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        catalog = Catalog(
            url_hash="extract-candidate",
            location=str(source_path),
            content="extracted agenda",
            content_hash=compute_content_hash("extracted agenda"),
            extraction_status="complete",
        )
        pending_catalog = Catalog(url_hash="extract-pending", location=str(source_path))
        multi_document = Catalog(
            url_hash="extract-multi-document",
            location=str(source_path),
            content="multi-document agenda",
            content_hash=compute_content_hash("multi-document agenda"),
            extraction_status="complete",
        )
        stale_hash = Catalog(
            url_hash="extract-stale-hash",
            location=str(source_path),
            content="changed agenda",
            content_hash=compute_content_hash("old agenda"),
            extraction_status="complete",
        )
        session.add_all([catalog, pending_catalog, multi_document, stale_hash])
        session.flush()
        session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add(
            Document(catalog_id=pending_catalog.id, event_id=event.id, place_id=place.id, category="agenda")
        )
        session.add_all(
            [
                Document(catalog_id=multi_document.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=multi_document.id, event_id=event.id, place_id=place.id, category="minutes"),
                Document(catalog_id=stale_hash.id, event_id=event.id, place_id=place.id, category="agenda"),
            ]
        )
        catalog_id = catalog.id
        session.commit()

        candidates = profile_manifest_candidates.extract_candidates(session)

    assert candidates == [{"catalog_id": catalog_id, "source_location": str(source_path)}]
    engine.dispose()


def test_segment_candidates_require_fresh_completed_agenda_output():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo")
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        eligible = Catalog(
            url_hash="segment-eligible",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            agenda_segmentation_status="complete",
        )
        multi_document = Catalog(
            url_hash="segment-multi-document",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            agenda_segmentation_status="complete",
        )
        missing_page = Catalog(
            url_hash="segment-missing-page",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            agenda_segmentation_status="complete",
        )
        stale_hash = Catalog(
            url_hash="segment-stale-hash",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            agenda_segmentation_status="complete",
            agenda_items_hash="stale-hash",
        )
        stale_content_hash = Catalog(
            url_hash="segment-stale-content-hash",
            content="changed agenda text",
            content_hash=compute_content_hash("old agenda text"),
            agenda_segmentation_status="complete",
        )
        no_items = Catalog(
            url_hash="segment-no-items",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            agenda_segmentation_status="complete",
            agenda_items_hash="orphaned-hash",
        )
        session.add_all([eligible, multi_document, missing_page, stale_hash, stale_content_hash, no_items])
        session.flush()
        session.add(Document(catalog_id=eligible.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add_all(
            [
                Document(catalog_id=multi_document.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=multi_document.id, event_id=event.id, place_id=place.id, category="minutes"),
                Document(catalog_id=missing_page.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=stale_hash.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=stale_content_hash.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=no_items.id, event_id=event.id, place_id=place.id, category="agenda"),
            ]
        )
        eligible_item = AgendaItem(
            catalog_id=eligible.id,
            event_id=event.id,
            order=1,
            title="Eligible item",
            page_number=1,
        )
        missing_page_item = AgendaItem(
            catalog_id=missing_page.id,
            event_id=event.id,
            order=1,
            title="Missing page",
            page_number=None,
        )
        stale_hash_item = AgendaItem(
            catalog_id=stale_hash.id,
            event_id=event.id,
            order=1,
            title="Changed item",
            page_number=2,
        )
        stale_content_hash_item = AgendaItem(
            catalog_id=stale_content_hash.id,
            event_id=event.id,
            order=1,
            title="Stale content item",
            page_number=3,
        )
        session.add_all([eligible_item, missing_page_item, stale_hash_item, stale_content_hash_item])
        session.flush()
        eligible.agenda_items_hash = compute_agenda_items_hash([eligible_item])
        stale_content_hash.agenda_items_hash = compute_agenda_items_hash([stale_content_hash_item])
        eligible_id = eligible.id
        session.commit()

        candidates = profile_manifest_candidates.segment_reset_candidates(session)
        pending_ids = select_catalog_ids_for_agenda_segmentation(session)

    assert candidates == [{"catalog_id": eligible_id}]
    assert eligible_id not in pending_ids
    engine.dispose()


def test_summary_candidates_require_current_runtime_freshness_source():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo")
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        agenda_without_items = Catalog(url_hash="agenda-no-items", content="agenda", summary="summary")
        terminal_empty_agenda = Catalog(
            url_hash="agenda-empty",
            content="agenda",
            content_hash=compute_content_hash("agenda"),
            summary="summary",
            summary_source_hash=compute_content_hash("agenda"),
            agenda_segmentation_status="empty",
        )
        minutes_first = Catalog(
            url_hash="minutes-first",
            content="minutes",
            content_hash=compute_content_hash("minutes"),
            summary="summary",
            summary_source_hash=compute_content_hash("minutes"),
        )
        structured_agenda = Catalog(
            url_hash="agenda-structured",
            content="agenda items",
            content_hash=compute_content_hash("agenda items"),
            summary="summary",
            agenda_segmentation_status="complete",
        )
        stale_terminal = Catalog(
            url_hash="agenda-empty-stale",
            content="changed agenda",
            content_hash=compute_content_hash("changed agenda"),
            summary="summary",
            summary_source_hash=compute_content_hash("old agenda"),
            agenda_segmentation_status="empty",
        )
        stale_minutes = Catalog(
            url_hash="minutes-stale",
            content="changed minutes",
            content_hash=compute_content_hash("changed minutes"),
            summary="summary",
            summary_source_hash=compute_content_hash("old minutes"),
        )
        stale_content_hash = Catalog(
            url_hash="minutes-stale-content-hash",
            content="changed minutes",
            content_hash=compute_content_hash("old minutes"),
            summary="summary",
            summary_source_hash=compute_content_hash("old minutes"),
        )
        stale_empty_agenda_hash = Catalog(
            url_hash="agenda-empty-stale-agenda-hash",
            content="agenda",
            content_hash=compute_content_hash("agenda"),
            summary="summary",
            summary_source_hash=compute_content_hash("agenda"),
            agenda_items_hash="orphaned-agenda-hash",
            agenda_segmentation_status="empty",
        )
        stale_structured = Catalog(
            url_hash="agenda-structured-stale",
            content="agenda items",
            content_hash=compute_content_hash("agenda items"),
            summary="summary",
            agenda_items_hash="stale-agenda-hash",
            summary_source_hash="stale-agenda-hash",
            agenda_segmentation_status="complete",
        )
        empty_summary = Catalog(
            url_hash="minutes-empty-summary",
            content="minutes",
            content_hash=compute_content_hash("minutes"),
            summary="",
            summary_source_hash=compute_content_hash("minutes"),
        )
        session.add_all(
            [
                agenda_without_items,
                terminal_empty_agenda,
                minutes_first,
                structured_agenda,
                stale_terminal,
                stale_minutes,
                stale_content_hash,
                stale_empty_agenda_hash,
                stale_structured,
                empty_summary,
            ]
        )
        session.flush()
        session.add_all(
            [
                Document(
                    catalog_id=agenda_without_items.id,
                    event_id=event.id,
                    place_id=place.id,
                    category="agenda",
                ),
                Document(
                    catalog_id=terminal_empty_agenda.id,
                    event_id=event.id,
                    place_id=place.id,
                    category="agenda",
                ),
                Document(catalog_id=minutes_first.id, event_id=event.id, place_id=place.id, category="minutes"),
                Document(catalog_id=minutes_first.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=structured_agenda.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=stale_terminal.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=stale_minutes.id, event_id=event.id, place_id=place.id, category="minutes"),
                Document(catalog_id=stale_content_hash.id, event_id=event.id, place_id=place.id, category="minutes"),
                Document(
                    catalog_id=stale_empty_agenda_hash.id,
                    event_id=event.id,
                    place_id=place.id,
                    category="agenda",
                ),
                Document(catalog_id=stale_structured.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=empty_summary.id, event_id=event.id, place_id=place.id, category="minutes"),
            ]
        )
        structured_item = AgendaItem(
            catalog_id=structured_agenda.id,
            event_id=event.id,
            order=1,
            title="Current item",
            page_number=1,
        )
        stale_structured_item = AgendaItem(
            catalog_id=stale_structured.id,
            event_id=event.id,
            order=1,
            title="Changed item",
            page_number=1,
        )
        session.add_all([structured_item, stale_structured_item])
        session.flush()
        structured_agenda.agenda_items_hash = compute_agenda_items_hash([structured_item])
        structured_agenda.summary_source_hash = structured_agenda.agenda_items_hash
        expected_ids = [terminal_empty_agenda.id, minutes_first.id, structured_agenda.id]
        runtime_pending_ids = [stale_terminal.id, stale_minutes.id]
        stale_structured_id = stale_structured.id
        session.commit()

        candidates = profile_manifest_candidates.summary_reset_candidates(session)
        pending_ids = select_catalog_ids_for_summary_hydration(session)

    assert candidates == [{"catalog_id": catalog_id} for catalog_id in sorted(expected_ids)]
    assert not set(expected_ids) & set(pending_ids)
    assert set(runtime_pending_ids).issubset(pending_ids)
    assert stale_structured_id not in {candidate["catalog_id"] for candidate in candidates}
    engine.dispose()


def test_entity_candidates_require_fresh_completed_entities():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        fresh = Catalog(
            url_hash="entity-fresh",
            content="minutes",
            content_hash=compute_content_hash("minutes"),
            entities={"orgs": ["Demo Council"]},
            entities_source_hash=compute_content_hash("minutes"),
        )
        stale = Catalog(
            url_hash="entity-stale",
            content="minutes",
            content_hash=compute_content_hash("minutes"),
            entities={"orgs": ["Demo Council"]},
            entities_source_hash="old-hash",
        )
        stale_content_hash = Catalog(
            url_hash="entity-stale-content-hash",
            content="changed minutes",
            content_hash=compute_content_hash("old minutes"),
            entities={"orgs": ["Demo Council"]},
            entities_source_hash=compute_content_hash("old minutes"),
        )
        json_null = Catalog(
            url_hash="entity-json-null",
            content="minutes",
            content_hash="null-hash",
            entities=None,
            entities_source_hash="null-hash",
        )
        session.add_all([fresh, stale, stale_content_hash, json_null])
        session.flush()
        fresh_id = fresh.id
        session.commit()

        candidates = profile_manifest_candidates.entity_reset_candidates(session)

    assert candidates == [{"catalog_id": fresh_id}]
    engine.dispose()


def test_org_candidates_require_unique_current_runtime_assignment():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        places = [
            Place(
                name=f"Demo {index}",
                state="CA",
                ocd_division_id=f"ocd-division/country:us/state:ca/place:demo_{index}",
            )
            for index in range(4)
        ]
        session.add_all(places)
        session.flush()
        safe_org = Organization(name="City Council", place_id=places[0].id)
        mismatched_org = Organization(name="Planning Commission", place_id=places[1].id)
        duplicate_orgs = [
            Organization(name="City Council", place_id=places[2].id),
            Organization(name="City Council", place_id=places[2].id),
        ]
        multi_document_org = Organization(name="City Council", place_id=places[3].id)
        session.add_all([safe_org, mismatched_org, *duplicate_orgs, multi_document_org])
        session.flush()
        events = [
            Event(
                name=f"Meeting {index}",
                place_id=place.id,
                meeting_type="Regular City Council",
                organization_id=organization.id,
            )
            for index, (place, organization) in enumerate(
                zip(places, [safe_org, mismatched_org, duplicate_orgs[0], multi_document_org], strict=True)
            )
        ]
        session.add_all(events)
        session.flush()
        catalogs = [Catalog(url_hash=f"org-candidate-{index}") for index in range(5)]
        session.add_all(catalogs)
        session.flush()
        session.add_all(
            [
                Document(catalog_id=catalogs[index].id, event_id=event.id, place_id=event.place_id)
                for index, event in enumerate(events)
            ]
        )
        session.add(Document(catalog_id=catalogs[4].id, event_id=events[3].id, place_id=places[3].id))
        safe_catalog_id = catalogs[0].id
        safe_event_id = events[0].id
        session.commit()

        candidates = profile_manifest_candidates.org_reset_candidates(session)

    assert candidates == [{"catalog_id": safe_catalog_id, "event_id": safe_event_id}]
    engine.dispose()


def test_build_manifest_package_rejects_retired_phase_quota():
    with pytest.raises(ValueError, match="unsupported manifest phases: people"):
        profile_manifest.build_manifest_package("baseline_demo", quotas={"people": 1})


def test_apply_preconditioning_mutates_only_selected_rows():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo")
        session.add(place)
        session.flush()
        organization = Organization(name="City Council", place_id=place.id)
        session.add(organization)
        session.flush()
        segment_event = Event(name="Segment Meeting", place_id=place.id)
        summary_event = Event(name="Summary Meeting", place_id=place.id)
        entity_event = Event(name="Entity Meeting", place_id=place.id)
        org_event = Event(
            name="Organization Meeting",
            place_id=place.id,
            meeting_type="Regular City Council",
            organization_id=organization.id,
        )
        session.add_all([segment_event, summary_event, entity_event, org_event])
        session.flush()
        segment_catalog = Catalog(
            url_hash="segment-target",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            summary="preserved summary",
            agenda_segmentation_status="complete",
            agenda_segmentation_item_count=1,
            agenda_items_hash="segment-agenda-hash",
        )
        summary_catalog = Catalog(
            url_hash="summary-target",
            content="minutes text",
            content_hash=compute_content_hash("minutes text"),
            summary="existing summary",
            summary_source_hash=compute_content_hash("minutes text"),
            summary_extractive="preserved extractive summary",
            agenda_items_hash="preserved agenda hash",
        )
        entity_catalog = Catalog(
            url_hash="entity-target",
            content="minutes text",
            content_hash=compute_content_hash("minutes text"),
            entities={"orgs": ["Demo Council"]},
            entities_source_hash=compute_content_hash("minutes text"),
            related_ids=[1, 2],
        )
        org_catalog = Catalog(url_hash="org-target", content="agenda text")
        session.add_all([segment_catalog, summary_catalog, entity_catalog, org_catalog])
        session.flush()
        session.add_all(
            [
                Document(
                    catalog_id=segment_catalog.id,
                    event_id=segment_event.id,
                    place_id=place.id,
                    category="agenda",
                ),
                Document(
                    catalog_id=summary_catalog.id,
                    event_id=summary_event.id,
                    place_id=place.id,
                    category="minutes",
                ),
                Document(
                    catalog_id=entity_catalog.id,
                    event_id=entity_event.id,
                    place_id=place.id,
                    category="minutes",
                ),
                Document(
                    catalog_id=org_catalog.id,
                    event_id=org_event.id,
                    place_id=place.id,
                    category="agenda",
                ),
                AgendaItem(
                    catalog_id=segment_catalog.id,
                    event_id=segment_event.id,
                    order=1,
                    title="Item 1",
                    page_number=1,
                ),
            ]
        )
        session.flush()
        segment_items = session.query(AgendaItem).filter(AgendaItem.catalog_id == segment_catalog.id).all()
        segment_catalog.agenda_items_hash = compute_agenda_items_hash(segment_items)
        target_ids = [segment_catalog.id, summary_catalog.id, entity_catalog.id, org_catalog.id]
        segment_id, summary_id, entity_id, org_id = target_ids
        org_event_id = org_event.id
        session.commit()

    @contextmanager
    def fake_db_session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    package = {
        "schema_version": 3,
        "manifest_name": "demo",
        "catalog_ids": target_ids,
        "strata": {
            "extract": [],
            "segment": [segment_id],
            "summary": [summary_id],
            "entity": [entity_id],
            "org": [org_id],
        },
        "extract_source_sha256": {},
        "org_event_resets": [{"catalog_id": org_id, "event_id": org_event_id}],
        "expected_phase_coverage": {"extract": 0, "segment": 1, "summary": 1, "entity": 1, "org": 1},
        "safety": {"org_reset_requires_single_document_event": True},
    }

    original_db_session = profile_manifest.db_session
    profile_manifest.db_session = fake_db_session
    try:
        result = profile_manifest.apply_preconditioning(package)
    finally:
        profile_manifest.db_session = original_db_session

    assert result["applied"] == {
        "deleted_agenda_items": 1,
        "cleared_extract_catalogs": 0,
        "cleared_segment_catalogs": 1,
        "cleared_summary_catalogs": 1,
        "cleared_entity_catalogs": 1,
        "cleared_org_events": 1,
    }

    with Session() as verify:
        refreshed_segment = verify.get(Catalog, segment_id)
        refreshed_summary = verify.get(Catalog, summary_id)
        refreshed_entity = verify.get(Catalog, entity_id)
        refreshed_event = verify.get(Event, org_event_id)
        assert refreshed_segment.agenda_segmentation_status is None
        assert refreshed_segment.agenda_items_hash is None
        assert refreshed_segment.summary == "preserved summary"
        assert refreshed_summary.summary is None
        assert refreshed_summary.summary_source_hash is None
        assert refreshed_summary.summary_extractive == "preserved extractive summary"
        assert refreshed_summary.agenda_items_hash == "preserved agenda hash"
        assert refreshed_entity.entities is None
        assert refreshed_entity.entities_source_hash is None
        assert refreshed_entity.related_ids == [1, 2]
        assert refreshed_event.organization_id is None
        assert verify.query(AgendaItem).count() == 0
    engine.dispose()


@pytest.mark.parametrize("source_bytes", [b"archived source"])
def test_extract_preconditioning_restores_replayable_catalog_and_preserves_source_records(
    tmp_path: Path,
    source_bytes: bytes,
):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    source_path = tmp_path / "agenda.pdf"
    source_path.write_bytes(source_bytes)

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo")
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id, organization_id=77)
        session.add(event)
        session.flush()
        target = Catalog(
            url="https://example.test/agenda.pdf",
            url_hash="extract-target",
            location=str(source_path),
            filename="agenda.pdf",
            content="extracted agenda",
            content_hash=compute_content_hash("extracted agenda"),
            extraction_status="complete",
            extraction_attempted_at=datetime.now(tz=UTC),
            extraction_attempt_count=2,
            extraction_error="old error",
            summary="summary",
            summary_source_hash="summary-hash",
            summary_extractive="extractive summary",
            agenda_items_hash="agenda-hash",
            entities={"orgs": ["Demo Council"]},
            entities_source_hash="entity-hash",
            tables=[{"rows": 1}],
            topics=["budget"],
            topics_source_hash="topic-hash",
            related_ids=[91, 92],
            lineage_id="lineage-1",
            lineage_confidence=0.8,
            lineage_updated_at=datetime.now(tz=UTC),
            agenda_segmentation_status="complete",
            agenda_segmentation_attempted_at=datetime.now(tz=UTC),
            agenda_segmentation_item_count=1,
            agenda_segmentation_error="old segmentation error",
            processed=True,
        )
        control = Catalog(url_hash="control", content="control content", location=str(source_path))
        session.add_all([target, control])
        session.flush()
        session.add(Document(catalog_id=target.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add(AgendaItem(catalog_id=target.id, event_id=event.id, order=1, title="Item 1"))
        target_id = target.id
        control_id = control.id
        event_id = event.id
        session.commit()

    preconditioning = apply_preconditioning(
        _extract_reset_package([target_id], {target_id: hashlib.sha256(source_bytes).hexdigest()}),
        dry_run=False,
        session_factory=Session,
    )

    assert preconditioning["applied"] == {
        "deleted_agenda_items": 1,
        "cleared_extract_catalogs": 1,
        "cleared_segment_catalogs": 1,
        "cleared_summary_catalogs": 0,
        "cleared_entity_catalogs": 0,
        "cleared_org_events": 0,
    }
    assert preconditioning["report"]["reset_actions"]["segment_catalogs"] == 1
    with Session() as session:
        replayable_catalog = session.get(Catalog, target_id)
        assert replayable_catalog is not None
        assert replayable_catalog.content is None
        assert replayable_catalog.content_hash is None
        assert replayable_catalog.extraction_status is None
        assert replayable_catalog.extraction_attempted_at is None
        assert replayable_catalog.extraction_attempt_count is None
        assert replayable_catalog.extraction_error is None
        assert replayable_catalog.summary == "summary"
        assert replayable_catalog.summary_source_hash == "summary-hash"
        assert replayable_catalog.summary_extractive == "extractive summary"
        assert replayable_catalog.agenda_items_hash is None
        assert replayable_catalog.entities == {"orgs": ["Demo Council"]}
        assert replayable_catalog.entities_source_hash == "entity-hash"
        assert replayable_catalog.tables == [{"rows": 1}]
        assert replayable_catalog.topics == ["budget"]
        assert replayable_catalog.topics_source_hash == "topic-hash"
        assert replayable_catalog.agenda_segmentation_status is None
        assert replayable_catalog.agenda_segmentation_attempted_at is None
        assert replayable_catalog.agenda_segmentation_item_count is None
        assert replayable_catalog.agenda_segmentation_error is None
        assert replayable_catalog.related_ids == [91, 92]
        assert replayable_catalog.lineage_id == "lineage-1"
        assert replayable_catalog.lineage_confidence == 0.8
        assert replayable_catalog.lineage_updated_at is not None
        assert replayable_catalog.processed is True
        assert replayable_catalog.url == "https://example.test/agenda.pdf"
        assert replayable_catalog.location == str(source_path)
        assert replayable_catalog.filename == "agenda.pdf"
        assert session.get(Document, replayable_catalog.document.id) is not None
        assert session.get(Event, event_id).organization_id == 77
        assert session.get(Catalog, control_id).content == "control content"
        assert session.query(AgendaItem).count() == 0

    engine.dispose()


@pytest.mark.parametrize(
    "invalid_source",
    ["missing_catalog", "null_location", "missing_path", "directory", "empty_file", "modified_bytes"],
)
def test_extract_preconditioning_rejects_invalid_sources_before_mutation(tmp_path: Path, invalid_source: str):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    valid_source = tmp_path / "valid.pdf"
    valid_source.write_bytes(b"valid source")

    with Session() as session:
        place = Place(
            name=f"Demo {invalid_source}",
            state="CA",
            ocd_division_id=f"ocd-division/country:us/state:ca/place:demo_{invalid_source}",
        )
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        valid_target = Catalog(
            url_hash="valid-target",
            location=str(valid_source),
            content="keep valid content",
            content_hash=compute_content_hash("keep valid content"),
            extraction_status="complete",
        )
        session.add(valid_target)
        session.flush()
        session.add(
            Document(catalog_id=valid_target.id, event_id=event.id, place_id=place.id, category="agenda")
        )
        session.add(AgendaItem(catalog_id=valid_target.id, event_id=event.id, order=1, title="Keep this item"))
        valid_target_id = valid_target.id
        if invalid_source == "missing_catalog":
            invalid_target_id = valid_target_id + 1000
        else:
            modified_source = tmp_path / "modified.pdf"
            if invalid_source == "modified_bytes":
                modified_source.write_bytes(b"before")
            if invalid_source == "empty_file":
                modified_source.write_bytes(b"")
            invalid_location = {
                "null_location": None,
                "missing_path": str(tmp_path / "missing.pdf"),
                "directory": str(tmp_path),
                "empty_file": str(modified_source),
                "modified_bytes": str(modified_source),
            }[invalid_source]
            invalid_target = Catalog(
                url_hash=f"invalid-{invalid_source}",
                location=invalid_location,
                content="keep invalid content",
                content_hash=compute_content_hash("keep invalid content"),
                extraction_status="complete",
            )
            session.add(invalid_target)
            session.flush()
            session.add(
                Document(catalog_id=invalid_target.id, event_id=event.id, place_id=place.id, category="agenda")
            )
            invalid_target_id = invalid_target.id
        session.commit()

    invalid_source_digest = "0" * 64
    if invalid_source == "modified_bytes":
        invalid_source_digest = hashlib.sha256(b"before").hexdigest()
    elif invalid_source == "empty_file":
        invalid_source_digest = hashlib.sha256(b"").hexdigest()
    source_digests = {
        valid_target_id: hashlib.sha256(b"valid source").hexdigest(),
        invalid_target_id: invalid_source_digest,
    }
    if invalid_source == "modified_bytes":
        modified_source.write_bytes(b"after!")

    with pytest.raises(ValueError, match="extract replay"):
        apply_preconditioning(
            _extract_reset_package([valid_target_id, invalid_target_id], source_digests),
            dry_run=False,
            session_factory=Session,
        )

    with Session() as session:
        valid_target = session.get(Catalog, valid_target_id)
        assert valid_target.content == "keep valid content"
        assert valid_target.extraction_status == "complete"
        assert session.query(AgendaItem).filter(AgendaItem.catalog_id == valid_target_id).count() == 1
        if invalid_source != "missing_catalog":
            invalid_target = session.get(Catalog, invalid_target_id)
            assert invalid_target.content == "keep invalid content"
            assert invalid_target.extraction_status == "complete"

    engine.dispose()


def test_extract_preconditioning_dry_run_rejects_modified_source_bytes(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    source_path = tmp_path / "agenda.pdf"
    source_path.write_bytes(b"before")

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo_dry")
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        catalog = Catalog(
            url_hash="dry-run-target",
            location=str(source_path),
            content="keep content",
            content_hash=compute_content_hash("keep content"),
            extraction_status="complete",
        )
        session.add(catalog)
        session.flush()
        session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
        catalog_id = catalog.id
        session.commit()

    package = _extract_reset_package([catalog_id], {catalog_id: hashlib.sha256(b"before").hexdigest()})
    source_path.write_bytes(b"after!")

    with pytest.raises(ValueError, match="digest mismatch"):
        apply_preconditioning(package, dry_run=True, session_factory=Session)

    with Session() as session:
        assert session.get(Catalog, catalog_id).content == "keep content"

    engine.dispose()


def test_preconditioning_dry_run_simulates_hash_normalization_without_persisting() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(
            name="Demo",
            state="CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:dry_run_hashes",
        )
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        catalog = Catalog(
            url_hash="dry-run-hash-normalization",
            content="minutes text",
            summary="existing summary",
        )
        agenda_catalog = Catalog(
            url_hash="dry-run-agenda-hash-normalization",
            content="agenda text",
            agenda_segmentation_status="complete",
        )
        session.add_all([catalog, agenda_catalog])
        session.flush()
        session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="minutes"))
        session.add(Document(catalog_id=agenda_catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add(
            AgendaItem(
                catalog_id=agenda_catalog.id,
                event_id=event.id,
                order=1,
                title="Current item",
                page_number=1,
            )
        )
        catalog_id = catalog.id
        agenda_catalog_id = agenda_catalog.id
        session.commit()

    package = {
        "schema_version": 3,
        "manifest_name": "dry_run_hash_normalization",
        "catalog_ids": [catalog_id, agenda_catalog_id],
        "strata": {
            "extract": [],
            "segment": [agenda_catalog_id],
            "summary": [catalog_id],
            "entity": [],
            "org": [],
        },
        "extract_source_sha256": {},
        "org_event_resets": [],
        "expected_phase_coverage": {"extract": 0, "segment": 1, "summary": 1, "entity": 0, "org": 0},
        "safety": {"org_reset_requires_single_document_event": True},
    }

    preconditioning = apply_preconditioning(package, dry_run=True, session_factory=Session)

    assert preconditioning["dry_run"] is True
    with Session() as session:
        unchanged_catalog = session.get(Catalog, catalog_id)
        assert unchanged_catalog.content_hash is None
        assert unchanged_catalog.summary_source_hash is None
        unchanged_agenda_catalog = session.get(Catalog, agenda_catalog_id)
        assert unchanged_agenda_catalog.content_hash is None
        assert unchanged_agenda_catalog.agenda_items_hash is None

    engine.dispose()


def test_preconditioning_dry_run_rejects_explicit_stale_agenda_hash() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(
            name="Demo",
            state="CA",
            ocd_division_id="ocd-division/country:us/state:ca/place:stale_agenda_hash",
        )
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        catalog = Catalog(
            url_hash="dry-run-stale-agenda-hash",
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            agenda_segmentation_status="complete",
            agenda_items_hash="explicit-stale-agenda-hash",
        )
        session.add(catalog)
        session.flush()
        session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add(AgendaItem(catalog_id=catalog.id, event_id=event.id, order=1, title="Current item", page_number=1))
        catalog_id = catalog.id
        session.commit()

    package = {
        "schema_version": 3,
        "manifest_name": "dry_run_stale_agenda_hash",
        "catalog_ids": [catalog_id],
        "strata": {"extract": [], "segment": [catalog_id], "summary": [], "entity": [], "org": []},
        "extract_source_sha256": {},
        "org_event_resets": [],
        "expected_phase_coverage": {"extract": 0, "segment": 1, "summary": 0, "entity": 0, "org": 0},
        "safety": {"org_reset_requires_single_document_event": True},
    }

    with pytest.raises(ValueError, match="segment replay targets are no longer eligible"):
        apply_preconditioning(package, dry_run=True, session_factory=Session)

    with Session() as session:
        assert session.get(Catalog, catalog_id).agenda_items_hash == "explicit-stale-agenda-hash"

    engine.dispose()


@pytest.mark.parametrize(
    ("case_name", "phase", "catalog_fields", "empty_hash_field"),
    [
        (
            "content",
            "summary",
            {
                "content_hash": "",
                "summary": "existing summary",
                "summary_source_hash": compute_content_hash("minutes text"),
            },
            "content_hash",
        ),
        (
            "summary_source",
            "summary",
            {
                "content_hash": compute_content_hash("minutes text"),
                "summary": "existing summary",
                "summary_source_hash": "",
            },
            "summary_source_hash",
        ),
        (
            "entity_source",
            "entity",
            {
                "content_hash": compute_content_hash("minutes text"),
                "entities": {"orgs": ["Demo Council"]},
                "entities_source_hash": "",
            },
            "entities_source_hash",
        ),
    ],
)
def test_preconditioning_dry_run_rejects_explicit_empty_hashes(
    case_name: str,
    phase: str,
    catalog_fields: dict[str, object],
    empty_hash_field: str,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        place = Place(
            name="Demo",
            state="CA",
            ocd_division_id=f"ocd-division/country:us/state:ca/place:empty_{case_name}_hash",
        )
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        catalog = Catalog(
            url_hash=f"dry-run-empty-{case_name}-hash",
            content="minutes text",
            **catalog_fields,
        )
        session.add(catalog)
        session.flush()
        session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="minutes"))
        catalog_id = catalog.id
        session.commit()

    strata = {"extract": [], "segment": [], "summary": [], "entity": [], "org": []}
    strata[phase] = [catalog_id]
    package = {
        "schema_version": 3,
        "manifest_name": f"dry_run_empty_{case_name}_hash",
        "catalog_ids": [catalog_id],
        "strata": strata,
        "extract_source_sha256": {},
        "org_event_resets": [],
        "expected_phase_coverage": {key: len(catalog_ids) for key, catalog_ids in strata.items()},
        "safety": {"org_reset_requires_single_document_event": True},
    }

    with pytest.raises(ValueError, match=f"{phase} replay targets are no longer eligible"):
        apply_preconditioning(package, dry_run=True, session_factory=Session)

    with Session() as session:
        assert getattr(session.get(Catalog, catalog_id), empty_hash_field) == ""

    engine.dispose()


def test_preconditioning_validates_all_targets_before_first_mutation(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    source_path = tmp_path / "agenda.pdf"
    source_path.write_bytes(b"archived source")

    with Session() as session:
        place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:all_targets")
        session.add(place)
        session.flush()
        event = Event(name="Meeting", place_id=place.id)
        session.add(event)
        session.flush()
        extract_target = Catalog(
            url_hash="extract-target",
            location=str(source_path),
            content="agenda text",
            content_hash=compute_content_hash("agenda text"),
            extraction_status="complete",
        )
        stale_entity_target = Catalog(
            url_hash="stale-entity-target",
            content="minutes text",
            content_hash="new-hash",
            entities={"orgs": ["Demo Council"]},
            entities_source_hash="old-hash",
        )
        session.add_all([extract_target, stale_entity_target])
        session.flush()
        session.add(
            Document(catalog_id=extract_target.id, event_id=event.id, place_id=place.id, category="agenda")
        )
        extract_id = extract_target.id
        entity_id = stale_entity_target.id
        session.commit()

    package = {
        "schema_version": 3,
        "manifest_name": "all-target-validation",
        "catalog_ids": [extract_id, entity_id],
        "strata": {"extract": [extract_id], "segment": [], "summary": [], "entity": [entity_id], "org": []},
        "extract_source_sha256": {str(extract_id): hashlib.sha256(b"archived source").hexdigest()},
        "org_event_resets": [],
        "expected_phase_coverage": {"extract": 1, "segment": 0, "summary": 0, "entity": 1, "org": 0},
        "safety": {"org_reset_requires_single_document_event": True},
    }

    with pytest.raises(ValueError, match="entity replay target"):
        apply_preconditioning(package, dry_run=False, session_factory=Session)

    with Session() as session:
        preserved_extract = session.get(Catalog, extract_id)
        assert preserved_extract.content == "agenda text"
        assert preserved_extract.extraction_status == "complete"

    engine.dispose()


def test_build_profile_manifest_script_writes_schema_v3_package(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("build_profile_manifest", Path("scripts/build_profile_manifest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    package = {
        "schema_version": 3,
        "manifest_name": "baseline_demo",
        "catalog_ids": [11, 12],
        "phase_candidates": {"extract": 10, "segment": 10, "summary": 10, "entity": 10, "org": 10},
        "strata": {"extract": [11], "segment": [12], "summary": [], "entity": [], "org": []},
        "extract_source_sha256": {"11": "a" * 64},
        "expected_phase_coverage": {"extract": 1, "segment": 1, "summary": 0, "entity": 0, "org": 0},
    }

    mod._build_manifest_package_via_docker = lambda name, quotas: package
    exit_code = mod.main(["--name", "baseline_demo", "--output-dir", str(tmp_path), "--write"])

    assert exit_code == 0
    assert (tmp_path / "baseline_demo.txt").read_text(encoding="utf-8") == "11\n12\n"
    written_sidecar = json.loads((tmp_path / "baseline_demo.json").read_text(encoding="utf-8"))
    assert written_sidecar["schema_version"] == 3


def test_build_profile_manifest_cli_rejects_people_quota():
    spec = importlib.util.spec_from_file_location("build_profile_manifest", Path("scripts/build_profile_manifest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(SystemExit):
        mod.parse_args(["--name", "baseline_demo", "--people-quota", "4"])


@pytest.mark.parametrize("old_schema_version", [1, 2])
def test_validate_manifest_package_rejects_old_schema_versions(old_schema_version: int):
    package = {"schema_version": old_schema_version, "catalog_ids": [1, 2]}

    with pytest.raises(ValueError, match="unsupported manifest package schema_version"):
        profile_manifest.validate_manifest_package([1, 2], package)


def test_validate_manifest_package_rejects_mismatched_ids():
    package = {"schema_version": 3, "catalog_ids": [1, 3]}

    with pytest.raises(ValueError, match="do not match"):
        profile_manifest.validate_manifest_package([1, 2], package)


def test_validate_manifest_package_accepts_exact_schema_v3_partition():
    package = _valid_manifest_package()

    profile_manifest.validate_manifest_package([1, 2, 3, 4, 5], package)


@pytest.mark.parametrize("invalid_catalog_id", [True, "1", 1.0, None])
def test_validate_manifest_package_rejects_noninteger_json_ids(invalid_catalog_id: object):
    package = _valid_manifest_package()
    package["catalog_ids"] = [invalid_catalog_id, 2, 3, 4, 5]

    with pytest.raises(ValueError, match="catalog_ids must contain JSON integers"):
        profile_manifest.validate_manifest_package([1, 2, 3, 4, 5], package)


def test_validate_manifest_package_rejects_duplicate_workload_ids():
    package = _valid_manifest_package()
    package["catalog_ids"] = [1, 1, 2, 3, 4, 5]

    with pytest.raises(ValueError, match="catalog_ids must be unique"):
        profile_manifest.validate_manifest_package([1, 1, 2, 3, 4, 5], package)


@pytest.mark.parametrize("partition_defect", ["missing_phase", "overlap", "incomplete"])
def test_validate_manifest_package_rejects_invalid_strata_partition(partition_defect: str):
    package = _valid_manifest_package()
    strata = deepcopy(package["strata"])
    if partition_defect == "missing_phase":
        del strata["org"]
    elif partition_defect == "overlap":
        strata["summary"] = [2, 3]
    else:
        strata["summary"] = []
    package["strata"] = strata

    with pytest.raises(ValueError, match="strata"):
        profile_manifest.validate_manifest_package([1, 2, 3, 4, 5], package)


def test_validate_manifest_package_rejects_inaccurate_phase_coverage():
    package = _valid_manifest_package()
    package["expected_phase_coverage"] = {
        "extract": 1,
        "segment": 1,
        "summary": 0,
        "entity": 1,
        "org": 1,
    }

    with pytest.raises(ValueError, match="expected_phase_coverage"):
        profile_manifest.validate_manifest_package([1, 2, 3, 4, 5], package)


@pytest.mark.parametrize("invalid_coverage", [True, 1.0])
def test_validate_manifest_package_rejects_noninteger_phase_coverage(invalid_coverage: object):
    package = _valid_manifest_package()
    package["expected_phase_coverage"] = {
        "extract": invalid_coverage,
        "segment": 1,
        "summary": 1,
        "entity": 1,
        "org": 1,
    }

    with pytest.raises(ValueError, match="expected_phase_coverage values must be JSON integers"):
        profile_manifest.validate_manifest_package([1, 2, 3, 4, 5], package)


def test_validate_manifest_package_requires_safety_declaration_without_org_targets():
    package = _valid_manifest_package()
    package["catalog_ids"] = [1, 2, 3, 4]
    package["strata"] = {"extract": [1], "segment": [2], "summary": [3], "entity": [4], "org": []}
    package["org_event_resets"] = []
    package["expected_phase_coverage"] = {"extract": 1, "segment": 1, "summary": 1, "entity": 1, "org": 0}
    del package["safety"]

    with pytest.raises(ValueError, match="org reset safety"):
        profile_manifest.validate_manifest_package([1, 2, 3, 4], package)


@pytest.mark.parametrize("org_defect", ["missing_mapping", "duplicate_event", "unsafe"])
def test_validate_manifest_package_rejects_invalid_org_reset_contract(org_defect: str):
    package = _valid_manifest_package()
    if org_defect == "missing_mapping":
        package["org_event_resets"] = []
    elif org_defect == "duplicate_event":
        package["org_event_resets"] = [
            {"catalog_id": 5, "event_id": 50},
            {"catalog_id": 5, "event_id": 50},
        ]
    else:
        package["safety"] = {"org_reset_requires_single_document_event": False}

    with pytest.raises(ValueError, match="org"):
        profile_manifest.validate_manifest_package([1, 2, 3, 4, 5], package)


@pytest.mark.parametrize("phase", ["extract", "segment", "summary", "entity", "org"])
def test_validate_manifest_package_rejects_stratum_ids_outside_workload(phase: str):
    strata = {name: [] for name in ("extract", "segment", "summary", "entity", "org")}
    strata[phase] = [2]
    package = {
        "schema_version": 3,
        "catalog_ids": [1],
        "strata": strata,
        "extract_source_sha256": {"2": "a" * 64} if phase == "extract" else {},
    }

    with pytest.raises(ValueError, match="strata contain catalog_ids outside manifest workload"):
        profile_manifest.validate_manifest_package([1], package)


@pytest.mark.parametrize(
    "source_digests",
    [
        {},
        {"1": "a" * 64, "2": "b" * 64},
        {"1": "A" * 64},
        {"1": "not-a-sha256"},
    ],
)
def test_validate_manifest_package_rejects_invalid_extract_source_digests(source_digests: dict[str, str]):
    package = {
        "schema_version": 3,
        "catalog_ids": [1],
        "strata": {"extract": [1], "segment": [], "summary": [], "entity": [], "org": []},
        "extract_source_sha256": source_digests,
    }

    with pytest.raises(ValueError, match="extract_source_sha256"):
        profile_manifest.validate_manifest_package([1], package)


def test_baseline_v1_is_immutable_and_v2_uses_its_own_workload_contract():
    assert hashlib.sha256(V1_JSON_PATH.read_bytes()).hexdigest() == V1_JSON_SHA256
    assert hashlib.sha256(V1_TEXT_PATH.read_bytes()).hexdigest() == V1_TEXT_SHA256

    v1_ids = [int(value) for value in V1_TEXT_PATH.read_text(encoding="utf-8").splitlines()]
    v2_ids = [int(value) for value in V2_TEXT_PATH.read_text(encoding="utf-8").splitlines()]
    v2_package = json.loads(V2_JSON_PATH.read_text(encoding="utf-8"))
    v2_strata = v2_package["strata"]

    assert len(v2_ids) == 30
    assert len(set(v2_ids)) == 30
    assert set(v2_ids) != set(v1_ids)
    assert v2_package["schema_version"] == 3
    assert v2_package["catalog_ids"] == v2_ids
    assert v2_package["phase_quotas"] == {"extract": 8, "segment": 6, "summary": 6, "entity": 8, "org": 2}
    assert {phase: len(catalog_ids) for phase, catalog_ids in v2_strata.items()} == v2_package[
        "phase_quotas"
    ]
    assert set().union(*(set(catalog_ids) for catalog_ids in v2_strata.values())) == set(v2_ids)
    assert v2_package["phase_candidates"]["extract"] == 8
    assert v2_package["expected_phase_coverage"] == v2_package["phase_quotas"]
    assert set(v2_package["extract_source_sha256"]) == {str(catalog_id) for catalog_id in v2_strata["extract"]}
    assert all(
        len(source_digest) == 64 and source_digest == source_digest.lower()
        for source_digest in v2_package["extract_source_sha256"].values()
    )
    assert v2_package["safety"]["org_reset_requires_single_document_event"] is True
    assert [reset["catalog_id"] for reset in v2_package["org_event_resets"]] == v2_strata["org"]
    assert len({reset["event_id"] for reset in v2_package["org_event_resets"]}) == 2
    assert "people" not in v2_strata
    assert "people" not in v2_package["expected_phase_coverage"]
    assert "people_reset_names" not in v2_package

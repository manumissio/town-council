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
from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place
from pipeline.profile_manifest_preconditioning import apply_preconditioning


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


def test_extract_candidates_include_archived_source_location(tmp_path: Path):
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
            extraction_status="complete",
        )
        pending_catalog = Catalog(url_hash="extract-pending", location=str(source_path))
        session.add_all([catalog, pending_catalog])
        session.flush()
        session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add(
            Document(catalog_id=pending_catalog.id, event_id=event.id, place_id=place.id, category="agenda")
        )
        catalog_id = catalog.id
        session.commit()

        candidates = profile_manifest_candidates.extract_candidates(session)

    assert candidates == [{"catalog_id": catalog_id, "source_location": str(source_path)}]
    engine.dispose()


def test_segment_candidates_require_one_completed_agenda_document():
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
            agenda_segmentation_status="complete",
        )
        multi_document = Catalog(
            url_hash="segment-multi-document",
            content="agenda text",
            agenda_segmentation_status="complete",
        )
        session.add_all([eligible, multi_document])
        session.flush()
        session.add(Document(catalog_id=eligible.id, event_id=event.id, place_id=place.id, category="agenda"))
        session.add_all(
            [
                Document(catalog_id=multi_document.id, event_id=event.id, place_id=place.id, category="agenda"),
                Document(catalog_id=multi_document.id, event_id=event.id, place_id=place.id, category="minutes"),
            ]
        )
        eligible_id = eligible.id
        session.commit()

        candidates = profile_manifest_candidates.segment_reset_candidates(session)

    assert candidates == [{"catalog_id": eligible_id}]
    engine.dispose()


def test_summary_candidates_use_first_document_kind_and_terminal_empty_agendas():
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
            summary="summary",
            agenda_segmentation_status="empty",
        )
        minutes_first = Catalog(url_hash="minutes-first", content="minutes", summary="summary")
        session.add_all([agenda_without_items, terminal_empty_agenda, minutes_first])
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
            ]
        )
        expected_ids = [terminal_empty_agenda.id, minutes_first.id]
        session.commit()

        candidates = profile_manifest_candidates.summary_reset_candidates(session)

    assert candidates == [{"catalog_id": catalog_id} for catalog_id in sorted(expected_ids)]
    engine.dispose()


def test_entity_candidates_require_fresh_completed_entities():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        fresh = Catalog(
            url_hash="entity-fresh",
            content="minutes",
            content_hash="fresh-hash",
            entities={"orgs": ["Demo Council"]},
            entities_source_hash="fresh-hash",
        )
        stale = Catalog(
            url_hash="entity-stale",
            content="minutes",
            content_hash="new-hash",
            entities={"orgs": ["Demo Council"]},
            entities_source_hash="old-hash",
        )
        json_null = Catalog(
            url_hash="entity-json-null",
            content="minutes",
            content_hash="null-hash",
            entities=None,
            entities_source_hash="null-hash",
        )
        session.add_all([fresh, stale, json_null])
        session.flush()
        fresh_id = fresh.id
        session.commit()

        candidates = profile_manifest_candidates.entity_reset_candidates(session)

    assert candidates == [{"catalog_id": fresh_id}]
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
        segment_event = Event(name="Segment Meeting", place_id=place.id)
        summary_event = Event(name="Summary Meeting", place_id=place.id)
        entity_event = Event(name="Entity Meeting", place_id=place.id)
        org_event = Event(name="Organization Meeting", place_id=place.id, organization_id=77)
        session.add_all([segment_event, summary_event, entity_event, org_event])
        session.flush()
        segment_catalog = Catalog(
            url_hash="segment-target",
            content="agenda text",
            summary="preserved summary",
            agenda_segmentation_status="complete",
            agenda_segmentation_item_count=1,
            agenda_items_hash="segment-agenda-hash",
        )
        summary_catalog = Catalog(
            url_hash="summary-target",
            content="minutes text",
            summary="existing summary",
            summary_source_hash="summary-hash",
            summary_extractive="preserved extractive summary",
            agenda_items_hash="preserved agenda hash",
        )
        entity_catalog = Catalog(
            url_hash="entity-target",
            content="minutes text",
            content_hash="entity-hash",
            entities={"orgs": ["Demo Council"]},
            entities_source_hash="entity-hash",
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
                AgendaItem(catalog_id=segment_catalog.id, event_id=segment_event.id, order=1, title="Item 1"),
            ]
        )
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


@pytest.mark.parametrize("source_bytes", [b"archived source", b""])
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
            content_hash="content-hash",
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
        "deleted_agenda_items": 0,
        "cleared_extract_catalogs": 1,
        "cleared_segment_catalogs": 0,
        "cleared_summary_catalogs": 0,
        "cleared_entity_catalogs": 0,
        "cleared_org_events": 0,
    }
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
        assert replayable_catalog.agenda_items_hash == "agenda-hash"
        assert replayable_catalog.entities == {"orgs": ["Demo Council"]}
        assert replayable_catalog.entities_source_hash == "entity-hash"
        assert replayable_catalog.tables == [{"rows": 1}]
        assert replayable_catalog.topics == ["budget"]
        assert replayable_catalog.topics_source_hash == "topic-hash"
        assert replayable_catalog.agenda_segmentation_status == "complete"
        assert replayable_catalog.agenda_segmentation_attempted_at is not None
        assert replayable_catalog.agenda_segmentation_item_count == 1
        assert replayable_catalog.agenda_segmentation_error == "old segmentation error"
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
        assert session.query(AgendaItem).count() == 1

    engine.dispose()


@pytest.mark.parametrize(
    "invalid_source",
    ["missing_catalog", "null_location", "missing_path", "directory", "modified_bytes"],
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
            invalid_location = {
                "null_location": None,
                "missing_path": str(tmp_path / "missing.pdf"),
                "directory": str(tmp_path),
                "modified_bytes": str(modified_source),
            }[invalid_source]
            invalid_target = Catalog(
                url_hash=f"invalid-{invalid_source}",
                location=invalid_location,
                content="keep invalid content",
                extraction_status="complete",
            )
            session.add(invalid_target)
            session.flush()
            session.add(
                Document(catalog_id=invalid_target.id, event_id=event.id, place_id=place.id, category="agenda")
            )
            invalid_target_id = invalid_target.id
        session.commit()

    source_digests = {
        valid_target_id: hashlib.sha256(b"valid source").hexdigest(),
        invalid_target_id: hashlib.sha256(b"before").hexdigest() if invalid_source == "modified_bytes" else "0" * 64,
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

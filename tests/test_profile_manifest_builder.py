from contextlib import contextmanager
import ast
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline import profile_manifest
from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Place
from pipeline.profile_manifest_preconditioning import apply_preconditioning


V1_JSON_SHA256 = "862d8dd0b8297463d4f19f0ea2590183d5a78d9cf6477a530fd7dc73f445f16c"
V1_TEXT_SHA256 = "9867bea1aa140317d4a84ebb3670fbacd76b37bf163e4e66963e8d15cfcfa17b"
V1_JSON_PATH = Path("profiling/manifests/baseline_representative_v1.json")
V1_TEXT_PATH = Path("profiling/manifests/baseline_representative_v1.txt")
V2_JSON_PATH = Path("profiling/manifests/baseline_representative_v2.json")
V2_TEXT_PATH = Path("profiling/manifests/baseline_representative_v2.txt")


def _extract_reset_package(catalog_ids: list[int]) -> dict[str, object]:
    return {
        "schema_version": 2,
        "manifest_name": "extract_replay",
        "catalog_ids": catalog_ids,
        "strata": {"extract": catalog_ids, "segment": [], "summary": [], "entity": [], "org": []},
        "org_event_resets": [],
        "expected_phase_coverage": {"extract": len(catalog_ids), "segment": 0, "summary": 0, "entity": 0, "org": 0},
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
        "_extract_candidates",
        "_segment_reset_candidates",
        "_summary_reset_candidates",
        "_entity_reset_candidates",
        "_org_reset_candidates",
        "db_session",
        "AgendaItem",
        "Catalog",
        "Document",
        "Event",
        "select_catalog_ids_for_entity_backfill",
        "select_catalog_ids_for_processing",
    ]

    missing_names = [name for name in expected_names if not hasattr(profile_manifest, name)]

    assert missing_names == []
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


def test_build_manifest_package_honors_phase_quotas(monkeypatch):
    @contextmanager
    def fake_db_session():
        yield object()

    monkeypatch.setattr(profile_manifest, "db_session", fake_db_session)
    monkeypatch.setattr(profile_manifest, "_extract_candidates", lambda session: [{"catalog_id": 1}, {"catalog_id": 2}])
    monkeypatch.setattr(profile_manifest, "_segment_reset_candidates", lambda session: [{"catalog_id": 3}, {"catalog_id": 4}])
    monkeypatch.setattr(profile_manifest, "_summary_reset_candidates", lambda session: [{"catalog_id": 5}, {"catalog_id": 6}])
    monkeypatch.setattr(profile_manifest, "_entity_reset_candidates", lambda session: [{"catalog_id": 7}, {"catalog_id": 8}])
    monkeypatch.setattr(profile_manifest, "_org_reset_candidates", lambda session: [{"catalog_id": 9, "event_id": 90}])

    package = profile_manifest.build_manifest_package(
        "baseline_demo",
        quotas={"extract": 1, "segment": 1, "summary": 1, "entity": 1, "org": 1},
    )

    assert package["schema_version"] == 2
    assert package["catalog_ids"] == [1, 3, 5, 7, 9]
    assert set(package["strata"]) == {"extract", "segment", "summary", "entity", "org"}
    assert package["org_event_resets"] == [{"catalog_id": 9, "event_id": 90}]
    assert package["expected_phase_coverage"]["entity"] == 1
    assert "people_reset_names" not in package


def test_build_manifest_package_rejects_retired_phase_quota():
    with pytest.raises(ValueError, match="unsupported manifest phases: people"):
        profile_manifest.build_manifest_package("baseline_demo", quotas={"people": 1})


def test_apply_preconditioning_mutates_only_selected_rows():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    place = Place(name="Demo", state="CA", ocd_division_id="ocd-division/country:us/state:ca/place:demo")
    session.add(place)
    session.flush()
    event = Event(name="Meeting", place_id=place.id, organization_id=77)
    session.add(event)
    session.flush()
    catalog = Catalog(
        url_hash="demo-hash",
        content="agenda text",
        summary="existing summary",
        entities={"orgs": ["Demo Council"], "locs": []},
        agenda_segmentation_status="complete",
        agenda_segmentation_item_count=2,
        related_ids=[1, 2],
    )
    session.add(catalog)
    session.flush()
    session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
    session.add(AgendaItem(catalog_id=catalog.id, event_id=event.id, order=1, title="Item 1"))
    catalog_id = catalog.id
    event_id = event.id
    session.commit()
    session.close()

    @contextmanager
    def fake_db_session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    package = {
        "schema_version": 2,
        "manifest_name": "demo",
        "catalog_ids": [catalog_id],
        "strata": {
            "extract": [],
            "segment": [catalog_id],
            "summary": [],
            "entity": [catalog_id],
            "org": [catalog_id],
        },
        "org_event_resets": [{"catalog_id": catalog_id, "event_id": event_id}],
        "expected_phase_coverage": {"extract": 0, "segment": 1, "summary": 0, "entity": 1, "org": 1},
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
        "cleared_summary_catalogs": 0,
        "cleared_entity_catalogs": 1,
        "cleared_org_events": 1,
    }

    verify = Session()
    refreshed_catalog = verify.get(Catalog, catalog_id)
    refreshed_event = verify.get(Event, event_id)
    assert refreshed_catalog.summary is None
    assert refreshed_catalog.entities is None
    assert refreshed_catalog.agenda_segmentation_status is None
    assert refreshed_catalog.related_ids is None
    assert refreshed_event.organization_id is None
    assert verify.query(AgendaItem).count() == 0
    verify.close()
    engine.dispose()


def test_extract_preconditioning_restores_replayable_catalog_and_preserves_source_records(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    source_path = tmp_path / "agenda.pdf"
    source_path.write_bytes(b"archived source")

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
            extraction_status="success",
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
        _extract_reset_package([target_id]),
        dry_run=False,
        session_factory=Session,
    )

    assert preconditioning["applied"] == {
        "deleted_agenda_items": 1,
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
        assert replayable_catalog.summary is None
        assert replayable_catalog.summary_source_hash is None
        assert replayable_catalog.summary_extractive is None
        assert replayable_catalog.agenda_items_hash is None
        assert replayable_catalog.entities is None
        assert replayable_catalog.entities_source_hash is None
        assert replayable_catalog.tables is None
        assert replayable_catalog.topics is None
        assert replayable_catalog.topics_source_hash is None
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


@pytest.mark.parametrize("invalid_source", ["missing_catalog", "null_location", "missing_path", "directory"])
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
            extraction_status="success",
        )
        session.add(valid_target)
        session.flush()
        session.add(AgendaItem(catalog_id=valid_target.id, event_id=event.id, order=1, title="Keep this item"))
        valid_target_id = valid_target.id
        if invalid_source == "missing_catalog":
            invalid_target_id = valid_target_id + 1000
        else:
            invalid_location = {
                "null_location": None,
                "missing_path": str(tmp_path / "missing.pdf"),
                "directory": str(tmp_path),
            }[invalid_source]
            invalid_target = Catalog(
                url_hash=f"invalid-{invalid_source}",
                location=invalid_location,
                content="keep invalid content",
                extraction_status="success",
            )
            session.add(invalid_target)
            session.flush()
            invalid_target_id = invalid_target.id
        session.commit()

    with pytest.raises(ValueError, match="extract replay source"):
        apply_preconditioning(
            _extract_reset_package([valid_target_id, invalid_target_id]),
            dry_run=False,
            session_factory=Session,
        )

    with Session() as session:
        valid_target = session.get(Catalog, valid_target_id)
        assert valid_target.content == "keep valid content"
        assert valid_target.extraction_status == "success"
        assert session.query(AgendaItem).filter(AgendaItem.catalog_id == valid_target_id).count() == 1
        if invalid_source != "missing_catalog":
            invalid_target = session.get(Catalog, invalid_target_id)
            assert invalid_target.content == "keep invalid content"
            assert invalid_target.extraction_status == "success"

    engine.dispose()


def test_build_profile_manifest_script_writes_schema_v2_package(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("build_profile_manifest", Path("scripts/build_profile_manifest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    package = {
        "schema_version": 2,
        "manifest_name": "baseline_demo",
        "catalog_ids": [11, 12],
        "phase_candidates": {"extract": 10, "segment": 10, "summary": 10, "entity": 10, "org": 10},
        "strata": {"extract": [11], "segment": [12], "summary": [], "entity": [], "org": []},
        "expected_phase_coverage": {"extract": 1, "segment": 1, "summary": 0, "entity": 0, "org": 0},
    }

    mod._build_manifest_package_via_docker = lambda name, quotas: package
    exit_code = mod.main(["--name", "baseline_demo", "--output-dir", str(tmp_path), "--write"])

    assert exit_code == 0
    assert (tmp_path / "baseline_demo.txt").read_text(encoding="utf-8") == "11\n12\n"
    written_sidecar = json.loads((tmp_path / "baseline_demo.json").read_text(encoding="utf-8"))
    assert written_sidecar["schema_version"] == 2


def test_build_profile_manifest_cli_rejects_people_quota():
    spec = importlib.util.spec_from_file_location("build_profile_manifest", Path("scripts/build_profile_manifest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(SystemExit):
        mod.parse_args(["--name", "baseline_demo", "--people-quota", "4"])


def test_validate_manifest_package_rejects_schema_v1():
    package = {"schema_version": 1, "catalog_ids": [1, 2]}

    with pytest.raises(ValueError, match="unsupported manifest package schema_version"):
        profile_manifest.validate_manifest_package([1, 2], package)


def test_validate_manifest_package_rejects_mismatched_ids():
    package = {"schema_version": 2, "catalog_ids": [1, 3]}

    with pytest.raises(ValueError, match="do not match"):
        profile_manifest.validate_manifest_package([1, 2], package)


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
    assert v2_package["schema_version"] == 2
    assert v2_package["catalog_ids"] == v2_ids
    assert v2_package["phase_quotas"] == {"extract": 8, "segment": 6, "summary": 6, "entity": 8, "org": 2}
    assert {phase: len(catalog_ids) for phase, catalog_ids in v2_strata.items()} == v2_package[
        "phase_quotas"
    ]
    assert set().union(*(set(catalog_ids) for catalog_ids in v2_strata.values())) == set(v2_ids)
    assert v2_package["phase_candidates"]["extract"] == 8
    assert v2_package["expected_phase_coverage"] == v2_package["phase_quotas"]
    assert v2_package["safety"]["org_reset_requires_single_document_event"] is True
    assert [reset["catalog_id"] for reset in v2_package["org_event_resets"]] == v2_strata["org"]
    assert len({reset["event_id"] for reset in v2_package["org_event_resets"]}) == 2
    assert "people" not in v2_strata
    assert "people" not in v2_package["expected_phase_coverage"]
    assert "people_reset_names" not in v2_package

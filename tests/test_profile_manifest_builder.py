from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import AgendaItem, Base, Catalog, Document, Event, Membership, Person, Place
from pipeline import profile_manifest


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
    monkeypatch.setattr(profile_manifest, "_people_reset_candidates", lambda session: [{"catalog_id": 10, "reset_names": ["Alex Doe"]}])

    package = profile_manifest.build_manifest_package(
        "baseline_demo",
        quotas={"extract": 1, "segment": 1, "summary": 1, "entity": 1, "org": 1, "people": 1},
    )

    assert package["catalog_ids"] == [1, 3, 5, 7, 9, 10]
    assert package["strata"]["people"] == [10]
    assert package["org_event_resets"] == [{"catalog_id": 9, "event_id": 90}]
    assert package["people_reset_names"] == [{"catalog_id": 10, "names": ["Alex Doe"]}]
    assert package["expected_phase_coverage"]["entity"] == 2


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
        entities={"persons": ["Alex Doe"]},
        agenda_segmentation_status="complete",
        agenda_segmentation_item_count=2,
        related_ids=[1, 2],
    )
    session.add(catalog)
    session.flush()
    session.add(Document(catalog_id=catalog.id, event_id=event.id, place_id=place.id, category="agenda"))
    session.add(AgendaItem(catalog_id=catalog.id, event_id=event.id, order=1, title="Item 1"))
    session.add(Person(name="Alex Doe", person_type="mentioned", current_role="Mentioned in Demo records"))
    session.flush()
    catalog_id = catalog.id
    event_id = event.id
    person_id = session.query(Person.id).filter(Person.name == "Alex Doe").scalar()
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
        "schema_version": 1,
        "manifest_name": "demo",
        "catalog_ids": [catalog_id],
        "strata": {
            "extract": [],
            "segment": [catalog_id],
            "summary": [],
            "entity": [],
            "org": [catalog_id],
            "people": [catalog_id],
        },
        "org_event_resets": [{"catalog_id": catalog_id, "event_id": event_id}],
        "people_reset_names": [{"catalog_id": catalog_id, "names": ["Alex Doe"]}],
        "expected_phase_coverage": {"extract": 0, "segment": 1, "summary": 0, "entity": 1, "org": 1, "people": 1},
    }

    original_db_session = profile_manifest.db_session
    profile_manifest.db_session = fake_db_session
    try:
        result = profile_manifest.apply_preconditioning(package)
    finally:
        profile_manifest.db_session = original_db_session

    assert result["applied"]["deleted_agenda_items"] == 1
    assert result["applied"]["cleared_segment_catalogs"] == 1
    assert result["applied"]["cleared_entity_catalogs"] == 1
    assert result["applied"]["cleared_org_events"] == 1
    assert result["applied"]["deleted_people"] == 1

    verify = Session()
    refreshed_catalog = verify.get(Catalog, catalog_id)
    refreshed_event = verify.get(Event, event_id)
    assert refreshed_catalog.summary is None
    assert refreshed_catalog.entities is None
    assert refreshed_catalog.agenda_segmentation_status is None
    assert refreshed_catalog.related_ids is None
    assert refreshed_event.organization_id is None
    assert verify.query(AgendaItem).count() == 0
    assert verify.get(Person, person_id) is None
    verify.close()
    engine.dispose()


def test_build_profile_manifest_script_writes_manifest_package(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("build_profile_manifest", Path("scripts/build_profile_manifest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    package = {
        "schema_version": 1,
        "manifest_name": "baseline_demo",
        "catalog_ids": [11, 12],
        "phase_candidates": {"extract": 10, "segment": 10, "summary": 10, "entity": 10, "org": 10, "people": 10},
        "strata": {"extract": [11], "segment": [12], "summary": [], "entity": [], "org": [], "people": []},
        "expected_phase_coverage": {"extract": 1, "segment": 1, "summary": 0, "entity": 0, "org": 0, "people": 0},
    }

    mod._build_manifest_package_via_docker = lambda name, quotas: package
    exit_code = mod.main(["--name", "baseline_demo", "--output-dir", str(tmp_path), "--write"])

    manifest_path = tmp_path / "baseline_demo.txt"
    sidecar_path = tmp_path / "baseline_demo.json"
    assert exit_code == 0
    assert manifest_path.read_text(encoding="utf-8") == "11\n12\n"
    written_sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert written_sidecar["manifest_name"] == "baseline_demo"


def test_validate_manifest_package_rejects_mismatched_ids():
    package = {
        "schema_version": 1,
        "catalog_ids": [1, 3],
    }

    try:
        profile_manifest.validate_manifest_package([1, 2], package)
    except ValueError as exc:
        assert "do not match" in str(exc)
    else:
        raise AssertionError("expected manifest package mismatch to fail")


def test_people_reset_candidates_filter_non_human_civic_phrases(monkeypatch):
    class QueryStub:
        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return [
                (
                    17,
                    {
                        "persons": [
                            "Automated License Plate Readers",
                            "Carbon Monoxide",
                            "Erin Woodell",
                            "Rebecca Ayers Azran",
                        ]
                    },
                )
            ]

    class PersonQueryStub:
        def __init__(self, name: str):
            self._name = name

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class SessionStub:
        def query(self, *args, **kwargs):
            if args and getattr(args[0], "class_", None) is Catalog:
                return QueryStub()
            return PersonQueryStub("")

    candidates = profile_manifest._people_reset_candidates(SessionStub())

    assert candidates == [
        {
            "catalog_id": 17,
            "reset_names": ["Erin Woodell", "Rebecca Ayers Azran"],
        }
    ]
    assert profile_manifest._is_safe_people_reset_name("Joshua Cayetano Chair") is False
    assert profile_manifest._is_safe_people_reset_name("Supervisory Skills") is False

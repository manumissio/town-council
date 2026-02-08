import datetime
import sys
from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from pipeline.models import Catalog, Document, Event, EventStage, Membership, Organization, Person, Place
from pipeline.person_linker import link_people
from pipeline.promote_stage import promote_stage
from pipeline.run_pipeline import process_document_chunk


def test_stage_to_promote_to_people_link_flow(db_session):
    place = Place(
        name="Flow City",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:flow",
    )
    db_session.add(place)
    db_session.flush()

    stage = EventStage(
        ocd_division_id=place.ocd_division_id,
        name="City Council Meeting",
        record_date=datetime.date(2026, 2, 1),
        source="crawler",
        source_url="https://example.com/meeting",
        meeting_type="Regular",
    )
    db_session.add(stage)
    db_session.commit()

    promote_stage()

    event = db_session.query(Event).filter_by(name="City Council Meeting").one()
    org = Organization(name="City Council", classification="legislature", place_id=place.id, ocd_id="ocd-organization/1")
    db_session.add(org)
    db_session.flush()
    event.organization_id = org.id

    catalog = Catalog(url_hash="flow-hash", filename="meeting.pdf", entities={"persons": ["Mayor Jane Doe", "Resident Alex"]})
    db_session.add(catalog)
    db_session.flush()
    db_session.add(Document(place_id=place.id, event_id=event.id, catalog_id=catalog.id, url_hash="doc-hash"))
    db_session.commit()

    link_people()

    official = db_session.query(Person).filter_by(name="Jane Doe").one()
    mentioned = db_session.query(Person).filter_by(name="Resident Alex").one()
    membership_count = db_session.query(Membership).filter_by(person_id=official.id, organization_id=org.id).count()

    assert official.person_type == "official"
    assert mentioned.person_type == "mentioned"
    assert membership_count == 1


def test_process_document_chunk_keeps_prior_success_when_later_commit_fails(mocker):
    first = MagicMock(id=1, location="/tmp/1.pdf", content=None, entities=None)
    second = MagicMock(id=2, location="/tmp/2.pdf", content=None, entities=None)
    db = MagicMock()
    db.get.side_effect = [first, second]
    db.execute.return_value = None
    db.commit.side_effect = [None, SQLAlchemyError("commit failed")]

    mock_session_factory = MagicMock(return_value=db)
    mocker.patch("sqlalchemy.orm.sessionmaker", return_value=mock_session_factory)
    mocker.patch("pipeline.models.db_connect")
    mock_extractor_module = MagicMock()
    mock_extractor_module.extract_text.side_effect = ["doc1", "doc2"]
    mock_nlp_module = MagicMock()
    mock_nlp_module.extract_entities.side_effect = [{"persons": ["A"]}, {"persons": ["B"]}]
    mocker.patch.dict(
        sys.modules,
        {"pipeline.nlp_worker": mock_nlp_module, "pipeline.extractor": mock_extractor_module},
    )

    processed = process_document_chunk([1, 2])

    assert processed == 1
    assert first.content == "doc1"
    assert first.entities == {"persons": ["A"]}

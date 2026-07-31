import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock


def _meeting_document():
    document = SimpleNamespace(id=10, category="minutes")
    catalog = SimpleNamespace(
        id=20,
        filename="minutes.pdf",
        url="https://example.test/minutes.pdf",
        content="Meeting minutes",
        summary=None,
        summary_extractive=None,
        topics=None,
        summary_source_hash=None,
        content_hash=None,
        topics_source_hash=None,
        related_ids=None,
        lineage_id=None,
        lineage_confidence=None,
        agenda_items_hash=None,
        agenda_segmentation_status=None,
    )
    event = SimpleNamespace(
        ocd_id="ocd-event/1",
        name="Regular Meeting",
        meeting_type="Regular",
        record_date=datetime.date(2026, 7, 1),
    )
    place = SimpleNamespace(display_name="Test", name="test", state="CA")
    organization = SimpleNamespace(
        name="City Council",
        legistar_body_id=777,
        legistar_body_guid="00000000-0000-0000-0000-000000000777",
        roster_source_url="https://webapi.legistar.com/v1/Test/Bodies/777/OfficeRecords",
        roster_synced_at=datetime.datetime(2026, 7, 31, tzinfo=datetime.UTC),
        memberships=[
            SimpleNamespace(
                person=SimpleNamespace(id=1, ocd_id="ocd-person/1", name="Roster Member"),
                start_date=datetime.date(2024, 1, 1),
                end_date=None,
            )
        ],
    )
    return document, catalog, event, place, organization


def test_meeting_index_omits_people_until_events_have_authoritative_body_linkage():
    from pipeline.indexer_documents import _build_meeting_search_doc

    document, catalog, event, place, organization = _meeting_document()
    search_document = _build_meeting_search_doc(document, catalog, event, place, organization)

    assert "people_metadata" not in search_document
    assert "people" not in search_document


def test_semantic_meeting_hydration_omits_people_without_authoritative_body_linkage():
    from semantic_service.hydration import hydrate_meeting_hits

    document, catalog, event, place, organization = _meeting_document()
    database = MagicMock()
    meeting_query = database.query.return_value
    meeting_query.join.return_value = meeting_query
    meeting_query.outerjoin.return_value = meeting_query
    meeting_query.filter.return_value = meeting_query
    meeting_query.all.return_value = [
        (document, catalog, event, place, organization)
    ]
    candidate = SimpleNamespace(
        score=0.9,
        metadata={"db_id": document.id, "result_type": "meeting"},
    )

    [semantic_hit] = hydrate_meeting_hits(database, [candidate])

    assert "people_metadata" not in semantic_hit
    assert "people" not in semantic_hit

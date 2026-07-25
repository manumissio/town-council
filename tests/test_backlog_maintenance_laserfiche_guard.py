import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()

from pipeline import agenda_segmentation_maintenance
from pipeline import agenda_summary_batch
from pipeline import indexer, semantic_tasks
from pipeline.models import AgendaItem, Catalog, Document, Event, Place


def _seed_catalog(
    db_session,
    *,
    content: str,
    url: str,
    location: str,
    with_agenda_item: bool = False,
) -> tuple[Catalog, Event]:
    place_number = db_session.query(Place).count() + 1
    place = Place(
        name="San Mateo",
        state="CA",
        ocd_division_id=(
            "ocd-division/country:us/state:ca/place:"
            f"san_mateo_{place_number}"
        ),
        crawler_name="san_mateo",
    )
    db_session.add(place)
    db_session.flush()
    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        source="san_mateo",
        name="City Council",
    )
    db_session.add(event)
    db_session.flush()
    catalog = Catalog(
        url_hash=f"catalog-{db_session.query(Catalog).count()}",
        location=location,
        url=url,
        content=content,
        agenda_segmentation_status="complete" if with_agenda_item else None,
    )
    db_session.add(catalog)
    db_session.flush()
    db_session.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            category="agenda",
            url=url,
        )
    )
    if with_agenda_item:
        db_session.add(
            AgendaItem(
                catalog_id=catalog.id,
                event_id=event.id,
                order=1,
                title="Housing Update",
                description="Discuss housing funding and authorize the proposed budget.",
                classification="Action",
                page_number=1,
            )
        )
    db_session.commit()
    return catalog, event


def _install_successful_side_effect_boundaries(mocker):
    meili_client = MagicMock()
    documents_index = MagicMock()
    indexed_document_batches: list[list[dict[str, object]]] = []
    documents_index.add_documents.side_effect = indexed_document_batches.append
    meili_client.index.return_value = documents_index
    mocker.patch.object(indexer.meilisearch, "Client", return_value=meili_client)
    enqueued_catalog_ids: list[int] = []
    mocker.patch.object(
        semantic_tasks.embed_catalog_task,
        "delay",
        side_effect=enqueued_catalog_ids.append,
    )
    return indexed_document_batches, enqueued_catalog_ids


def test_segment_catalog_marks_laserfiche_error_content_failed(db_session):
    catalog, _event = _seed_catalog(
        db_session,
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=1",
        location="/tmp/agenda.html",
    )

    segmentation_result = agenda_segmentation_maintenance.segment_catalog_with_mode(
        catalog.id,
        segment_mode="maintenance",
    )

    assert segmentation_result["status"] == "failed"
    assert segmentation_result["error"] == "laserfiche_error_page_detected"
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.agenda_segmentation_status == "failed"
    assert refreshed.agenda_segmentation_error == "laserfiche_error_page_detected"
    assert refreshed.agenda_segmentation_item_count == 0


def test_agenda_summary_rejects_laserfiche_error_content(db_session):
    catalog, _event = _seed_catalog(
        db_session,
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2",
        location="/tmp/agenda.html",
    )

    summary_result = agenda_summary_batch.build_deterministic_agenda_summary_payload(
        catalog.id
    )

    assert summary_result == {
        "status": "error",
        "error": "laserfiche_error_page_detected",
    }
    db_session.expire_all()
    assert db_session.get(Catalog, catalog.id).summary is None


def test_segment_catalog_marks_laserfiche_loading_shell_failed(db_session):
    catalog, _event = _seed_catalog(
        db_session,
        content=(
            "[PAGE 1] Loading... The URL can be used to link to this page "
            "Your browser does not support the video tag."
        ),
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=3",
        location="/tmp/agenda.html",
    )

    segmentation_result = agenda_segmentation_maintenance.segment_catalog_with_mode(
        catalog.id,
        segment_mode="maintenance",
    )

    assert segmentation_result["status"] == "failed"
    assert segmentation_result["error"] == "laserfiche_loading_shell_detected"


def test_segment_catalog_marks_single_item_staff_report_failed(db_session):
    catalog, _event = _seed_catalog(
        db_session,
        content=(
            "CITY OF SAN MATEO\nAgenda Report\nAgenda Number: 8\n"
            "Section Name: NEW BUSINESS\nTO: City Council\n"
            "FROM: Alex Khojikian, City Manager\n"
            "SUBJECT: Boards and Commissions Vacancy Process\n"
            "RECOMMENDATION: Approve the revised vacancy process."
        ),
        url="https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid=4",
        location="/tmp/agenda.pdf",
    )

    segmentation_result = agenda_segmentation_maintenance.segment_catalog_with_mode(
        catalog.id,
        segment_mode="maintenance",
    )

    assert segmentation_result["status"] == "failed"
    assert segmentation_result["error"] == "single_item_staff_report_detected"
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.agenda_segmentation_status == "failed"
    assert refreshed.agenda_segmentation_error == "single_item_staff_report_detected"
    assert refreshed.agenda_segmentation_item_count == 0


def test_agenda_batch_runs_side_effects_only_for_changed_catalogs(
    db_session,
    mocker,
):
    first_catalog, _event = _seed_catalog(
        db_session,
        content="Agenda with housing discussion and public comment.",
        url="https://example.com/agenda-1",
        location="/tmp/agenda-1.html",
        with_agenda_item=True,
    )
    indexed_document_batches, enqueued_catalog_ids = (
        _install_successful_side_effect_boundaries(mocker)
    )
    first_summary = agenda_summary_batch.build_deterministic_agenda_summary_payload(
        first_catalog.id
    )
    assert first_summary["status"] == "complete"
    indexed_document_batches.clear()
    enqueued_catalog_ids.clear()

    second_catalog, _event = _seed_catalog(
        db_session,
        content="Agenda with budget discussion and final reading.",
        url="https://example.com/agenda-2",
        location="/tmp/agenda-2.html",
        with_agenda_item=True,
    )

    agenda_batch = agenda_summary_batch.build_deterministic_agenda_summary_payloads(
        [first_catalog.id, second_catalog.id]
    )

    assert agenda_batch["changed_catalog_ids"] == [second_catalog.id]
    assert agenda_batch["reindex_summary"] == {
        "catalogs_considered": 1,
        "catalogs_reindexed": 1,
        "catalogs_failed": 0,
        "failed_catalog_ids": [],
    }
    assert agenda_batch["embed_summary"] == {
        "catalogs_considered": 1,
        "embed_enqueued": 1,
        "embed_dispatch_failed": 0,
        "failed_catalog_ids": [],
    }
    indexed_documents = indexed_document_batches[0]
    assert {document["catalog_id"] for document in indexed_documents} == {
        second_catalog.id
    }
    assert enqueued_catalog_ids == [second_catalog.id]


def test_agenda_batch_reports_side_effect_failures_after_persistence(
    db_session,
    mocker,
):
    catalog, _event = _seed_catalog(
        db_session,
        content="Agenda with transportation discussion and public comment.",
        url="https://example.com/agenda-3",
        location="/tmp/agenda-3.html",
        with_agenda_item=True,
    )
    mocker.patch.object(
        indexer.meilisearch,
        "Client",
        side_effect=RuntimeError("search unavailable"),
    )
    mocker.patch.object(
        semantic_tasks.embed_catalog_task,
        "delay",
        side_effect=RuntimeError("broker unavailable"),
    )

    agenda_batch = agenda_summary_batch.build_deterministic_agenda_summary_payloads(
        [catalog.id]
    )

    assert agenda_batch["results"][catalog.id]["status"] == "complete"
    assert agenda_batch["changed_catalog_ids"] == [catalog.id]
    assert agenda_batch["reindex_summary"]["catalogs_failed"] == 1
    assert agenda_batch["reindex_summary"]["failed_catalog_ids"] == [catalog.id]
    assert agenda_batch["embed_summary"]["embed_dispatch_failed"] == 1
    assert agenda_batch["embed_summary"]["failed_catalog_ids"] == [catalog.id]
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.summary
    assert refreshed.summary_source_hash

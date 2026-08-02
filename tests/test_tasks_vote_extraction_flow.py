from datetime import date
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.orm import sessionmaker

from pipeline import indexer, llm, task_runtime, tasks
from pipeline.inference_provider_contract import InferenceProvider
from pipeline.models import AgendaItem, Catalog, Document, Event, Place


MEETING_CONTENT = (
    "Budget Amendment. The council considered the revised allocation. "
    "A motion was made and seconded. The motion passed by a vote of five to zero. "
) * 5


def _seed_vote_catalog(db_session, *, catalog_id: int, include_agenda_item: bool) -> AgendaItem | None:
    place = Place(
        name=f"vote-place-{catalog_id}",
        state="CA",
        ocd_division_id=f"ocd-division/country:us/state:ca/place:vote-{catalog_id}",
    )
    event = Event(
        ocd_id=f"ocd-event/vote-{catalog_id}",
        place=place,
        name="City Council",
        record_date=date(2026, 1, 10),
    )
    catalog = Catalog(
        id=catalog_id,
        url_hash=f"vote-{catalog_id}",
        content=MEETING_CONTENT,
        filename=f"vote-{catalog_id}.pdf",
    )
    document = Document(
        place=place,
        event=event,
        catalog=catalog,
        category="minutes",
    )
    agenda_item = None
    if include_agenda_item:
        agenda_item = AgendaItem(
            ocd_id=f"ocd-agenda-item/vote-{catalog_id}",
            event=event,
            catalog=catalog,
            order=1,
            title="Budget Amendment",
            description="Approve the revised allocation",
            classification="Agenda Item",
        )
    db_session.add_all([place, event, catalog, document])
    if agenda_item is not None:
        db_session.add(agenda_item)
    db_session.commit()
    return agenda_item


def _patch_task_session(mocker, shared_engine) -> None:
    mocker.patch.object(
        task_runtime,
        "task_session",
        return_value=sessionmaker(bind=shared_engine)(),
    )


def _patch_vote_provider(mocker) -> MagicMock:
    vote_provider = MagicMock(spec=InferenceProvider)
    vote_provider.generate_json.return_value = json.dumps(
        {
            "outcome_label": "passed",
            "confidence": 0.96,
            "motion_text": "Approve the revised allocation",
            "vote_tally_raw": "5-0",
            "yes_count": 5,
            "no_count": 0,
            "abstain_count": 0,
            "absent_count": 0,
            "evidence_snippet": "The motion passed by a vote of five to zero.",
        }
    )
    mocker.patch.object(llm, "get_runtime_provider", return_value=vote_provider)
    return vote_provider


def _patch_meilisearch_client(mocker, *, failure: Exception | None = None) -> MagicMock | None:
    if failure is not None:
        mocker.patch.object(indexer.meilisearch, "Client", side_effect=failure)
        return None
    search_client = MagicMock()
    search_client.index.return_value.delete_documents.return_value = SimpleNamespace(
        task_uid=29
    )
    search_client.wait_for_task.return_value = SimpleNamespace(
        status="succeeded",
        error=None,
    )
    mocker.patch.object(indexer.meilisearch, "Client", return_value=search_client)
    return search_client


def test_extract_votes_task_runs_and_returns_counters(mocker, db_session, shared_engine):
    agenda_item = _seed_vote_catalog(db_session, catalog_id=99, include_agenda_item=True)
    _patch_task_session(mocker, shared_engine)
    _patch_vote_provider(mocker)
    search_client = _patch_meilisearch_client(mocker)

    vote_result = tasks.extract_votes_task.run(99, force=True)

    assert vote_result["status"] == "complete"
    assert vote_result["processed_items"] == 1
    assert vote_result["updated_items"] == 1
    db_session.refresh(agenda_item)
    assert agenda_item.result == "Passed"
    assert agenda_item.votes["source"] == "llm_extracted"
    assert search_client is not None
    assert search_client.index.return_value.add_documents.called


def test_extract_votes_task_requires_segmented_items(mocker, db_session, shared_engine):
    _seed_vote_catalog(db_session, catalog_id=88, include_agenda_item=False)
    _patch_task_session(mocker, shared_engine)
    _patch_vote_provider(mocker)

    vote_result = tasks.extract_votes_task.run(88, force=True)

    assert vote_result["status"] == "not_generated_yet"
    assert "Run segmentation first" in vote_result["reason"]


def test_extract_votes_task_returns_disabled_when_feature_is_off(mocker, db_session, shared_engine):
    _seed_vote_catalog(db_session, catalog_id=77, include_agenda_item=True)
    _patch_task_session(mocker, shared_engine)
    vote_provider = _patch_vote_provider(mocker)

    vote_result = tasks.extract_votes_task.run(77, force=False)

    assert vote_result["status"] == "disabled"
    assert "Vote extraction is disabled" in vote_result["reason"]
    vote_provider.generate_json.assert_not_called()


def test_extract_votes_task_keeps_success_when_reindex_fails(mocker, db_session, shared_engine):
    agenda_item = _seed_vote_catalog(db_session, catalog_id=66, include_agenda_item=True)
    _patch_task_session(mocker, shared_engine)
    _patch_vote_provider(mocker)
    _patch_meilisearch_client(mocker, failure=ConnectionError("search unavailable"))

    vote_result = tasks.extract_votes_task.run(66, force=True)

    assert vote_result["status"] == "complete"
    assert vote_result["updated_items"] == 1
    db_session.refresh(agenda_item)
    assert agenda_item.result == "Passed"

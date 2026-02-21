from types import SimpleNamespace

from sqlalchemy.exc import SQLAlchemyError

import pipeline.verification_service as verification_module
from pipeline.verification_service import VerificationService


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_verify_item_sets_coords_and_result_on_direct_match(mocker):
    service = VerificationService()
    db = mocker.MagicMock()
    item = SimpleNamespace(
        id=1,
        title="Agenda Item",
        catalog_id=10,
        raw_history="Ayes: One, Two, Three. " * 4,
        spatial_coords=None,
        votes={"result": "Passed"},
        result=None,
    )
    db.get.return_value = SimpleNamespace(location="/tmp/agenda.pdf")
    mocker.patch("pipeline.verification_service.find_text_coordinates", return_value=[{"page": 1, "x": 1.0, "y": 2.0}])

    service.verify_item(item, db=db)

    assert item.spatial_coords == [{"page": 1, "x": 1.0, "y": 2.0}]
    assert item.result == "Passed"
    db.commit.assert_called_once()


def test_verify_item_uses_vote_tally_fallback(mocker):
    service = VerificationService()
    db = mocker.MagicMock()
    item = SimpleNamespace(
        id=2,
        title="Fallback Item",
        catalog_id=10,
        raw_history="Some intro text. Ayes: Alice, Bob, Carol.",
        spatial_coords=None,
        votes={},
        result=None,
    )
    db.get.return_value = SimpleNamespace(location="/tmp/agenda.pdf")
    mocker.patch(
        "pipeline.verification_service.find_text_coordinates",
        side_effect=[[], [{"page": 3, "x": 5.0, "y": 9.0}]],
    )

    service.verify_item(item, db=db)

    assert item.spatial_coords == [{"page": 3, "x": 5.0, "y": 9.0}]
    db.commit.assert_called_once()


def test_verify_item_rolls_back_when_commit_fails(mocker):
    service = VerificationService()
    db = mocker.MagicMock()
    item = SimpleNamespace(
        id=3,
        title="Rollback Item",
        catalog_id=10,
        raw_history="Ayes: One, Two, Three. " * 3,
        spatial_coords=None,
        votes={},
        result=None,
    )
    db.get.return_value = SimpleNamespace(location="/tmp/agenda.pdf")
    db.commit.side_effect = SQLAlchemyError("commit failed")
    mocker.patch("pipeline.verification_service.find_text_coordinates", return_value=[{"page": 2}])

    service.verify_item(item, db=db)

    db.rollback.assert_called_once()


def test_verify_all_processes_pending_items(mocker):
    service = VerificationService()
    db = mocker.MagicMock()
    items = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    db.query.return_value.filter.return_value.all.return_value = items
    mocker.patch.object(verification_module, "SessionLocal", return_value=_SessionContext(db))
    verify_spy = mocker.patch.object(service, "verify_item")

    service.verify_all()

    assert verify_spy.call_count == 2
    verify_spy.assert_any_call(items[0], db=db)
    verify_spy.assert_any_call(items[1], db=db)

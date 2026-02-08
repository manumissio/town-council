from types import SimpleNamespace

from sqlalchemy.exc import SQLAlchemyError

from pipeline.verification_service import VerificationService


def _make_service(mocker):
    service = VerificationService()
    service.db = mocker.MagicMock()
    return service


def test_verify_item_sets_coords_and_result_on_direct_match(mocker):
    service = _make_service(mocker)
    item = SimpleNamespace(
        id=1,
        title="Agenda Item",
        catalog_id=10,
        raw_history="Ayes: One, Two, Three. " * 4,
        spatial_coords=None,
        votes={"result": "Passed"},
        result=None,
    )
    service.db.get.return_value = SimpleNamespace(location="/tmp/agenda.pdf")
    mocker.patch("pipeline.verification_service.find_text_coordinates", return_value=[{"page": 1, "x": 1.0, "y": 2.0}])

    service.verify_item(item)

    assert item.spatial_coords == [{"page": 1, "x": 1.0, "y": 2.0}]
    assert item.result == "Passed"
    service.db.commit.assert_called_once()


def test_verify_item_uses_vote_tally_fallback(mocker):
    service = _make_service(mocker)
    item = SimpleNamespace(
        id=2,
        title="Fallback Item",
        catalog_id=10,
        raw_history="Some intro text. Ayes: Alice, Bob, Carol.",
        spatial_coords=None,
        votes={},
        result=None,
    )
    service.db.get.return_value = SimpleNamespace(location="/tmp/agenda.pdf")
    mocker.patch(
        "pipeline.verification_service.find_text_coordinates",
        side_effect=[[], [{"page": 3, "x": 5.0, "y": 9.0}]],
    )

    service.verify_item(item)

    assert item.spatial_coords == [{"page": 3, "x": 5.0, "y": 9.0}]
    service.db.commit.assert_called_once()


def test_verify_item_rolls_back_when_commit_fails(mocker):
    service = _make_service(mocker)
    item = SimpleNamespace(
        id=3,
        title="Rollback Item",
        catalog_id=10,
        raw_history="Ayes: One, Two, Three. " * 3,
        spatial_coords=None,
        votes={},
        result=None,
    )
    service.db.get.return_value = SimpleNamespace(location="/tmp/agenda.pdf")
    service.db.commit.side_effect = SQLAlchemyError("commit failed")
    mocker.patch("pipeline.verification_service.find_text_coordinates", return_value=[{"page": 2}])

    service.verify_item(item)

    service.db.rollback.assert_called_once()


def test_verify_all_processes_pending_items(mocker):
    service = _make_service(mocker)
    items = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    service.db.query.return_value.filter.return_value.all.return_value = items
    verify_spy = mocker.patch.object(service, "verify_item")

    service.verify_all()

    assert verify_spy.call_count == 2
    verify_spy.assert_any_call(items[0])
    verify_spy.assert_any_call(items[1])

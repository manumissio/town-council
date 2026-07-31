import sys
from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from pipeline.run_pipeline import process_document_chunk


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
    mocker.patch.dict(
        sys.modules,
        {"pipeline.extractor": mock_extractor_module},
    )

    processed = process_document_chunk([1, 2])

    assert processed == 1
    assert first.content == "doc1"
    # NLP enrichment now runs in the batch entity backfill path, not here.
    assert first.entities is None

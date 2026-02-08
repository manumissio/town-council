import pytest
from unittest.mock import MagicMock
import sys

# Mock heavy libraries
sys.modules["llama_cpp"] = MagicMock()
sys.modules["tika"] = MagicMock()

from pipeline.run_pipeline import process_document_chunk

def test_document_chunk_worker(mocker):
    """
    Test: Does chunk worker orchestrate OCR and NLP for one document?
    """
    # Mock DB
    mock_catalog = MagicMock()
    mock_catalog.id = 1
    mock_catalog.location = "/tmp/test.pdf"
    mock_catalog.content = None
    mock_catalog.entities = None
    
    mock_db = MagicMock()
    mock_db.get.return_value = mock_catalog
    
    # Mock DB Connection context
    mock_session = MagicMock()
    mock_session.return_value = mock_db
    mocker.patch("sqlalchemy.orm.sessionmaker", return_value=mock_session)
    mocker.patch("pipeline.models.db_connect")

    # Mock Extractor and NLP
    mocker.patch("pipeline.extractor.extract_text", return_value="Extracted Text")
    # Provide a lightweight nlp_worker module so process_document_chunk can import it
    # without pulling in spaCy during this unit test.
    mock_nlp_module = MagicMock()
    mock_nlp_module.extract_entities.return_value = {"persons": ["Mayor"]}
    mocker.patch.dict(sys.modules, {"pipeline.nlp_worker": mock_nlp_module})
    mock_db.execute.return_value = None

    # Action
    processed_count = process_document_chunk([1])

    # Verify
    assert processed_count == 1
    assert mock_catalog.content == "Extracted Text"
    assert mock_catalog.entities == {"persons": ["Mayor"]}
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()

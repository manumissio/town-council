import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock heavy libraries
sys.modules["llama_cpp"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["tika"] = MagicMock()

from pipeline.run_pipeline import process_single_document
import pipeline.extractor
import pipeline.nlp_worker

def test_single_document_worker(mocker):
    """
    Test: Does the worker function correctly orchestrate OCR and NLP?
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
    # We patch the source because it is imported inside the function
    mocker.patch("sqlalchemy.orm.sessionmaker", return_value=mock_session)
    mocker.patch("pipeline.models.db_connect") # Patch this where it is defined, or imported? It's imported in the function from pipeline.models
    
    # Mock Extractor and NLP
    mocker.patch("pipeline.extractor.extract_text", return_value="Extracted Text")
    mocker.patch("pipeline.nlp_worker.extract_entities", return_value={"persons": ["Mayor"]})
    
    # Action
    result_id = process_single_document(1)
    
    # Verify
    assert result_id == 1
    assert mock_catalog.content == "Extracted Text"
    assert mock_catalog.entities == {"persons": ["Mayor"]}
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()

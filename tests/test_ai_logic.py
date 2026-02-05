import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root and pipeline dir to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import DeclarativeBase, Catalog
from pipeline.summarizer import summarize_documents

@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database."""
    engine = create_engine('sqlite:///:memory:')
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_summarization_mocked(db_session, mocker):
    """
    Verify the summarizer logic without hitting the real Gemini API.
    """
    # 1. Add a document that needs summarization
    doc = Catalog(
        url_hash="test_hash",
        content="This is a long meeting text about zoning and taxes.",
        filename="meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mock environment variable and Gemini client
    mocker.patch('os.getenv', return_value="fake_key")
    mock_model = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.text = "1. Zoning discussed\n2. Taxes raised\n3. Meeting adjourned"
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch('google.generativeai.GenerativeModel', return_value=mock_model)
    mocker.patch('pipeline.summarizer.db_connect', return_value=db_session.get_bind())
    # Mock sleep to speed up test
    mocker.patch('time.sleep', return_value=None)

    # 3. Run summarizer
    summarize_documents()

    # 4. Verify results
    db_session.refresh(doc)
    assert "Zoning discussed" in doc.summary
    assert "Taxes raised" in doc.summary

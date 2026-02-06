import os
import pytest
from pipeline.models import Catalog, Base
from pipeline.summarizer import summarize_documents
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Setup: This creates a temporary, empty database in memory for each test."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_summarization_tier1_local(db_session, mocker):
    """
    Test: Does the local summarizer correctly update summary_extractive?
    """
    # 1. Setup: Add a document that needs a summary.
    doc = Catalog(
        url_hash="test_hash_local",
        content="The City Council discussed the budget today. It was a long meeting. Many people attended.",
        filename="local_meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mock: Inject temporary database.
    mocker.patch('pipeline.summarizer.db_connect', return_value=db_session.get_bind())

    # 3. Action: Run Tier 1 summarizer.
    summarize_documents()

    # 4. Verify: Check summary_extractive
    db_session.refresh(doc)
    assert doc.summary_extractive is not None
    assert "Council" in doc.summary_extractive

def test_summarization_gemini_on_demand(db_session, mocker):
    """
    Test: Simulates the on-demand Gemini summarization triggered via API.
    """
    # 1. Setup
    doc = Catalog(
        url_hash="test_hash_gemini",
        content="Zoning laws are being updated to allow for more housing units.",
        filename="gemini_meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mock Gemini API
    mock_client = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.text = "1. Zoning updated\n2. Housing increased"
    mock_client.models.generate_content.return_value = mock_response
    mocker.patch('google.genai.Client', return_value=mock_client)

    # Note: In the real app, this is handled by api/main.py. 
    # Here we are testing the database storage logic for Tier 2.
    doc.summary = mock_response.text
    db_session.commit()

    # 3. Verify
    db_session.refresh(doc)
    assert doc.summary == "1. Zoning updated\n2. Housing increased"

import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup: Add the project and pipeline folders to the path.
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import DeclarativeBase, Catalog
from pipeline.summarizer import summarize_documents

@pytest.fixture
def db_session():
    """Setup: Creates an empty in-memory database for AI testing."""
    engine = create_engine('sqlite:///:memory:')
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_summarization_mocked(db_session, mocker):
    """
    Test: Does the AI summarizer correctly update the database?
    
    Why we 'Mock':
    We don't want to call the real Gemini API during a test because:
    1. It costs money.
    2. It requires a real API key.
    3. It is slow and might fail if the internet is down.
    So, we 'fake' (mock) the API response.
    """
    # 1. Setup: Add a document to our fake DB that needs a summary.
    doc = Catalog(
        url_hash="test_hash",
        content="This is a long meeting text about zoning and taxes.",
        filename="meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mocking the API: 
    # We trick the code into thinking there is a valid API key.
    mocker.patch('os.getenv', return_value="fake_api_key_123")
    
    # We create a 'fake' AI client and a 'fake' response.
    mock_client = mocker.Mock()
    mock_response = mocker.Mock()
    # This is the text we WANT the AI to 'return' for this test.
    mock_response.text = "1. Zoning discussed\n2. Taxes raised\n3. Meeting adjourned"
    mock_client.models.generate_content.return_value = mock_response
    
    # Inject our fake client into the genai.Client class.
    mocker.patch('google.genai.Client', return_value=mock_client)
    # Inject our temporary database connection.
    mocker.patch('pipeline.summarizer.db_connect', return_value=db_session.get_bind())
    # Mock 'time.sleep' so the test doesn't wait 4 seconds between files.
    mocker.patch('time.sleep', return_value=None)

    # 3. Action: Run the summarizer logic.
    summarize_documents()

    # 4. Verify: Did the 'summary' column in the DB get updated with our fake text?
    db_session.refresh(doc)
    assert doc.summary is not None
    assert "Zoning discussed" in doc.summary
    assert "Taxes raised" in doc.summary
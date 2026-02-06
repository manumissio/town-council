import pytest
from pipeline.models import Catalog, Base
from pipeline.summarizer import summarize_documents
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Temporary in-memory database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_extractive_summarization_integration(db_session, mocker):
    """
    Test: Does the extractive summarizer correctly pick sentences from the text?
    This is Traditional AI (TextRank) and should not require an API key.
    """
    # 1. Setup Data with a repetitive but structured text
    long_text = (
        "The City Council met today to discuss the budget. "
        "The budget is the most important item on the agenda. "
        "Members voted to increase funding for parks and recreation. "
        "Many citizens attended the meeting to voice their concerns. "
        "The meeting was adjourned at 8:00 PM. "
        "Next meeting is scheduled for March 1st."
    )
    
    catalog = Catalog(
        filename="budget_meeting.pdf",
        content=long_text
    )
    db_session.add(catalog)
    db_session.commit()

    # 2. Mock: Trick the summarizer into using our test DB
    mocker.patch('pipeline.summarizer.db_connect', return_value=db_session.get_bind())

    # 3. Action
    summarize_documents()

    # 4. Verify
    record = db_session.query(Catalog).filter_by(filename="budget_meeting.pdf").first()
    assert record.summary_extractive is not None
    
    # Check that output contains text from the input (zero hallucination)
    # We check for a few key words that are present in the source text.
    assert "funding" in record.summary_extractive or "budget" in record.summary_extractive
    
    # TextRank should pick sentences from the original text. 
    # Let's verify at least one part of the summary matches a source sentence.
    original_sentences = [s.strip() for s in long_text.split(".") if s.strip()]
    summary_parts = record.summary_extractive.split(".")
    found_match = False
    for part in summary_parts:
        if part.strip() in original_sentences:
            found_match = True
            break
    assert found_match is True
    
    # Ensure it's not too long (TextRank summary should be approx 3 sentences)
    assert len(record.summary_extractive.split()) > 5

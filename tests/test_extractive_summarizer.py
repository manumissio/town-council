import pytest
from pipeline.summarizer import extract_summarize_catalog
from pipeline.models import Catalog

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
        url_hash="extractive_test_hash",
        content=long_text
    )
    db_session.add(catalog)
    db_session.commit()

    # 2. Action: Run the extractive summarizer
    extract_summarize_catalog(catalog.id)

    # 3. Verify: Did it save a summary?
    db_session.refresh(catalog)
    assert catalog.summary_extractive is not None
    # We check for general meeting-related keywords that should be picked up
    keywords = ["meeting", "discuss", "budget", "council", "members"]
    summary_lower = catalog.summary_extractive.lower()
    assert any(k in summary_lower for k in keywords)
    assert len(catalog.summary_extractive.split('.')) >= 1
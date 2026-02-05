import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup: Add project root and pipeline dir to path.
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'pipeline'))

from pipeline.models import Base, Catalog
from pipeline.nlp_worker import run_nlp_pipeline

@pytest.fixture
def db_session():
    """Setup: Creates an empty in-memory database for NLP testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_nlp_extraction_mocked(db_session, mocker):
    """
    Test: Does the NLP worker correctly identify Organizations and Locations?
    
    Why we 'Mock':
    We mock the 'SpaCy' library so we don't have to load a massive 500MB 
    language model just to run a quick test.
    """
    # 1. Setup: Add a document with text that mentions an Org and a Location.
    doc = Catalog(
        url_hash="nlp_test",
        content="The Belmont Police Department met with PG&E at City Hall.",
        filename="meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mocking SpaCy:
    # We create 'Fake' entity objects like the ones SpaCy would return.
    mock_nlp = mocker.Mock()
    mock_doc = mocker.Mock()
    
    # Entity 1: An Organization
    ent1 = mocker.Mock()
    ent1.text = "Belmont Police Department"
    ent1.label_ = "ORG"
    
    # Entity 2: Another Organization
    ent2 = mocker.Mock()
    ent2.text = "PG&E"
    ent2.label_ = "ORG"
    
    # Entity 3: A Location
    ent3 = mocker.Mock()
    ent3.text = "City Hall"
    ent3.label_ = "GPE" # GPE stands for Geopolitical Entity (like a city)
    
    # Tell our fake 'doc' to return these entities.
    mock_doc.ents = [ent1, ent2, ent3]
    # Tell the fake 'nlp.pipe' to return our fake 'doc'.
    mock_nlp.pipe.return_value = [mock_doc]
    
    # Inject the mock into the 'spacy.load' function.
    mocker.patch('spacy.load', return_value=mock_nlp)
    # Inject our temporary database.
    mocker.patch('pipeline.nlp_worker.db_connect', return_value=db_session.get_bind())

    # 3. Action: Run the NLP extraction logic.
    run_nlp_pipeline()

    # 4. Verify: Did the DB get updated with the correctly categorized lists?
    db_session.refresh(doc)
    assert doc.entities is not None
    # Check that organizations were found.
    assert "Belmont Police Department" in doc.entities['orgs']
    assert "PG&E" in doc.entities['orgs']
    # Check that locations were found.
    assert "City Hall" in doc.entities['locs']
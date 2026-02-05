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
from pipeline.nlp_worker import run_nlp_pipeline

@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database."""
    engine = create_engine('sqlite:///:memory:')
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_nlp_extraction_mocked(db_session, mocker):
    """
    Verify the NLP entity extraction logic.
    We mock the SpaCy model to return specific entities.
    """
    # 1. Add a document that needs NLP
    doc = Catalog(
        url_hash="nlp_test",
        content="The Belmont Police Department met with PG&E at City Hall.",
        filename="meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mock SpaCy
    mock_nlp = mocker.Mock()
    mock_doc = mocker.Mock()
    
    # Create mock entities
    ent1 = mocker.Mock()
    ent1.text = "Belmont Police Department"
    ent1.label_ = "ORG"
    
    ent2 = mocker.Mock()
    ent2.text = "PG&E"
    ent2.label_ = "ORG"
    
    ent3 = mocker.Mock()
    ent3.text = "City Hall"
    ent3.label_ = "GPE"
    
    mock_doc.ents = [ent1, ent2, ent3]
    mock_nlp.pipe.return_value = [mock_doc]
    
    mocker.patch('spacy.load', return_value=mock_nlp)
    mocker.patch('pipeline.nlp_worker.db_connect', return_value=db_session.get_bind())

    # 3. Run NLP pipeline
    run_nlp_pipeline()

    # 4. Verify results
    db_session.refresh(doc)
    assert doc.entities is not None
    assert "Belmont Police Department" in doc.entities['orgs']
    assert "PG&E" in doc.entities['orgs']
    assert "City Hall" in doc.entities['locs']

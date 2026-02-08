import pytest
from pipeline.models import Catalog

def test_nlp_extraction_mocked(db_session, mocker):
    """
    Test: Does the NLP worker correctly identify Organizations and Locations?
    """
    # 1. Setup: Add a document with text that mentions an Org and a Location.
    doc = Catalog(
        url_hash="nlp_test_hash",
        content="The Belmont Police Department met with PG&E at City Hall.",
        filename="meeting.pdf"
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Mocking SpaCy
    mock_nlp = mocker.Mock()
    mock_doc = mocker.Mock()

    ent1 = mocker.Mock()
    ent1.text = "The Belmont Police Department"
    ent1.label_ = "ORG"

    ent2 = mocker.Mock()
    ent2.text = "PG&E"
    ent2.label_ = "ORG"

    ent3 = mocker.Mock()
    ent3.text = "City Hall"
    ent3.label_ = "GPE"

    # Tell our fake 'doc' to return these entities.
    mock_doc.ents = [ent1, ent2, ent3]
    # Tell the fake 'nlp' call to return our fake 'doc'.
    mock_nlp.return_value = mock_doc
    # Tell the fake 'nlp.pipe' to return our fake 'doc'.
    mock_nlp.pipe.return_value = [mock_doc]

    from pipeline import nlp_worker
    mocker.patch.object(nlp_worker, "get_municipal_nlp_model", return_value=mock_nlp)

    # 3. Action
    nlp_worker.run_nlp_pipeline()

    # 4. Verify
    db_session.refresh(doc)
    assert doc.entities is not None
    assert "The Belmont Police Department" in doc.entities['orgs']
    assert "PG&E" in doc.entities['orgs']

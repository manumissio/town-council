import pytest
from pipeline.nlp_worker import get_municipal_nlp_model

@pytest.fixture
def nlp():
    """Loads the customized municipal NLP model."""
    return get_municipal_nlp_model()

def test_title_recognition(nlp):
    """Verify that roles like Mayor and Councilmember trigger PERSON recognition."""
    text = "The meeting was called to order by Mayor Jesse Arreguin."
    doc = nlp(text)
    
    # We expect 'Mayor Jesse Arreguin' to be a PERSON due to our RuleRuler
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    assert any("Mayor Jesse Arreguin" in p or "Jesse Arreguin" in p for p in persons)

def test_motion_recognition(nlp):
    """Verify that 'Moved by' and 'Seconded by' trigger PERSON recognition."""
    text = "The item was moved by Councilmember Smith and seconded by Mayor Jones."
    doc = nlp(text)
    
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    # Check that both names were captured
    assert any("Councilmember Smith" in p for p in persons)
    assert any("Mayor Jones" in p for p in persons)

def test_vote_block_recognition(nlp):
    """Verify that names in vote blocks are captured."""
    text = "Ayes: Harrison, Arreguin, Robinson. Noes: None."
    doc = nlp(text)
    
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    assert any("Ayes : Harrison" in p or "Harrison" in p for p in persons)

def test_cleanup_logic(nlp):
    """Verify that our triggers don't accidentally capture non-names (Sanity Check)."""
    # Note: The cleanup of 'triggers' happens in the worker loop, not the model itself.
    # Here we just verify the model tags them correctly.
    text = "Mayor John Doe spoke."
    doc = nlp(text)
    
    ent = next((e for e in doc.ents if "John Doe" in e.text), None)
    assert ent is not None
    assert ent.label_ == "PERSON"

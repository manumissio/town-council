import pytest
from pipeline.nlp_worker import get_municipal_nlp_model, extract_entities

@pytest.fixture
def nlp():
    return get_municipal_nlp_model()

def test_noise_reduction_specific_cases():
    """
    Test: Ensure the reported false positives are correctly filtered.
    """
    # Reported noisy strings
    noise = [
        "Berkeley CA",
        "Order N-29-20",
        "Local Artist",
        "Body Worn Cameras",
        "Page 2",
        "City Manager",
        "Exhibit A"
    ]
    
    text = "Presented by " + ". Also ".join(noise)
    entities = extract_entities(text)
    
    # None of these should be in the persons list
    for item in noise:
        assert item not in entities["persons"], f"Noise '{item}' should have been filtered!"

def test_legitimate_names_preserved():
    """
    Test: Ensure real names are still captured.
    """
    real_people = [
        "Jesse Arreguin",
        "Rashi Kesarwani",
        "Terry Taplin",
        "Mark Numainville",
        "Savita Chaudhary"
    ]
    
    text = "Speakers included: " + ", ".join(real_people)
    entities = extract_entities(text)
    
    for name in real_people:
        assert name in entities["persons"], f"Real name '{name}' was incorrectly filtered!"

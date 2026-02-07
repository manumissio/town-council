import pytest
from pipeline.nlp_worker import get_municipal_nlp_model, extract_entities
from pipeline.utils import is_likely_human_name

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
        "Exhibit A",
        "TELECONFERENCE LOCATION - MARRIOTT",
        "mailto:council@berkeleyca.gov",
        "http://berkeley.granicus.com/MediaPlayer.php?publish_id=1244"
    ]
    
    for item in noise:
        # We test both the raw extraction and the utility function
        entities = extract_entities(f"Presented by {item}.")
        assert item not in entities["persons"], f"Noise '{item}' should have been filtered from entities!"
        assert not is_likely_human_name(item), f"Utility should have blocked '{item}'!"

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

from pipeline import nlp_worker
from pipeline.utils import is_likely_human_name


class _FakeEnt:
    def __init__(self, text, label):
        self.text = text
        self.label_ = label


class _FakeDoc:
    def __init__(self, ents):
        self.ents = ents


def test_noise_reduction_filters_non_human_person_entities(mocker):
    fake_doc = _FakeDoc(
        [
            _FakeEnt("City Manager", "PERSON"),
            _FakeEnt("Page 2", "PERSON"),
            _FakeEnt("Jesse Arreguin", "PERSON"),
            _FakeEnt("City Hall", "GPE"),
        ]
    )
    fake_nlp = mocker.Mock(return_value=fake_doc)
    mocker.patch.object(nlp_worker, "get_municipal_nlp_model", return_value=fake_nlp)

    entities = nlp_worker.extract_entities("Presented by City Manager on Page 2.")

    assert "City Manager" not in entities["persons"]
    assert "Page 2" not in entities["persons"]
    assert "Jesse Arreguin" in entities["persons"]
    assert "City Hall" in entities["locs"]


def test_name_bouncer_rejects_known_noise_strings():
    noisy_values = [
        "Berkeley CA",
        "Order N-29-20",
        "Page 2",
        "City of Berkeley",
        "County of Alameda",
    ]
    for value in noisy_values:
        assert not is_likely_human_name(value)

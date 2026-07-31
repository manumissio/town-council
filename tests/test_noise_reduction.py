from pipeline import nlp_worker


class _FakeEnt:
    def __init__(self, text, label):
        self.text = text
        self.label_ = label


class _FakeDoc:
    def __init__(self, ents):
        self.ents = ents


def test_entity_extraction_ignores_person_entities(mocker):
    fake_doc = _FakeDoc(
        [
            _FakeEnt("City Manager", "PERSON"),
            _FakeEnt("Page 2", "PERSON"),
            _FakeEnt("Jesse Arreguin", "PERSON"),
            _FakeEnt("Planning Commission", "ORG"),
            _FakeEnt("City Hall", "GPE"),
        ]
    )
    fake_nlp = mocker.Mock(return_value=fake_doc)
    mocker.patch.object(nlp_worker, "get_municipal_nlp_model", return_value=fake_nlp)

    entities = nlp_worker.extract_entities("Presented by City Manager on Page 2.")

    assert entities == {
        "orgs": ["Planning Commission"],
        "locs": ["City Hall"],
    }

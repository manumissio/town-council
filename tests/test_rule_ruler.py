from pipeline import nlp_worker


class _FakeEnt:
    def __init__(self, text, label):
        self.text = text
        self.label_ = label


class _FakeDoc:
    def __init__(self, ents):
        self.ents = ents


def test_extract_entities_ignores_titled_people(mocker):
    fake_doc = _FakeDoc(
        [
            _FakeEnt("Mayor Jesse Arreguin", "PERSON"),
            _FakeEnt("Councilmember Terry Taplin", "PERSON"),
            _FakeEnt("Berkeley City Council", "ORG"),
        ]
    )
    fake_nlp = mocker.Mock(return_value=fake_doc)
    mocker.patch.object(nlp_worker, "get_municipal_nlp_model", return_value=fake_nlp)

    entities = nlp_worker.extract_entities("Motion led by municipal officials.")

    assert entities == {"orgs": ["Berkeley City Council"], "locs": []}


def test_extract_entities_ignores_vote_style_people(mocker):
    fake_doc = _FakeDoc(
        [
            _FakeEnt("Ayes : Harrison", "PERSON"),
            _FakeEnt("Noes : Robinson", "PERSON"),
        ]
    )
    fake_nlp = mocker.Mock(return_value=fake_doc)
    mocker.patch.object(nlp_worker, "get_municipal_nlp_model", return_value=fake_nlp)

    entities = nlp_worker.extract_entities("Ayes and Noes were recorded.")

    assert entities == {"orgs": [], "locs": []}

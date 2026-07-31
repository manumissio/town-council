from pipeline.config import NLP_MAX_TEXT_LENGTH
from pipeline.nlp_entity_candidates import empty_entities_payload


def extract_entities(text, *, nlp_loader):
    """
    Extract entities from a single text string.

    The loader is injected by the facade so existing tests can keep patching
    pipeline.nlp_worker.get_municipal_nlp_model.
    """
    if not text:
        return empty_entities_payload()

    nlp = nlp_loader()
    doc = nlp(text[:NLP_MAX_TEXT_LENGTH])
    entities = empty_entities_payload()

    for ent in doc.ents:
        if ent.label_ == "BOILERPLATE":
            continue

        name = ent.text.strip().replace("\n", " ")

        if len(name) < 2 or len(name) > 100:
            continue

        if ent.label_ == "ORG" and name not in entities["orgs"]:
            entities["orgs"].append(name)
        elif ent.label_ in ["GPE", "LOC"] and name not in entities["locs"]:
            entities["locs"].append(name)

    return entities

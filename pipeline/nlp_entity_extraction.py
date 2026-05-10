from pipeline.config import NLP_MAX_TEXT_LENGTH
from pipeline.nlp_entity_candidates import empty_entities_payload
from pipeline.utils import is_likely_human_name

_TITLE_PREFIXES = [
    "moved by",
    "seconded by",
    "mayor",
    "councilmember",
    "vice mayor",
    "chair",
    "director",
    "ayes :",
    "noes :",
]


def _strip_municipal_prefix(name):
    has_prefix = False
    for prefix in _TITLE_PREFIXES:
        if name.lower().startswith(prefix):
            name = name[len(prefix) :].strip()
            has_prefix = True
    return name, has_prefix


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
        name, has_prefix = _strip_municipal_prefix(name)

        if len(name) < 2 or len(name) > 100:
            continue

        if ent.label_ == "PERSON":
            if not is_likely_human_name(name, allow_single_word=has_prefix):
                continue
            if name not in entities["persons"]:
                entities["persons"].append(name)
        elif ent.label_ == "ORG" and name not in entities["orgs"]:
            entities["orgs"].append(name)
        elif ent.label_ in ["GPE", "LOC"] and name not in entities["locs"]:
            entities["locs"].append(name)

    return entities

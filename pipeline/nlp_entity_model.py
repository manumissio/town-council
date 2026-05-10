import threading

from pipeline.utils import is_likely_human_name

_cached_nlp = None
_model_lock = threading.Lock()
_TRUST_TITLES = [
    "mayor",
    "councilmember",
    "commissioner",
    "chair",
    "director",
    "ayes",
    "noes",
    "moved",
    "seconded",
    "vice mayor",
]
_ENTITY_RULER_PATTERNS = [
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "item"}, {"IS_DIGIT": True}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "page"}, {"IS_DIGIT": True}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "exhibit"}, {"IS_ALPHA": True, "LENGTH": 1}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "city"}, {"LOWER": "clerk"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "city"}, {"LOWER": "manager"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "deputy"}, {"LOWER": "director"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "roll"}, {"LOWER": "call"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "annotated"}, {"LOWER": "agenda"}]},
    {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "councilmember"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "vice"}, {"LOWER": "mayor"}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "vice"}, {"LOWER": "mayor"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "moved"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "seconded"}, {"LOWER": "by"}, {"IS_TITLE": True}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "ayes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
    {"label": "PERSON", "pattern": [{"LOWER": "noes"}, {"ORTH": ":"}, {"IS_TITLE": True}]},
]


def scrub_municipal_noise(doc):
    new_ents = []
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            text = ent.text.strip()
            text_lower = text.lower()
            is_trusted = any(text_lower.startswith(title) for title in _TRUST_TITLES)
            if not is_likely_human_name(text, allow_single_word=is_trusted):
                continue
            if not any(token.pos_ == "PROPN" for token in ent):
                continue

        new_ents.append(ent)

    doc.ents = new_ents
    return doc


def get_municipal_nlp_model():
    global _cached_nlp

    if _cached_nlp:
        return _cached_nlp

    with _model_lock:
        if _cached_nlp:
            return _cached_nlp

        try:
            import spacy
            from spacy.language import Language
        except Exception as exc:  # pragma: no cover - depends on local runtime
            raise RuntimeError(f"SpaCy NLP stack is unavailable in this runtime: {exc}") from exc

        if not Language.has_factory("scrub_municipal_noise"):
            Language.component("scrub_municipal_noise")(scrub_municipal_noise)

        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            import en_core_web_sm

            nlp = en_core_web_sm.load()

        ruler = nlp.add_pipe("entity_ruler", before="ner")
        ruler.add_patterns(_ENTITY_RULER_PATTERNS)
        nlp.add_pipe("scrub_municipal_noise", last=True)

        _cached_nlp = nlp
        return nlp

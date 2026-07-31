import threading

_cached_nlp = None
_model_lock = threading.Lock()
_ENTITY_RULER_PATTERNS = [
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "item"}, {"IS_DIGIT": True}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "page"}, {"IS_DIGIT": True}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "exhibit"}, {"IS_ALPHA": True, "LENGTH": 1}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "city"}, {"LOWER": "clerk"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "city"}, {"LOWER": "manager"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "deputy"}, {"LOWER": "director"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "roll"}, {"LOWER": "call"}]},
    {"label": "BOILERPLATE", "pattern": [{"LOWER": "annotated"}, {"LOWER": "agenda"}]},
]


def get_municipal_nlp_model():
    global _cached_nlp

    if _cached_nlp:
        return _cached_nlp

    with _model_lock:
        if _cached_nlp:
            return _cached_nlp

        try:
            import spacy
        except Exception as exc:  # pragma: no cover - depends on local runtime
            raise RuntimeError(f"SpaCy NLP stack is unavailable in this runtime: {exc}") from exc

        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            import en_core_web_sm

            nlp = en_core_web_sm.load()

        ruler = nlp.add_pipe("entity_ruler", before="ner")
        ruler.add_patterns(_ENTITY_RULER_PATTERNS)

        _cached_nlp = nlp
        return nlp

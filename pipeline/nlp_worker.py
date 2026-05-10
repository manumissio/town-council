from pipeline import nlp_entity_model as _model
from pipeline.nlp_entity_candidates import (
    _CAPITALIZED_NAME_RE,
    _ENTITY_LINE_HINTS,
    _bounded_join,
    _looks_low_signal_for_entity_ner,
    build_entity_candidate_text,
    empty_entities_payload,
)
from pipeline.nlp_entity_extraction import extract_entities as _extract_entities
from pipeline.nlp_entity_model import scrub_municipal_noise

__all__ = [
    "_CAPITALIZED_NAME_RE",
    "_ENTITY_LINE_HINTS",
    "_bounded_join",
    "_cached_nlp",
    "_looks_low_signal_for_entity_ner",
    "_model_lock",
    "build_entity_candidate_text",
    "empty_entities_payload",
    "extract_entities",
    "get_municipal_nlp_model",
    "scrub_municipal_noise",
]

# Compatibility surface for tests and callers that reset or inspect the cache
# through pipeline.nlp_worker.
_cached_nlp = None
_model_lock = _model._model_lock


def get_municipal_nlp_model():
    global _cached_nlp

    if _cached_nlp is not _model._cached_nlp:
        _model._cached_nlp = _cached_nlp

    _cached_nlp = _model.get_municipal_nlp_model()
    return _cached_nlp


def extract_entities(text):
    return _extract_entities(text, nlp_loader=get_municipal_nlp_model)

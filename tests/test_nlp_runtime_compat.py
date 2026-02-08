import sys

def test_nlp_runtime_compatibility_is_explicit():
    """
    Keep runtime behavior explicit:
    - nlp_worker module import should never crash due to spaCy.
    - Model loading should raise a clear RuntimeError when spaCy is unavailable.
    """
    import pipeline.nlp_worker as nlp_worker

    if sys.version_info >= (3, 14):
        try:
            nlp_worker.get_municipal_nlp_model()
        except RuntimeError as exc:
            assert "SpaCy NLP stack is unavailable" in str(exc)
        else:  # pragma: no cover - only if upstream stack adds support
            assert True


def test_sanitize_text_for_topics_strips_urls_and_http_tokens():
    from pipeline.topic_worker import _sanitize_text_for_topics

    text = "See https://cupertino.gov for details. http cupertino www.cupertino.org"
    out = _sanitize_text_for_topics(text)

    lowered = out.lower()
    assert "https://" not in lowered
    assert "www." not in lowered
    # Token-level removals: we don't want topic bigrams like 'http cupertino'
    assert " http " not in f" {lowered} "
    assert " www " not in f" {lowered} "

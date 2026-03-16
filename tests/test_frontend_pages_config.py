from pathlib import Path


def test_next_config_supports_static_export_mode():
    source = Path("frontend/next.config.js").read_text(encoding="utf-8")
    assert 'process.env.STATIC_EXPORT === "true"' in source
    assert 'output: staticExport ? "export" : "standalone"' in source
    assert "basePath: staticExport ? pagesBasePath : \"\"" in source


def test_frontend_uses_proxy_csp_and_same_origin_mutation_routes():
    next_config = Path("frontend/next.config.js").read_text(encoding="utf-8")
    proxy_source = Path("frontend/proxy.js").read_text(encoding="utf-8")
    result_card = Path("frontend/components/ResultCard.js").read_text(encoding="utf-8")
    api_lib = Path("frontend/lib/api.js").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_API_AUTH_KEY" not in api_lib
    assert "NEXT_PUBLIC_API_AUTH_KEY" not in result_card
    assert "x-nonce" in proxy_source
    assert "script-src 'self' 'nonce-${nonce}' 'strict-dynamic'" in proxy_source
    assert "script-src 'self' 'unsafe-inline'" not in proxy_source
    assert "NEXT_PUBLIC_API_URL must be set to a non-localhost origin when APP_ENV is not dev." in next_config
    assert 'fetch(`/api/report-issue`' in result_card
    assert 'new URL(`/api/summarize/${hit.catalog_id}`' in result_card
    assert 'new URL(`/api/segment/${hit.catalog_id}`' in result_card
    assert 'new URL(`/api/topics/${hit.catalog_id}`' in result_card
    assert 'new URL(`/api/extract/${hit.catalog_id}`' in result_card

from pathlib import Path


def test_next_config_supports_static_export_mode():
    source = Path("frontend/next.config.js").read_text(encoding="utf-8")
    assert 'process.env.STATIC_EXPORT === "true"' in source
    assert 'output: staticExport ? "export" : "standalone"' in source
    assert "basePath: staticExport ? pagesBasePath : \"\"" in source

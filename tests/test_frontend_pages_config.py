import os
import subprocess
from pathlib import Path


def test_next_config_supports_static_export_mode():
    source = Path("frontend/next.config.js").read_text(encoding="utf-8")
    package_json = Path("frontend/package.json").read_text(encoding="utf-8")
    build_script = Path("frontend/scripts/build.js").read_text(encoding="utf-8")
    assert 'process.env.STATIC_EXPORT === "true"' in source
    assert 'output: staticExport ? "export" : "standalone"' in source
    assert "basePath: staticExport ? pagesBasePath : \"\"" in source
    assert '"build": "node scripts/build.js"' in package_json
    assert 'const staticExport = process.env.STATIC_EXPORT === "true";' in build_script
    assert '"app", "api"' in build_script


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


def test_static_export_build_wrapper_restores_api_routes(tmp_path):
    project_root = tmp_path / "frontend"
    scripts_dir = project_root / "scripts"
    app_api_dir = project_root / "app" / "api"
    next_bin = project_root / "node_modules" / "next" / "dist" / "bin"

    scripts_dir.mkdir(parents=True)
    app_api_dir.mkdir(parents=True)
    next_bin.mkdir(parents=True)

    (scripts_dir / "build.js").write_text(
        Path("frontend/scripts/build.js").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (app_api_dir / "route.js").write_text("console.log('route');\n", encoding="utf-8")
    (next_bin / "next.js").write_text("process.exit(0);\n", encoding="utf-8")

    env = os.environ.copy()
    env["STATIC_EXPORT"] = "true"

    subprocess.run(
        ["node", str(scripts_dir / "build.js")],
        cwd=project_root,
        env=env,
        check=True,
    )

    assert app_api_dir.exists()
    assert (app_api_dir / "route.js").exists()
    assert not (project_root / "app" / "__api_runtime_only").exists()


def test_home_page_uses_explicit_offset_search_flow():
    source = Path("frontend/app/page.js").read_text(encoding="utf-8")
    assert "offsetToUse = 0" in source
    assert "append = false" in source
    assert "performSearch({ offsetToUse: 0, append: false })" in source
    assert "const handleLoadMore = () => {" in source

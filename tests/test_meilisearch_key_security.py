import json
import logging
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.meilisearch_credentials import (
    DEVELOPMENT_MEILI_SEARCH_KEY,
    resolve_meilisearch_reader_key,
)
from semantic_service import main as semantic_main


SCOPED_SEARCH_KEY = "scoped-search-key"
MASTER_KEY_SENTINEL = "master-key-must-not-reach-readers"
UNSAFE_SEARCH_KEY_MESSAGE = "MEILI_SEARCH_KEY must contain printable ASCII characters"
MISSING_SEARCH_KEY_MESSAGE = "MEILI_SEARCH_KEY must be set when APP_ENV is not dev"
DEVELOPMENT_SEARCH_KEY_MESSAGE = "MEILI_SEARCH_KEY must not use the development fallback"
FALLBACK_WARNING = "Meilisearch reader is using the development fallback key"


@pytest.mark.parametrize("app_env", ["prod", "staging", ""])
@pytest.mark.parametrize("search_key", ["", "   "])
def test_non_dev_reader_policy_rejects_missing_search_key(
    app_env: str,
    search_key: str,
) -> None:
    with pytest.raises(RuntimeError, match=MISSING_SEARCH_KEY_MESSAGE):
        resolve_meilisearch_reader_key(app_env, search_key)


@pytest.mark.parametrize(
    "search_key",
    [
        " scoped-search-key",
        "scoped-search-key ",
        "scoped-search-key\n",
        "scoped-search-key\x7f",
        "scoped-search-key-é",
    ],
)
def test_reader_policy_rejects_transport_unsafe_key(search_key: str) -> None:
    with pytest.raises(RuntimeError, match=UNSAFE_SEARCH_KEY_MESSAGE) as search_key_error:
        resolve_meilisearch_reader_key("dev", search_key)

    assert search_key not in str(search_key_error.value)


@pytest.mark.parametrize("search_key", ["", "   "])
def test_dev_reader_policy_uses_named_fallback(search_key: str) -> None:
    selected_key = resolve_meilisearch_reader_key("dev", search_key)

    assert selected_key == DEVELOPMENT_MEILI_SEARCH_KEY


def test_reader_policy_preserves_valid_key() -> None:
    assert resolve_meilisearch_reader_key("prod", SCOPED_SEARCH_KEY) == SCOPED_SEARCH_KEY


def test_non_dev_reader_policy_rejects_development_fallback_key() -> None:
    with pytest.raises(RuntimeError, match=DEVELOPMENT_SEARCH_KEY_MESSAGE):
        resolve_meilisearch_reader_key("prod", DEVELOPMENT_MEILI_SEARCH_KEY)


@pytest.mark.parametrize("module_name", ["api.main", "semantic_service.main"])
def test_reader_module_rejects_missing_non_dev_search_key(module_name: str) -> None:
    reader_environment = {**os.environ, "APP_ENV": "prod", "MEILI_MASTER_KEY": MASTER_KEY_SENTINEL}
    reader_environment.pop("MEILI_SEARCH_KEY", None)

    completed_process = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        check=False,
        capture_output=True,
        env=reader_environment,
        text=True,
        timeout=10,
    )

    assert completed_process.returncode != 0
    assert MISSING_SEARCH_KEY_MESSAGE in completed_process.stderr
    assert MASTER_KEY_SENTINEL not in completed_process.stderr


@pytest.mark.parametrize("module_name", ["api.main", "semantic_service.main"])
def test_reader_module_rejects_development_key_outside_dev(module_name: str) -> None:
    reader_environment = {
        **os.environ,
        "APP_ENV": "prod",
        "MEILI_SEARCH_KEY": DEVELOPMENT_MEILI_SEARCH_KEY,
        "MEILI_MASTER_KEY": MASTER_KEY_SENTINEL,
    }
    completed_process = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        check=False,
        capture_output=True,
        env=reader_environment,
        text=True,
        timeout=10,
    )

    assert completed_process.returncode != 0
    assert DEVELOPMENT_SEARCH_KEY_MESSAGE in completed_process.stderr
    assert DEVELOPMENT_MEILI_SEARCH_KEY not in completed_process.stderr
    assert MASTER_KEY_SENTINEL not in completed_process.stderr


def _reader_request_handler(
    authorization_headers: list[str],
    request_paths: list[str],
) -> type[BaseHTTPRequestHandler]:
    class ReaderRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            authorization_headers.append(self.headers.get("Authorization", ""))
            request_paths.append(self.path)
            response_body = json.dumps(
                {
                    "message": "denied",
                    "code": "invalid_api_key",
                    "type": "auth",
                    "link": "https://docs.meilisearch.com/errors#invalid_api_key",
                }
            ).encode()
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def do_GET(self) -> None:
            authorization_headers.append(self.headers.get("Authorization", ""))
            request_paths.append(self.path)
            response_body = json.dumps(
                {
                    "numberOfDocuments": 1,
                    "isIndexing": False,
                    "fieldDistribution": {"title": 1},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, _format: str, *_arguments: object) -> None:
            return None

    return ReaderRequestHandler


@pytest.mark.parametrize(
    "client_import",
    [
        "from api.search.support_core import client",
        "from semantic_service.main import client",
    ],
    ids=["api", "semantic"],
)
def test_rejected_reader_search_uses_scoped_key_once_without_master_retry(
    client_import: str,
) -> None:
    authorization_headers: list[str] = []
    request_paths: list[str] = []
    server = HTTPServer(
        ("127.0.0.1", 0),
        _reader_request_handler(authorization_headers, request_paths),
    )
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    search_environment = {
        **os.environ,
        "APP_ENV": "prod",
        "MEILI_HOST": f"http://127.0.0.1:{server.server_port}",
        "MEILI_SEARCH_KEY": SCOPED_SEARCH_KEY,
        "MEILI_MASTER_KEY": MASTER_KEY_SENTINEL,
    }
    request_code = (
        "from meilisearch.errors import MeilisearchApiError;"
        f"{client_import};"
        "\ntry:\n client.index('documents').search('zoning')"
        "\nexcept MeilisearchApiError:\n print('denied')"
    )
    try:
        completed_process = subprocess.run(
            [sys.executable, "-c", request_code],
            check=True,
            capture_output=True,
            env=search_environment,
            text=True,
            timeout=10,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    assert not server_thread.is_alive()
    assert completed_process.stdout.strip() == "denied"
    assert authorization_headers == [f"Bearer {SCOPED_SEARCH_KEY}"]
    assert request_paths == ["/indexes/documents/search"]


def test_api_stats_uses_scoped_reader_key() -> None:
    authorization_headers: list[str] = []
    request_paths: list[str] = []
    server = HTTPServer(
        ("127.0.0.1", 0),
        _reader_request_handler(authorization_headers, request_paths),
    )
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    stats_environment = {
        **os.environ,
        "APP_ENV": "prod",
        "MEILI_HOST": f"http://127.0.0.1:{server.server_port}",
        "MEILI_SEARCH_KEY": SCOPED_SEARCH_KEY,
        "MEILI_MASTER_KEY": MASTER_KEY_SENTINEL,
    }
    try:
        completed_process = subprocess.run(
            [
                sys.executable,
                "-c",
                "from api import main; print(main.get_stats().number_of_documents)",
            ],
            check=True,
            capture_output=True,
            env=stats_environment,
            text=True,
            timeout=10,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    assert not server_thread.is_alive()
    assert completed_process.stdout.strip() == "1"
    assert authorization_headers == [f"Bearer {SCOPED_SEARCH_KEY}"]
    assert request_paths == ["/indexes/documents/stats"]


def test_legacy_api_export_contains_reader_key_not_master_key() -> None:
    reader_environment = {
        **os.environ,
        "APP_ENV": "prod",
        "MEILI_SEARCH_KEY": SCOPED_SEARCH_KEY,
        "MEILI_MASTER_KEY": MASTER_KEY_SENTINEL,
    }
    completed_process = subprocess.run(
        [
            sys.executable,
            "-c",
            "from api.search.support_core import MEILI_MASTER_KEY; print(MEILI_MASTER_KEY)",
        ],
        check=True,
        capture_output=True,
        env=reader_environment,
        text=True,
        timeout=10,
    )

    assert completed_process.stdout.strip() == SCOPED_SEARCH_KEY
    assert MASTER_KEY_SENTINEL not in completed_process.stdout


def test_semantic_dev_startup_warns_without_search_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MEILI_MASTER_KEY", MASTER_KEY_SENTINEL)
    monkeypatch.setattr(semantic_main, "MEILI_SEARCH_KEY", "")
    monkeypatch.setattr(semantic_main, "MEILI_READER_KEY", DEVELOPMENT_MEILI_SEARCH_KEY)
    application = FastAPI(lifespan=semantic_main.lifespan)

    with caplog.at_level(logging.WARNING, logger="town-council-semantic"):
        with TestClient(application):
            pass

    assert FALLBACK_WARNING in caplog.text
    assert DEVELOPMENT_MEILI_SEARCH_KEY not in caplog.text
    assert MASTER_KEY_SENTINEL not in caplog.text


def test_meilisearch_reader_key_contract_is_documented() -> None:
    example_environment = Path(".env.example").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    operations = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")
    profile_readme = Path("env/profiles/README.md").read_text(encoding="utf-8")
    security = Path("SECURITY.md").read_text(encoding="utf-8")

    assert "MEILI_SEARCH_KEY=" in example_environment
    assert "MEILI_SEARCH_KEY" in readme
    assert "MEILI_SEARCH_KEY_UID" in operations
    assert "GET /keys/{uid}" in operations
    assert '"actions":["search","stats.get"]' in operations
    assert 'Authorization: Bearer $MEILI_' not in operations
    assert 'MEILI_SEARCH_KEY="$MEILI_SEARCH_KEY"' not in operations
    assert '-H "@$MEILI_MASTER_HEADER_FILE"' in operations
    assert '-H "@$MEILI_SEARCH_HEADER_FILE"' in operations
    assert (
        "APP_ENV=production docker compose -f docker-compose.yml up -d --build\n"
        "   --force-recreate api semantic"
    ) in operations
    assert "docker compose up -d --build postgres redis meilisearch" not in readme
    assert "docker compose up -d --build postgres redis meilisearch" not in operations
    assert "docker compose up -d" not in operations
    assert "--env-file .env --env-file env/profiles/" in readme
    assert "--env-file .env --env-file env/profiles/" in operations
    assert "--env-file .env --env-file env/profiles/" in profile_readme
    assert "docker compose --env-file env/profiles/" not in readme
    assert "docker compose --env-file env/profiles/" not in operations
    assert "docker compose --env-file env/profiles/" not in profile_readme
    assert "docker-compose.dev.yml" in profile_readme
    assert "API and semantic" in security
    assert "MEILI_SEARCH_KEY" in security

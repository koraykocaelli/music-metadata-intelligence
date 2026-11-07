import os
import re
from pathlib import Path

import pytest

# The app module needs a DATABASE_URL to build its (lazy, unconnected) engine.
# These tests never touch a database.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://placeholder:placeholder@localhost:5432/unit_placeholder",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_index_is_served_with_security_headers(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Music Metadata Intelligence" in response.text

    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_index_has_no_inline_scripts_styles_or_external_resources() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "<style" not in html
    assert " style=" not in html
    assert not re.search(r"\son[a-z]+=", html)  # inline event handlers
    assert not re.search(r"(src|href)=\"(https?:)?//", html)  # no CDN


JS_MODULES = sorted((STATIC / "js").glob("*.js"))


def test_javascript_modules_exist() -> None:
    names = {path.name for path in JS_MODULES}

    assert {"main.js", "api.js", "ui.js", "analysis.js"} <= names


@pytest.mark.parametrize("module", JS_MODULES, ids=lambda path: path.name)
def test_javascript_never_inserts_untrusted_html(module) -> None:
    script = module.read_text(encoding="utf-8")

    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert sink not in script


def test_javascript_uses_only_existing_api_endpoints(client) -> None:
    spec_paths = set(client.get("/openapi.json").json()["paths"])
    source = "\n".join(path.read_text(encoding="utf-8") for path in JS_MODULES)
    used = set(re.findall(r"[\"`](/api/v1/[a-z/]+)", source))

    assert used
    assert used <= spec_paths


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/static/js/main.js", "javascript"),
        ("/static/js/analysis.js", "javascript"),
        ("/static/app.css", "text/css"),
        ("/examples/catalog.csv", "text/csv"),
        ("/examples/catalog.json", "application/json"),
    ],
)
def test_assets_and_examples_are_served(client, path, content_type) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


@pytest.mark.parametrize(
    "path",
    [
        "/examples/reference_tracks.json",
        "/examples/..%2f.env",
        "/examples/%2e%2e/.env",
        "/static/..%2f..%2f.env",
        "/static/%2e%2e/%2e%2e/.env",
        "/static/../../requirements.txt",
    ],
)
def test_no_arbitrary_file_access(client, path) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert "DATABASE_URL" not in response.text


def test_ui_routes_are_not_in_api_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/" not in paths
    assert not any(path.startswith("/examples") for path in paths)


def test_seed_script_refuses_non_demo_database(monkeypatch, capsys) -> None:
    from scripts import seed_demo_catalog

    monkeypatch.setattr(
        seed_demo_catalog.settings,
        "database_url",
        "postgresql+psycopg://u:p@localhost:5432/music_metadata",
    )

    def fail_if_connecting():
        raise AssertionError("must not connect")

    monkeypatch.setattr(seed_demo_catalog, "SessionLocal", fail_if_connecting)

    assert seed_demo_catalog.main() == 2
    assert "Refusing to seed" in capsys.readouterr().err

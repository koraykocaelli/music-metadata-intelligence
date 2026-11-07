from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


APP_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_DIR / "static"
EXAMPLES_DIR = APP_DIR.parent / "examples"

# Strict policy for the browser interface: only same-origin scripts, styles
# and API calls; no inline script, no framing, no plugins.
UI_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; form-action 'none'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

# Fixed allow-list: no user-controlled paths are ever resolved.
EXAMPLE_FILES = {
    "catalog.csv": "text/csv; charset=utf-8",
    "catalog.json": "application/json",
}

router = APIRouter(include_in_schema=False)

static_files = StaticFiles(directory=STATIC_DIR)


@router.get("/")
def index() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html; charset=utf-8",
        headers=UI_SECURITY_HEADERS,
    )


def _example(name: str) -> FileResponse:
    return FileResponse(
        EXAMPLES_DIR / name,
        media_type=EXAMPLE_FILES[name],
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/examples/catalog.csv")
def example_catalog_csv() -> FileResponse:
    return _example("catalog.csv")


@router.get("/examples/catalog.json")
def example_catalog_json() -> FileResponse:
    return _example("catalog.json")

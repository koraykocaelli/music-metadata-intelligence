from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import CatalogFormat, CatalogMatchResponse
from app.services import catalog as catalog_service
from app.services.catalog import CatalogFileError


router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"],
)

# Documents the raw request body in OpenAPI / Swagger UI.
CATALOG_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "description": (
            "Raw UTF-8 catalog file (max "
            f"{catalog_service.MAX_UPLOAD_BYTES // 1024} KiB, "
            f"{catalog_service.MAX_CATALOG_ROWS} records). Columns/keys: "
            "artist, title (required), album, isrc (optional)."
        ),
        "content": {
            "text/csv": {
                "schema": {"type": "string"},
                "example": "artist,title,album,isrc\nThe Weeknd,Blinding Lights,After Hours,USUG11904206\n",
            },
            "application/json": {
                "schema": {"type": "array", "items": {"type": "object"}},
                "example": [{"artist": "The Weeknd", "title": "Blinding Lights"}],
            },
        },
    }
}


@dataclass(frozen=True)
class CatalogUpload:
    catalog_format: CatalogFormat
    content: bytes


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail=(
            "Catalog file exceeds the "
            f"{catalog_service.MAX_UPLOAD_BYTES} byte limit."
        ),
    )


async def read_catalog_upload(request: Request) -> CatalogUpload:
    """Read the request body in memory with a hard size limit.

    The body is never written to disk; reading stops as soon as the limit is
    exceeded, so memory use is bounded regardless of Content-Length.
    """

    try:
        catalog_format = catalog_service.detect_catalog_format(
            request.headers.get("content-type")
        )
    except CatalogFileError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message)

    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        if not declared_length.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            )

        if int(declared_length) > catalog_service.MAX_UPLOAD_BYTES:
            raise _too_large()

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)

        if len(body) > catalog_service.MAX_UPLOAD_BYTES:
            raise _too_large()

    return CatalogUpload(catalog_format=catalog_format, content=bytes(body))


def _match(db: Session, upload: CatalogUpload) -> CatalogMatchResponse:
    try:
        return catalog_service.match_catalog(
            db,
            upload.catalog_format,
            upload.content,
        )
    except CatalogFileError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message)


@router.post(
    "/match",
    response_model=CatalogMatchResponse,
    openapi_extra=CATALOG_REQUEST_BODY,
)
def match_catalog(
    upload: CatalogUpload = Depends(read_catalog_upload),
    db: Session = Depends(get_db),
) -> CatalogMatchResponse:
    """Match an uploaded catalog against the reference catalog (read-only)."""

    return _match(db, upload)


@router.post(
    "/match/export",
    openapi_extra=CATALOG_REQUEST_BODY,
    responses={
        200: {
            "content": {"text/csv": {}, "application/json": {}},
            "description": "Downloadable match results in input order.",
        }
    },
)
def export_catalog_matches(
    export_format: CatalogFormat = Query(alias="format"),
    upload: CatalogUpload = Depends(read_catalog_upload),
    db: Session = Depends(get_db),
) -> Response:
    """Match an uploaded catalog and download the results as CSV or JSON."""

    result = _match(db, upload)

    if export_format == CatalogFormat.CSV:
        content = catalog_service.export_results_csv(result)
        media_type = "text/csv; charset=utf-8"
    else:
        content = catalog_service.export_results_json(result)
        media_type = "application/json"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                'attachment; filename="catalog_match_results.'
                f'{export_format.value}"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )

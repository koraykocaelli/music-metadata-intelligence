from enum import Enum

from pydantic import BaseModel

from app.schemas.track import MatchCandidate


class CatalogFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


class CatalogRowStatus(str, Enum):
    MATCHED = "matched"
    REVIEW = "review"
    UNMATCHED = "unmatched"
    INVALID = "invalid"


class CatalogRowError(BaseModel):
    field: str | None
    message: str


class CatalogRowResult(BaseModel):
    # 0-based position of the record in the uploaded file.
    input_index: int
    # 1-based physical line where the record starts (CSV only).
    line_number: int | None
    artist: str | None
    title: str | None
    album: str | None
    isrc: str | None
    status: CatalogRowStatus
    matches: list[MatchCandidate]
    errors: list[CatalogRowError]


class CatalogMatchSummary(BaseModel):
    total: int
    matched: int
    review: int
    unmatched: int
    invalid: int


class CatalogMatchResponse(BaseModel):
    input_format: CatalogFormat
    ignored_columns: list[str]
    summary: CatalogMatchSummary
    results: list[CatalogRowResult]

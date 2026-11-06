import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.services.normalization import normalize_text, normalize_track_title


# ISRC (ISO 3901): 2-letter country code, 3-character alphanumeric registrant
# code, 2-digit year, 5-digit designation code. Hyphenated display form
# (e.g. "US-UG1-19-04206") is accepted and stored in compact uppercase form.
ISRC_PATTERN = re.compile(
    r"^([A-Z]{2})-?([A-Z0-9]{3})-?([0-9]{2})-?([0-9]{5})$"
)

RequiredText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
OptionalText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=255),
]


def normalize_isrc(value: str) -> str:
    match = ISRC_PATTERN.fullmatch(value.strip().upper())

    if match is None:
        raise ValueError(
            "ISRC must be 12 characters: 2-letter country code, "
            "3 letters/digits, 2-digit year and 5 digits "
            "(e.g. USUG11904206 or US-UG1-19-04206)."
        )

    return "".join(match.groups())


class TrackCreate(BaseModel):
    artist: RequiredText
    title: RequiredText
    album: OptionalText | None = None
    isrc: str | None = None

    @field_validator("artist")
    @classmethod
    def artist_must_have_content(cls, value: str) -> str:
        if not normalize_text(value):
            raise ValueError("artist must contain at least one letter or digit.")

        return value

    @field_validator("title")
    @classmethod
    def title_must_have_content(cls, value: str) -> str:
        if not normalize_track_title(value):
            raise ValueError(
                "title must contain at least one letter or digit besides "
                "noise such as 'Official Audio' or 'Lyrics'."
            )

        return value

    @field_validator("album")
    @classmethod
    def blank_album_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("isrc", mode="before")
    @classmethod
    def validate_isrc(cls, value: object) -> object:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("ISRC must be a string.")

        return normalize_isrc(value)


class TrackRead(BaseModel):
    id: int
    artist: str
    title: str
    album: str | None
    isrc: str | None
    normalized_artist: str | None
    normalized_title: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchClassification(str, Enum):
    HIGH_CONFIDENCE = "high_confidence"
    REVIEW = "review"
    NO_MATCH = "no_match"


class MatchMethod(str, Enum):
    ISRC = "isrc"
    METADATA = "metadata"


class MatchCandidate(BaseModel):
    track_id: int
    artist: str
    title: str
    score: float
    classification: MatchClassification
    match_method: MatchMethod

class BatchTrackRequest(BaseModel):
    tracks: list[TrackCreate] = Field(
        min_length=1,
        max_length=100,
    )


class BatchTrackStatus(str, Enum):
    MATCHED = "matched"
    REVIEW = "review"
    UNMATCHED = "unmatched"


class BatchTrackResult(BaseModel):
    input_index: int
    artist: str
    title: str
    status: BatchTrackStatus
    matches: list[MatchCandidate]


class BatchTrackResponse(BaseModel):
    total: int
    matched: int
    review: int
    unmatched: int
    results: list[BatchTrackResult]
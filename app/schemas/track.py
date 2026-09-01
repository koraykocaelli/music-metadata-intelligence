from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackCreate(BaseModel):
    artist: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    album: str | None = Field(default=None, max_length=255)
    isrc: str | None = Field(default=None, min_length=12, max_length=12)


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
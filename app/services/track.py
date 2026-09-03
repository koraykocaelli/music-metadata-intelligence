from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.track import Track
from app.repositories import track as track_repository
from app.schemas.track import TrackCreate
from app.services.normalization import normalize_text, normalize_track_title


def create_track(db: Session, track_data: TrackCreate) -> Track:
    normalized_artist = normalize_text(track_data.artist)
    normalized_title = normalize_track_title(track_data.title)

    if track_data.isrc:
        existing_track = track_repository.get_track_by_isrc(
            db,
            track_data.isrc,
        )

        if existing_track is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A track with this ISRC already exists.",
            )

    existing_track = track_repository.get_track_by_normalized_metadata(
        db,
        normalized_artist,
        normalized_title,
    )

    if existing_track is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A track with the same normalized artist and title already exists.",
        )

    return track_repository.create_track(
        db,
        track_data,
        normalized_artist=normalized_artist,
        normalized_title=normalized_title,
    )


def get_tracks(db: Session) -> list[Track]:
    return track_repository.get_tracks(db)


def get_track_by_id(db: Session, track_id: int) -> Track | None:
    return track_repository.get_track_by_id(db, track_id)
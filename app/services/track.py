from sqlalchemy.orm import Session

from app.models.track import Track
from app.repositories import track as track_repository
from app.schemas.track import TrackCreate


def create_track(db: Session, track_data: TrackCreate) -> Track:
    return track_repository.create_track(db, track_data)


def get_tracks(db: Session) -> list[Track]:
    return track_repository.get_tracks(db)


def get_track_by_id(db: Session, track_id: int) -> Track | None:
    return track_repository.get_track_by_id(db, track_id)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.track import Track
from app.schemas.track import TrackCreate

from sqlalchemy import or_, select


def create_track(
    db: Session,
    track_data: TrackCreate,
    normalized_artist: str,
    normalized_title: str,
) -> Track:
    track = Track(
        artist=track_data.artist,
        title=track_data.title,
        album=track_data.album,
        isrc=track_data.isrc,
        normalized_artist=normalized_artist,
        normalized_title=normalized_title,
    )

    db.add(track)
    db.commit()
    db.refresh(track)

    return track

def get_tracks(db: Session) -> list[Track]:
    statement = select(Track).order_by(Track.id)

    return list(db.scalars(statement).all())


def get_track_by_id(db: Session, track_id: int) -> Track | None:
    return db.get(Track, track_id)

def get_track_by_isrc(db: Session, isrc: str) -> Track | None:
    statement = select(Track).where(Track.isrc == isrc)

    return db.scalar(statement)


def get_track_by_normalized_metadata(
    db: Session,
    normalized_artist: str,
    normalized_title: str,
) -> Track | None:
    statement = select(Track).where(
        Track.normalized_artist == normalized_artist,
        Track.normalized_title == normalized_title,
    )

    return db.scalar(statement)

def get_all_tracks(db: Session) -> list[Track]:
    statement = select(Track).order_by(Track.id)

    return list(db.scalars(statement).all())

def get_match_candidates(
    db: Session,
    normalized_artist: str,
    normalized_title: str,
    limit: int = 100,
) -> list[Track]:
    artist_tokens = normalized_artist.split()
    title_tokens = normalized_title.split()

    artist_hint = artist_tokens[-1] if artist_tokens else normalized_artist
    title_hint = title_tokens[0] if title_tokens else normalized_title

    statement = (
        select(Track)
        .where(
            or_(
                Track.normalized_artist == normalized_artist,
                Track.normalized_title == normalized_title,
                Track.normalized_artist.contains(artist_hint),
                Track.normalized_title.contains(title_hint),
            )
        )
        .order_by(Track.id)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


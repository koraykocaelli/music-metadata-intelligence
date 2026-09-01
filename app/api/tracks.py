from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.track import TrackCreate, TrackRead
from app.services import track as track_service


router = APIRouter(
    prefix="/api/v1/tracks",
    tags=["tracks"],
)


@router.post(
    "",
    response_model=TrackRead,
    status_code=status.HTTP_201_CREATED,
)
def create_track(
    track_data: TrackCreate,
    db: Session = Depends(get_db),
) -> TrackRead:
    return track_service.create_track(db, track_data)


@router.get(
    "",
    response_model=list[TrackRead],
)
def get_tracks(
    db: Session = Depends(get_db),
) -> list[TrackRead]:
    return track_service.get_tracks(db)


@router.get(
    "/{track_id}",
    response_model=TrackRead,
)
def get_track(
    track_id: int,
    db: Session = Depends(get_db),
) -> TrackRead:
    track = track_service.get_track_by_id(db, track_id)

    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    return track
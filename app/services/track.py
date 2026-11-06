from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.track import Track
from app.repositories import track as track_repository
from app.schemas.track import (
    BatchTrackRequest,
    BatchTrackResponse,
    BatchTrackResult,
    BatchTrackStatus,
    MatchClassification,
    MatchMethod,
    TrackCreate,
)
from app.services.normalization import normalize_text, normalize_track_title
from app.services.matching import (
    calculate_similarity,
    classify_similarity,
    is_metadata_match,
)

ISRC_UNIQUE_INDEX = "ix_tracks_isrc"
UNIQUE_VIOLATION_SQLSTATE = "23505"


def _is_unique_violation(error: IntegrityError, constraint_name: str) -> bool:
    diag = getattr(error.orig, "diag", None)

    return (
        getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION_SQLSTATE
        and getattr(diag, "constraint_name", None) == constraint_name
    )


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

    try:
        return track_repository.create_track(
            db,
            track_data,
            normalized_artist=normalized_artist,
            normalized_title=normalized_title,
        )
    except IntegrityError as error:
        # A concurrent request inserted the same ISRC between the check above
        # and this insert; the unique index rejected it (session rolled back).
        if _is_unique_violation(error, ISRC_UNIQUE_INDEX):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A track with this ISRC already exists.",
            ) from error

        raise


def get_tracks(db: Session) -> list[Track]:
    return track_repository.get_tracks(db)


def get_track_by_id(db: Session, track_id: int) -> Track | None:
    return track_repository.get_track_by_id(db, track_id)

def find_similar_tracks(
    db: Session,
    track_data: TrackCreate,
    threshold: float = 80.0,
) -> list[dict[str, object]]:
    # ISRC is a strong recording identifier.
    # If an exact ISRC match exists, return it directly.
    if track_data.isrc:
        isrc_match = track_repository.get_track_by_isrc(
            db,
            track_data.isrc,
        )

        if isrc_match is not None:
            return [
                {
                    "track_id": isrc_match.id,
                    "artist": isrc_match.artist,
                    "title": isrc_match.title,
                    "score": 100.0,
                    "classification": classify_similarity(100.0),
                    "match_method": MatchMethod.ISRC,
                }
            ]

    normalized_artist = normalize_text(track_data.artist)
    normalized_title = normalize_track_title(track_data.title)

    candidates = track_repository.get_match_candidates(
        db,
        normalized_artist,
        normalized_title,
    )

    matches: list[dict[str, object]] = []

    for candidate in candidates:
        # Skip candidates without usable normalized metadata (None or empty,
        # e.g. legacy rows whose text was stripped by older normalization).
        if not candidate.normalized_artist or not candidate.normalized_title:
            continue

        score = calculate_similarity(
            normalized_artist,
            normalized_title,
            candidate.normalized_artist,
            candidate.normalized_title,
        )

        if score >= threshold and is_metadata_match(
                normalized_artist,
                normalized_title,
                candidate.normalized_artist,
                candidate.normalized_title,
                raw_title_a=track_data.title,
                raw_title_b=candidate.title,
        ):
            matches.append(
                {
                    "track_id": candidate.id,
                    "artist": candidate.artist,
                    "title": candidate.title,
                    "score": score,
                    "classification": classify_similarity(score),
                    "match_method": MatchMethod.METADATA,
                }
            )

    return sorted(
        matches,
        key=lambda item: item["score"],
        reverse=True,
    )

def determine_match_status(matches: list[dict[str, object]]) -> BatchTrackStatus:
    """Shared matched/review/unmatched rule for batch and catalog matching."""

    if not matches:
        return BatchTrackStatus.UNMATCHED

    if any(
        match["classification"] == MatchClassification.HIGH_CONFIDENCE
        for match in matches
    ):
        return BatchTrackStatus.MATCHED

    return BatchTrackStatus.REVIEW


def match_batch_tracks(
    db: Session,
    batch_data: BatchTrackRequest,
) -> BatchTrackResponse:
    results: list[BatchTrackResult] = []

    matched_count = 0
    review_count = 0
    unmatched_count = 0

    for index, track_data in enumerate(batch_data.tracks):
        matches = find_similar_tracks(db, track_data)
        track_status = determine_match_status(matches)

        if track_status == BatchTrackStatus.UNMATCHED:
            unmatched_count += 1
        elif track_status == BatchTrackStatus.MATCHED:
            matched_count += 1
        else:
            review_count += 1

        results.append(
            BatchTrackResult(
                input_index=index,
                artist=track_data.artist,
                title=track_data.title,
                status=track_status,
                matches=matches,
            )
        )

    return BatchTrackResponse(
        total=len(batch_data.tracks),
        matched=matched_count,
        review=review_count,
        unmatched=unmatched_count,
        results=results,
    )


from rapidfuzz import fuzz

from app.schemas.track import MatchClassification

from app.services.normalization import detect_track_versions


MIN_ARTIST_SCORE = 60.0
MIN_TITLE_SCORE = 92.0
MIN_FINAL_SCORE = 80.0


def calculate_similarity_components(
    artist_a: str,
    title_a: str,
    artist_b: str,
    title_b: str,
) -> tuple[float, float]:
    artist_score = fuzz.ratio(artist_a, artist_b)
    title_score = fuzz.ratio(title_a, title_b)

    return round(artist_score, 2), round(title_score, 2)


def calculate_similarity(
    artist_a: str,
    title_a: str,
    artist_b: str,
    title_b: str,
) -> float:
    artist_score, title_score = calculate_similarity_components(
        artist_a,
        title_a,
        artist_b,
        title_b,
    )

    final_score = (artist_score * 0.4) + (title_score * 0.6)

    return round(final_score, 2)


def is_metadata_match(
    artist_a: str,
    title_a: str,
    artist_b: str,
    title_b: str,
    raw_title_a: str | None = None,
    raw_title_b: str | None = None,
) -> bool:
    if raw_title_a is not None and raw_title_b is not None:
        versions_a = detect_track_versions(raw_title_a)
        versions_b = detect_track_versions(raw_title_b)

        if versions_a != versions_b:
            return False

    artist_score, title_score = calculate_similarity_components(
        artist_a,
        title_a,
        artist_b,
        title_b,
    )

    final_score = calculate_similarity(
        artist_a,
        title_a,
        artist_b,
        title_b,
    )

    return (
        artist_score >= MIN_ARTIST_SCORE
        and title_score >= MIN_TITLE_SCORE
        and final_score >= MIN_FINAL_SCORE
    )


def classify_similarity(score: float) -> MatchClassification:
    if score >= 95.0:
        return MatchClassification.HIGH_CONFIDENCE

    if score >= 80.0:
        return MatchClassification.REVIEW

    return MatchClassification.NO_MATCH
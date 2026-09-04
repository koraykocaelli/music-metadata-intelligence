from rapidfuzz import fuzz

from app.schemas.track import MatchClassification


def calculate_similarity(
    artist_a: str,
    title_a: str,
    artist_b: str,
    title_b: str,
) -> float:
    artist_score = fuzz.ratio(artist_a, artist_b)
    title_score = fuzz.ratio(title_a, title_b)

    final_score = (artist_score * 0.4) + (title_score * 0.6)

    return round(final_score, 2)


def classify_similarity(score: float) -> MatchClassification:
    if score >= 95.0:
        return MatchClassification.HIGH_CONFIDENCE

    if score >= 80.0:
        return MatchClassification.REVIEW

    return MatchClassification.NO_MATCH


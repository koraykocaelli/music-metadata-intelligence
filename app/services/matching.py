from rapidfuzz import fuzz


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

def classify_similarity(score: float) -> str:
    if score >= 95.0:
        return "high_confidence"

    if score >= 80.0:
        return "review"

    return "no_match"

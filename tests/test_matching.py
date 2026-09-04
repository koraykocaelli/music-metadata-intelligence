from app.schemas.track import MatchClassification
from app.services.matching import calculate_similarity, classify_similarity


def test_identical_metadata_has_full_similarity() -> None:
    score = calculate_similarity(
        "the weeknd",
        "blinding lights",
        "the weeknd",
        "blinding lights",
    )

    assert score == 100.0


def test_similar_metadata_has_high_score() -> None:
    score = calculate_similarity(
        "the weekend",
        "blinding light",
        "the weeknd",
        "blinding lights",
    )

    assert score >= 80.0


def test_high_confidence_classification() -> None:
    assert (
        classify_similarity(96.0)
        == MatchClassification.HIGH_CONFIDENCE
    )


def test_review_classification() -> None:
    assert classify_similarity(85.0) == MatchClassification.REVIEW


def test_no_match_classification() -> None:
    assert classify_similarity(60.0) == MatchClassification.NO_MATCH


from app.schemas.track import MatchClassification
from app.services.matching import (
    calculate_similarity,
    classify_similarity,
    is_metadata_match,
)


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

def test_metadata_match_accepts_similar_metadata() -> None:
    assert is_metadata_match(
        "the weekend",
        "blinding light",
        "the weeknd",
        "blinding lights",
    )


def test_metadata_match_rejects_insufficient_title_similarity() -> None:
    assert not is_metadata_match(
        "coldplay",
        "clocks",
        "coldplay",
        "clock",
    )

def test_metadata_match_rejects_different_track_versions() -> None:
    assert not is_metadata_match(
        "the weeknd",
        "save your tears",
        "the weeknd",
        "save your tears remix",
        raw_title_a="Save Your Tears",
        raw_title_b="Save Your Tears Remix",
    )


def test_metadata_match_accepts_noise_title_variation() -> None:
    assert is_metadata_match(
        "the weeknd",
        "blinding lights",
        "the weeknd",
        "blinding lights",
        raw_title_a="Blinding Lights",
        raw_title_b="Blinding Lights (Official Audio)",
    )
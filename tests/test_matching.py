import pytest

from app.schemas.track import MatchClassification
from app.services.matching import (
    calculate_similarity,
    classify_similarity,
    is_metadata_match,
)
from app.services.normalization import normalize_text, normalize_track_title


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


# --- Empty and non-Latin metadata must never match spuriously -------------


@pytest.mark.parametrize(
    ("artist_a", "title_a", "artist_b", "title_b"),
    [
        ("", "", "", ""),
        ("", "blinding lights", "", "blinding lights"),
        ("the weeknd", "", "the weeknd", ""),
        ("the weeknd", "blinding lights", "", ""),
    ],
)
def test_empty_normalized_metadata_never_matches(
    artist_a, title_a, artist_b, title_b
) -> None:
    assert not is_metadata_match(artist_a, title_a, artist_b, title_b)


def test_empty_normalized_metadata_has_no_similarity() -> None:
    assert calculate_similarity("", "", "", "") == 0.0
    assert calculate_similarity("", "blinding lights", "", "blinding lights") == 60.0


def test_unrelated_non_latin_tracks_do_not_match() -> None:
    # Previously both artists normalized to "" and this pair matched.
    assert not is_metadata_match(
        normalize_text("Кино"),
        normalize_track_title("Группа крови"),
        normalize_text("宇多田ヒカル"),
        normalize_track_title("Звезда"),
    )


def test_identical_non_latin_tracks_match() -> None:
    assert is_metadata_match(
        normalize_text("Кино"),
        normalize_track_title("Группа крови"),
        normalize_text("КИНО"),
        normalize_track_title("Группа Крови (Official Audio)"),
    )

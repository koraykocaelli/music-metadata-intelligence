import pytest

from app.services.normalization import normalize_text, normalize_track_title


def test_normalize_text() -> None:
    assert normalize_text("THE WEEKND!!!") == "the weeknd"


def test_normalize_track_title_removes_official_audio() -> None:
    assert (
        normalize_track_title("Blinding Lights (Official Audio)")
        == "blinding lights"
    )


def test_normalize_track_title_removes_lyrics() -> None:
    assert normalize_track_title("Blinding Lights [Lyrics]") == "blinding lights"


# --- Unicode, whitespace and empty-value handling -------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Beyoncé", "beyonce"),
        ("Björk", "bjork"),
        ("Sigur Rós", "sigur ros"),
        ("Motörhead", "motorhead"),
        ("İstanbul", "istanbul"),
        ("Tarkan Şımarık", "tarkan simarik"),
        ("Mø", "mo"),
        ("Straße", "strasse"),
        ("Łona", "lona"),
        ("Œuvre", "oeuvre"),
        ("ＡＢＣ", "abc"),
    ],
)
def test_normalize_text_folds_latin_letters_to_ascii(raw, expected) -> None:
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Кино", "кино"),
        ("Группа Крови!", "группа крови"),
        ("宇多田ヒカル", "宇多田ヒカル"),
        ("ドラゴン", "ドラゴン"),
        ("हिन्दी गाना", "हिन्दी गाना"),
        ("Ελλάδα", "ελλάδα"),
    ],
)
def test_normalize_text_preserves_non_latin_scripts(raw, expected) -> None:
    assert normalize_text(raw) == expected


def test_normalize_text_keeps_unrelated_non_latin_strings_distinct() -> None:
    assert normalize_text("Кино") != normalize_text("宇多田ヒカル")
    assert normalize_text("Кино") != ""


@pytest.mark.parametrize("raw", ["", "   ", "!!!", "\t\n", "...---...", "\u200b"])
def test_normalize_text_returns_empty_for_content_free_values(raw) -> None:
    assert normalize_text(raw) == ""


def test_normalize_text_collapses_unicode_whitespace() -> None:
    assert normalize_text("  The\u00a0Weeknd\t\n ") == "the weeknd"


def test_normalize_track_title_can_become_empty_for_noise_only_titles() -> None:
    assert normalize_track_title("(Official Audio)") == ""

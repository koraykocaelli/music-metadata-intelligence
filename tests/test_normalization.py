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


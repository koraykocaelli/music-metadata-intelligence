import pytest
from pydantic import ValidationError

from app.schemas.track import BatchTrackRequest, TrackCreate


def test_valid_existing_request_is_unchanged() -> None:
    track = TrackCreate(
        artist="Daft Punk",
        title="One More Time",
        album="Discovery",
        isrc="GBDUW0000053",
    )

    assert track.artist == "Daft Punk"
    assert track.title == "One More Time"
    assert track.album == "Discovery"
    assert track.isrc == "GBDUW0000053"


def test_optional_fields_default_to_none() -> None:
    track = TrackCreate(artist="Daft Punk", title="One More Time")

    assert track.album is None
    assert track.isrc is None


def test_surrounding_whitespace_is_trimmed() -> None:
    track = TrackCreate(
        artist="  The Weeknd\t",
        title="\nBlinding Lights  ",
        album="  After Hours ",
    )

    assert track.artist == "The Weeknd"
    assert track.title == "Blinding Lights"
    assert track.album == "After Hours"


def test_trimming_applies_before_max_length() -> None:
    track = TrackCreate(artist=f"  {'a' * 255}  ", title="Song")

    assert len(track.artist) == 255


@pytest.mark.parametrize("field", ["artist", "title"])
def test_values_longer_than_255_characters_are_rejected(field) -> None:
    data = {"artist": "Artist", "title": "Title", field: "a" * 256}

    with pytest.raises(ValidationError):
        TrackCreate(**data)


@pytest.mark.parametrize("field", ["artist", "title"])
@pytest.mark.parametrize("value", ["", " ", "   \t\n ", " "])
def test_empty_or_whitespace_only_values_are_rejected(field, value) -> None:
    data = {"artist": "Artist", "title": "Title", field: value}

    with pytest.raises(ValidationError):
        TrackCreate(**data)


@pytest.mark.parametrize("field", ["artist", "title"])
@pytest.mark.parametrize("value", ["!!!", "...", "-_-", "​"])
def test_values_that_normalize_to_empty_are_rejected(field, value) -> None:
    data = {"artist": "Artist", "title": "Title", field: value}

    with pytest.raises(ValidationError, match="letter or digit"):
        TrackCreate(**data)


@pytest.mark.parametrize("title", ["Official Audio", "(Official Audio)", "[Lyrics]"])
def test_noise_only_titles_are_rejected(title) -> None:
    with pytest.raises(ValidationError, match="title"):
        TrackCreate(artist="Artist", title=title)


def test_non_latin_metadata_is_accepted() -> None:
    track = TrackCreate(artist="Кино", title="Группа крови")

    assert track.artist == "Кино"
    assert track.title == "Группа крови"


@pytest.mark.parametrize("album", ["", "   "])
def test_blank_album_becomes_none(album) -> None:
    assert TrackCreate(artist="Artist", title="Title", album=album).album is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("USUG11904206", "USUG11904206"),
        ("usug11904206", "USUG11904206"),
        ("  USUG11904206  ", "USUG11904206"),
        ("US-UG1-19-04206", "USUG11904206"),
        ("us-ug1-19-04206", "USUG11904206"),
        ("FR9W11100001", "FR9W11100001"),
    ],
)
def test_valid_isrc_is_normalized(raw, expected) -> None:
    assert TrackCreate(artist="Artist", title="Title", isrc=raw).isrc == expected


@pytest.mark.parametrize(
    "isrc",
    [
        "",
        "   ",
        "USUG1190420",  # 11 characters
        "USUG119042061",  # 13 characters
        "1SUG11904206",  # country code must be letters
        "USU-G11904206",  # misplaced hyphen
        "USUG1AB04206",  # year must be digits
        "USUG1190420X",  # designation must be digits
        "US UG1 19 04206",  # spaces are not a valid separator
        "USUG1_1904206",
        "ÜSUG11904206",
    ],
)
def test_invalid_isrc_is_rejected(isrc) -> None:
    with pytest.raises(ValidationError, match="ISRC"):
        TrackCreate(artist="Artist", title="Title", isrc=isrc)


def test_non_string_isrc_is_rejected() -> None:
    with pytest.raises(ValidationError, match="ISRC"):
        TrackCreate(artist="Artist", title="Title", isrc=123456789012)


def test_batch_request_validates_each_track() -> None:
    with pytest.raises(ValidationError):
        BatchTrackRequest(
            tracks=[
                {"artist": "The Weeknd", "title": "Blinding Lights"},
                {"artist": "   ", "title": "Blinding Lights"},
            ]
        )


def test_batch_request_normalizes_isrc() -> None:
    batch = BatchTrackRequest(
        tracks=[{"artist": "A", "title": "B", "isrc": "us-ug1-19-04206"}]
    )

    assert batch.tracks[0].isrc == "USUG11904206"

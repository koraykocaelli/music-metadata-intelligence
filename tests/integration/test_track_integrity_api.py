import pytest
from sqlalchemy.exc import IntegrityError

from app.models.track import Track
from app.repositories import track as track_repository


def _create(client, **payload):
    return client.post("/api/v1/tracks", json=payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"artist": "   ", "title": "Blinding Lights"},
        {"artist": "The Weeknd", "title": ""},
        {"artist": "!!!", "title": "Blinding Lights"},
        {"artist": "The Weeknd", "title": "(Official Audio)"},
        {"artist": "The Weeknd", "title": "Blinding Lights", "isrc": "INVALID"},
        {"artist": "The Weeknd", "title": "Blinding Lights", "isrc": "USUG1190420X"},
    ],
)
def test_create_track_rejects_invalid_input(client, payload) -> None:
    response = _create(client, **payload)

    assert response.status_code == 422
    assert client.get("/api/v1/tracks").json() == []


@pytest.mark.parametrize("payload", [{"artist": "!!!", "title": "???"}])
def test_similar_rejects_input_that_normalizes_to_empty(client, payload) -> None:
    response = client.post("/api/v1/tracks/similar", json=payload)

    assert response.status_code == 422


def test_create_track_trims_and_normalizes_isrc(client) -> None:
    response = _create(
        client,
        artist="  The Weeknd ",
        title=" Blinding Lights\t",
        album="   ",
        isrc=" us-ug1-19-04206 ",
    )

    assert response.status_code == 201

    data = response.json()

    assert data["artist"] == "The Weeknd"
    assert data["title"] == "Blinding Lights"
    assert data["album"] is None
    assert data["isrc"] == "USUG11904206"


def test_duplicate_isrc_is_detected_across_formats(client) -> None:
    assert _create(
        client, artist="The Weeknd", title="Blinding Lights", isrc="USUG11904206"
    ).status_code == 201

    response = _create(
        client, artist="Someone", title="Something", isrc="us-ug1-19-04206"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A track with this ISRC already exists."


def test_similar_finds_isrc_match_with_hyphenated_input(client) -> None:
    _create(client, artist="The Weeknd", title="Blinding Lights", isrc="USUG11904206")

    response = client.post(
        "/api/v1/tracks/similar",
        json={"artist": "Wrong", "title": "Wrong", "isrc": "US-UG1-19-04206"},
    )

    assert response.status_code == 200
    assert response.json()[0]["match_method"] == "isrc"


def test_multiple_tracks_without_isrc_are_allowed(client) -> None:
    assert _create(client, artist="Artist A", title="Song A").status_code == 201
    assert _create(client, artist="Artist B", title="Song B").status_code == 201

    assert len(client.get("/api/v1/tracks").json()) == 2


def test_unrelated_non_latin_tracks_are_not_duplicates(client) -> None:
    # Previously both normalized to empty strings and the second got a 409.
    first = _create(client, artist="Кино", title="Группа крови")
    second = _create(client, artist="宇多田ヒカル", title="First Love")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["normalized_artist"] == "кино"
    assert second.json()["normalized_artist"] == "宇多田ヒカル"


def test_non_latin_duplicate_metadata_is_detected(client) -> None:
    assert _create(client, artist="Кино", title="Группа крови").status_code == 201

    response = _create(client, artist="КИНО", title="Группа Крови (Official Audio)")

    assert response.status_code == 409


def test_similar_does_not_match_unrelated_non_latin_track(client) -> None:
    _create(client, artist="宇多田ヒカル", title="First Love")

    response = client.post(
        "/api/v1/tracks/similar",
        json={"artist": "Кино", "title": "Группа крови"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_database_rejects_duplicate_isrc(db_session) -> None:
    db_session.add(Track(artist="A", title="One", isrc="USUG11904206"))
    db_session.flush()

    db_session.add(Track(artist="B", title="Two", isrc="USUG11904206"))

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_concurrent_duplicate_isrc_returns_409_and_rolls_back(
    client,
    monkeypatch,
) -> None:
    assert _create(
        client, artist="The Weeknd", title="Blinding Lights", isrc="USUG11904206"
    ).status_code == 201

    # Simulate a race: the application-level pre-check sees no existing row,
    # so only the database unique index can stop the duplicate insert.
    monkeypatch.setattr(
        track_repository,
        "get_track_by_isrc",
        lambda db, isrc: None,
    )

    response = _create(
        client, artist="Other Artist", title="Other Title", isrc="USUG11904206"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A track with this ISRC already exists."

    # The session was rolled back safely and remains usable.
    tracks = client.get("/api/v1/tracks").json()

    assert len(tracks) == 1
    assert tracks[0]["artist"] == "The Weeknd"

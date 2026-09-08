def test_create_track(client):
    response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "Daft Punk",
            "title": "One More Time",
            "album": "Discovery",
            "isrc": "GBDUW0000053",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["artist"] == "Daft Punk"
    assert data["title"] == "One More Time"
    assert data["album"] == "Discovery"
    assert data["isrc"] == "GBDUW0000053"
    assert data["normalized_artist"] == "daft punk"
    assert data["normalized_title"] == "one more time"


def test_get_tracks(client):
    create_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "Justice",
            "title": "D.A.N.C.E.",
            "album": "Cross",
            "isrc": "FR4EU0700001",
        },
    )

    assert create_response.status_code == 201

    response = client.get("/api/v1/tracks")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["artist"] == "Justice"
    assert data[0]["title"] == "D.A.N.C.E."
    assert data[0]["normalized_artist"] == "justice"
    assert data[0]["normalized_title"] == "d a n c e"

def test_get_track_by_id(client):
    create_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "Kavinsky",
            "title": "Nightcall",
            "album": "OutRun",
            "isrc": "FR9W11100001",
        },
    )

    assert create_response.status_code == 201

    created_track = create_response.json()
    track_id = created_track["id"]

    response = client.get(f"/api/v1/tracks/{track_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == track_id
    assert data["artist"] == "Kavinsky"
    assert data["title"] == "Nightcall"
    assert data["album"] == "OutRun"
    assert data["normalized_artist"] == "kavinsky"
    assert data["normalized_title"] == "nightcall"

def test_get_track_by_id_returns_404_when_track_does_not_exist(client):
    response = client.get("/api/v1/tracks/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Track not found"

def test_find_similar_tracks(client):
    create_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "The Weeknd",
            "title": "Blinding Lights",
            "album": "After Hours",
            "isrc": "USUG11904206",
        },
    )

    assert create_response.status_code == 201

    response = client.post(
        "/api/v1/tracks/similar",
        json={
            "artist": "The Weekend",
            "title": "Blinding Light",
            "album": None,
            "isrc": None,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    match = data[0]

    assert match["artist"] == "The Weeknd"
    assert match["title"] == "Blinding Lights"
    assert match["score"] > 90
    assert match["classification"] == "high_confidence"

def test_create_track_returns_409_for_duplicate_isrc(client):
    first_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "Daft Punk",
            "title": "One More Time",
            "album": "Discovery",
            "isrc": "GBDUW0000053",
        },
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "Daft Punk",
            "title": "Something Else",
            "album": "Discovery",
            "isrc": "GBDUW0000053",
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == (
        "A track with this ISRC already exists."
    )


def test_create_track_returns_409_for_duplicate_normalized_metadata(client):
    first_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "The Weeknd",
            "title": "Blinding Lights",
            "album": "After Hours",
            "isrc": "USUG11904206",
        },
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/tracks",
        json={
            "artist": "THE WEEKND!!!",
            "title": "Blinding Lights (Official Audio)",
            "album": "After Hours",
            "isrc": "USUG11999999",
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == (
        "A track with the same normalized artist and title already exists."
    )


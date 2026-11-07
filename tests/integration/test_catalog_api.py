import csv
import io
import json
from pathlib import Path

import pytest

from app.services import catalog as catalog_service

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
MATCH_URL = "/api/v1/catalog/match"
EXPORT_URL = "/api/v1/catalog/match/export"
CSV_TYPE = {"Content-Type": "text/csv; charset=utf-8"}
JSON_TYPE = {"Content-Type": "application/json"}

EXPECTED_EXAMPLE_STATUSES = [
    "matched",  # exact ISRC despite "(Official Audio)"
    "matched",  # artist typo, high-confidence metadata match
    "review",  # missing "The" in artist name
    "unmatched",
    "invalid",  # whitespace-only artist
    "invalid",  # malformed ISRC
    "matched",  # case and accent differences ("SILVER ÉCHO")
    "unmatched",  # formula-like artist (sanitized in CSV export)
]


@pytest.fixture
def reference_catalog(client):
    tracks = json.loads((EXAMPLES / "reference_tracks.json").read_text(encoding="utf-8"))

    created = []
    for track in tracks:
        response = client.post("/api/v1/tracks", json=track)
        assert response.status_code == 201
        created.append(response.json())

    return {track["title"]: track for track in created}


def _track_snapshot(client):
    return client.get("/api/v1/tracks").json()


# --- End-to-end with the example catalogs ---------------------------------


@pytest.mark.parametrize(
    ("filename", "headers", "line_numbers"),
    [
        ("catalog.csv", CSV_TYPE, [2, 3, 4, 5, 6, 7, 8, 9]),
        ("catalog.json", JSON_TYPE, [None] * 8),
    ],
)
def test_example_catalog_is_matched_in_input_order(
    client, reference_catalog, filename, headers, line_numbers
) -> None:
    before = _track_snapshot(client)

    response = client.post(
        MATCH_URL,
        content=(EXAMPLES / filename).read_bytes(),
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()
    results = data["results"]

    assert [r["status"] for r in results] == EXPECTED_EXAMPLE_STATUSES
    assert [r["input_index"] for r in results] == list(range(8))
    assert [r["line_number"] for r in results] == line_numbers
    assert data["summary"] == {
        "total": 8,
        "matched": 3,
        "review": 1,
        "unmatched": 2,
        "invalid": 2,
    }

    isrc_match = results[0]["matches"][0]
    assert isrc_match["match_method"] == "isrc"
    assert isrc_match["score"] == 100.0
    assert isrc_match["track_id"] == reference_catalog["Midnight Signal"]["id"]

    typo_match = results[1]["matches"][0]
    assert typo_match["match_method"] == "metadata"
    assert typo_match["classification"] == "high_confidence"
    assert typo_match["track_id"] == reference_catalog["Paper Satellites"]["id"]

    review_match = results[2]["matches"][0]
    assert review_match["classification"] == "review"
    assert 80 <= review_match["score"] < 95

    assert results[3]["matches"] == []
    assert results[4]["errors"][0]["field"] == "artist"
    assert results[5]["errors"][0]["field"] == "isrc"
    assert results[5]["isrc"] == "BAD-ISRC"
    assert results[6]["artist"] == "SILVER ÉCHO"
    assert results[6]["matches"][0]["artist"] == "Silver Echo"

    # Read-only: the reference catalog is unchanged.
    assert _track_snapshot(client) == before


def test_catalog_results_match_batch_api_for_same_rows(client, reference_catalog) -> None:
    rows = [
        {"artist": "Luna Vael", "title": "Paper Satellites"},
        {"artist": "Glass Orchard", "title": "Slow Motion Summer"},
        {"artist": "Unknown Collective", "title": "Brand New Song"},
    ]

    batch = client.post("/api/v1/tracks/batch/match", json={"tracks": rows}).json()
    catalog = client.post(MATCH_URL, content=json.dumps(rows), headers=JSON_TYPE).json()

    for batch_row, catalog_row in zip(batch["results"], catalog["results"]):
        assert catalog_row["status"] == batch_row["status"]
        assert catalog_row["matches"] == batch_row["matches"]


def test_upload_never_inserts_tracks(client) -> None:
    response = client.post(
        MATCH_URL,
        content="artist,title,isrc\nNew Artist,New Song,ZZNEW2600001\n".encode(),
        headers=CSV_TYPE,
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "unmatched"
    assert _track_snapshot(client) == []


def test_unicode_csv_with_bom_and_quoted_multiline(client, reference_catalog) -> None:
    # Dedicated non-Latin reference track (the example catalog is English-only).
    created = client.post(
        "/api/v1/tracks",
        json={"artist": "Северный Свет", "title": "Тихая гавань", "isrc": "ZZSVS2600003"},
    )
    assert created.status_code == 201

    content = (
        "﻿Artist,Title\n"
        "Северный Свет,\"Тихая\nгавань\"\n"
        "宇多田ヒカル,First Love\n"
    ).encode("utf-8")

    response = client.post(MATCH_URL, content=content, headers=CSV_TYPE)

    assert response.status_code == 200

    results = response.json()["results"]

    assert results[0]["title"] == "Тихая\nгавань"
    assert results[0]["status"] == "matched"
    assert results[0]["matches"][0]["artist"] == "Северный Свет"
    assert results[0]["matches"][0]["match_method"] == "metadata"
    assert results[1]["artist"] == "宇多田ヒカル"
    assert results[1]["status"] == "unmatched"


def test_ignored_columns_are_reported(client) -> None:
    response = client.post(
        MATCH_URL,
        content=b"artist,title,source_id\nA,B,1\n",
        headers=CSV_TYPE,
    )

    assert response.json()["ignored_columns"] == ["source_id"]


# --- File-level validation ------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "content", "status_code", "detail"),
    [
        ({}, b"artist,title\nA,B\n", 415, "Content-Type"),
        ({"Content-Type": "text/plain"}, b"artist,title\nA,B\n", 415, "Content-Type"),
        ({"Content-Type": "text/csv; charset=latin-1"}, b"artist,title\nA,B\n", 415, "UTF-8"),
        (CSV_TYPE, b"", 422, "empty"),
        (CSV_TYPE, b"artist,title\n", 422, "no records"),
        (CSV_TYPE, b"artist,album\nA,B\n", 422, "missing required column"),
        (CSV_TYPE, b"artist,title\n\xff\xfeA,B\n", 422, "UTF-8"),
        (CSV_TYPE, b"artist,title\nA\x00,B\n", 422, "NUL"),
        (CSV_TYPE, b"artist,title\n\"open,B\n", 422, "Malformed CSV"),
        (JSON_TYPE, b"[{\"artist\": \"A\"", 422, "Malformed JSON"),
        (JSON_TYPE, b"{\"artist\": \"A\"}", 422, "array"),
        (JSON_TYPE, b"\x89PNG\r\n\x1a\n\x00\x00", 422, "UTF-8"),
    ],
)
def test_invalid_files_are_rejected(client, headers, content, status_code, detail) -> None:
    response = client.post(MATCH_URL, content=content, headers=headers)

    assert response.status_code == status_code
    assert detail in response.json()["detail"]


def test_row_limit_is_enforced(client) -> None:
    rows = "".join(f"Artist {i},Song {i}\n" for i in range(catalog_service.MAX_CATALOG_ROWS + 1))

    response = client.post(MATCH_URL, content=("artist,title\n" + rows).encode(), headers=CSV_TYPE)

    assert response.status_code == 422
    assert "more than 1000 records" in response.json()["detail"]


def test_oversized_upload_is_rejected_by_content_length(client) -> None:
    content = b"artist,title\n" + b"A,B\n" * (catalog_service.MAX_UPLOAD_BYTES // 4 + 1)

    response = client.post(MATCH_URL, content=content, headers=CSV_TYPE)

    assert response.status_code == 413


def test_oversized_streamed_upload_without_content_length_is_rejected(client) -> None:
    chunk = b"A,B\n" * 16384  # 64 KiB

    def body():
        # A generator body is sent chunked, without a Content-Length header,
        # so only the streaming byte counter can reject it.
        yield b"artist,title\n"
        for _ in range(64):  # 4 MiB in total
            yield chunk

    response = client.post(MATCH_URL, content=body(), headers=CSV_TYPE)

    assert response.status_code == 413


def test_invalid_content_length_is_rejected(client) -> None:
    response = client.post(
        MATCH_URL,
        content=b"artist,title\nA,B\n",
        headers={**CSV_TYPE, "Content-Length": "-5"},
    )

    assert response.status_code in (400, 422)


def test_upload_at_size_limit_is_accepted(client) -> None:
    header = b"artist,title\n"
    row = b"Artist,Song\n"
    rows = row * catalog_service.MAX_CATALOG_ROWS
    # Blank lines are not records, so they pad the file to the exact limit.
    padding = b"\n" * (catalog_service.MAX_UPLOAD_BYTES - len(header) - len(rows))
    content = header + rows + padding

    assert len(content) == catalog_service.MAX_UPLOAD_BYTES

    response = client.post(MATCH_URL, content=content, headers=CSV_TYPE)

    assert response.status_code == 200
    assert response.json()["summary"]["total"] == catalog_service.MAX_CATALOG_ROWS


# --- Exports --------------------------------------------------------------


def test_csv_export_download(client, reference_catalog) -> None:
    response = client.post(
        EXPORT_URL,
        params={"format": "csv"},
        content=(EXAMPLES / "catalog.csv").read_bytes(),
        headers=CSV_TYPE,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="catalog_match_results.csv"'
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(b"\xef\xbb\xbf")

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))

    assert [row["status"] for row in rows] == EXPECTED_EXAMPLE_STATUSES
    assert [row["input_index"] for row in rows] == [str(i) for i in range(8)]
    assert rows[0]["best_match_method"] == "isrc"
    assert rows[0]["best_match_score"] == "100.0"
    assert rows[6]["artist"] == "SILVER ÉCHO"
    assert rows[7]["artist"] == "'=HYPERLINK(\"http://example.com\")"
    assert "isrc:" in rows[5]["errors"]

    for row in rows:
        for value in row.values():
            assert not value or value[0] not in "=+-@\t\r"


def test_json_export_download_matches_match_endpoint(client, reference_catalog) -> None:
    content = (EXAMPLES / "catalog.json").read_bytes()

    exported = client.post(
        EXPORT_URL, params={"format": "json"}, content=content, headers=JSON_TYPE
    )
    matched = client.post(MATCH_URL, content=content, headers=JSON_TYPE)

    assert exported.status_code == 200
    assert exported.headers["content-disposition"] == (
        'attachment; filename="catalog_match_results.json"'
    )
    assert exported.json() == matched.json()


@pytest.mark.parametrize("params", [{}, {"format": "xlsx"}, {"format": "../../etc/passwd"}])
def test_export_requires_supported_format(client, params) -> None:
    response = client.post(
        EXPORT_URL, params=params, content=b"artist,title\nA,B\n", headers=CSV_TYPE
    )

    assert response.status_code == 422

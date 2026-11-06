import csv
import io
import json

import pytest

from app.schemas.catalog import CatalogFormat, CatalogRowStatus
from app.schemas.track import MatchClassification, MatchMethod
from app.services import catalog as catalog_service
from app.services.catalog import (
    CatalogFileError,
    decode_catalog,
    detect_catalog_format,
    export_results_csv,
    export_results_json,
    match_catalog,
    parse_catalog,
    parse_csv_catalog,
    parse_json_catalog,
    sanitize_csv_cell,
)


# --- Content type ---------------------------------------------------------


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("text/csv", CatalogFormat.CSV),
        ("text/csv; charset=utf-8", CatalogFormat.CSV),
        ("TEXT/CSV; charset=\"UTF-8\"", CatalogFormat.CSV),
        ("application/json", CatalogFormat.JSON),
        ("application/json; charset=utf8", CatalogFormat.JSON),
    ],
)
def test_supported_content_types(content_type, expected) -> None:
    assert detect_catalog_format(content_type) == expected


@pytest.mark.parametrize(
    "content_type",
    [
        None,
        "",
        "text/plain",
        "application/vnd.ms-excel",
        "multipart/form-data; boundary=x",
        "application/octet-stream",
        "text/csv; charset=latin-1",
        "application/json; charset=utf-16",
    ],
)
def test_unsupported_content_types_are_rejected(content_type) -> None:
    with pytest.raises(CatalogFileError) as error:
        detect_catalog_format(content_type)

    assert error.value.status_code == 415


# --- Decoding -------------------------------------------------------------


def test_decode_strips_utf8_bom() -> None:
    assert decode_catalog("﻿artist,title".encode("utf-8")) == "artist,title"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"  \n\t ", "empty"),
        (b"artist,title\n\xff\xfe,x", "UTF-8"),
        ("artist,title".encode("utf-16"), "UTF-8"),
        (b"artist,title\nA\x00,B", "NUL"),
    ],
)
def test_invalid_content_is_rejected(content, message) -> None:
    with pytest.raises(CatalogFileError, match=message):
        decode_catalog(content)


# --- CSV parsing ----------------------------------------------------------


def test_csv_parsing_preserves_order_and_line_numbers() -> None:
    parsed = parse_csv_catalog(
        "artist,title,album,isrc\n"
        "A,One,,\n"
        "\n"
        '"B","Two\nlines",Album,USUG11904206\n'
        "C,Three,,\n"
    )

    assert [r.input_index for r in parsed.records] == [0, 1, 2]
    assert [r.line_number for r in parsed.records] == [2, 4, 6]
    assert parsed.records[0].values == {
        "artist": "A",
        "title": "One",
        "album": None,
        "isrc": None,
    }
    assert parsed.records[1].values["title"] == "Two\nlines"


def test_csv_header_is_case_and_whitespace_insensitive() -> None:
    parsed = parse_csv_catalog(" Artist , TITLE \nA,B\n")

    assert parsed.records[0].values == {"artist": "A", "title": "B"}


def test_csv_unknown_columns_are_ignored_and_reported() -> None:
    parsed = parse_csv_catalog("artist,title,source_id,genre\nA,B,1,pop\n")

    assert parsed.ignored_columns == ["source_id", "genre"]
    assert "source_id" not in parsed.records[0].values


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("artist,album\nA,B\n", "missing required column\\(s\\): title"),
        ("name;song\nA;B\n", "missing required column\\(s\\): artist, title"),
        ("artist,title,artist\nA,B,C\n", "duplicate columns: artist"),
        ("artist,,title\nA,B,C\n", "empty column name"),
        ("artist,title\n\"unterminated,B\n", "Malformed CSV"),
        ("artist,title\n\"A\"b,C\n", "Malformed CSV"),
        (",".join(["artist", "title"] + [f"c{i}" for i in range(60)]), "more than 50 columns"),
    ],
)
def test_invalid_csv_files_are_rejected(text, message) -> None:
    with pytest.raises(CatalogFileError, match=message):
        parse_csv_catalog(text)


def test_csv_row_with_wrong_field_count_is_kept_as_invalid() -> None:
    parsed = parse_csv_catalog("artist,title,album\nA,B\nC,D,E,F\n")

    assert len(parsed.records) == 2
    assert "2 fields but the header has 3" in parsed.records[0].errors[0].message
    assert "4 fields but the header has 3" in parsed.records[1].errors[0].message


def test_csv_row_limit_is_enforced() -> None:
    rows = "".join(f"A{i},T{i}\n" for i in range(catalog_service.MAX_CATALOG_ROWS + 1))

    with pytest.raises(CatalogFileError, match="more than 1000 records"):
        parse_csv_catalog("artist,title\n" + rows)


def test_csv_at_row_limit_is_accepted() -> None:
    rows = "".join(f"A{i},T{i}\n" for i in range(catalog_service.MAX_CATALOG_ROWS))

    assert len(parse_csv_catalog("artist,title\n" + rows).records) == 1000


def test_header_only_file_has_no_records() -> None:
    with pytest.raises(CatalogFileError, match="no records"):
        parse_catalog(CatalogFormat.CSV, b"artist,title\n")


# --- JSON parsing ---------------------------------------------------------


def test_json_array_and_tracks_object_are_supported() -> None:
    items = [{"artist": "A", "title": "B"}, {"artist": "C", "title": "D"}]

    for payload in (items, {"tracks": items}):
        parsed = parse_json_catalog(json.dumps(payload))

        assert [r.values["artist"] for r in parsed.records] == ["A", "C"]
        assert [r.line_number for r in parsed.records] == [None, None]


def test_json_unknown_keys_are_reported() -> None:
    parsed = parse_json_catalog('[{"artist": "A", "title": "B", "id": 7}]')

    assert parsed.ignored_columns == ["id"]
    assert parsed.records[0].values == {"artist": "A", "title": "B"}


def test_json_non_object_records_are_kept_as_invalid() -> None:
    parsed = parse_json_catalog('[{"artist": "A", "title": "B"}, "oops", 3, null]')

    assert len(parsed.records) == 4
    assert [bool(r.errors) for r in parsed.records] == [False, True, True, True]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[{\"artist\": \"A\",}]", "Malformed JSON"),
        ("{\"artist\": \"A\", \"title\": \"B\"}", "array of track objects"),
        ("\"just a string\"", "array of track objects"),
        ("{\"tracks\": {\"artist\": \"A\"}}", "array of track objects"),
        ("[{\"artist\": NaN, \"title\": \"B\"}]", "Invalid JSON"),
        pytest.param("[" * 100000 + "]" * 100000, "JSON", id="deeply-nested"),
    ],
)
def test_invalid_json_files_are_rejected(text, message) -> None:
    with pytest.raises(CatalogFileError, match=message):
        parse_json_catalog(text)


def test_json_row_limit_is_enforced() -> None:
    items = [{"artist": "A", "title": "B"}] * (catalog_service.MAX_CATALOG_ROWS + 1)

    with pytest.raises(CatalogFileError, match="more than 1000 records"):
        parse_json_catalog(json.dumps(items))


# --- Matching orchestration (matching engine stubbed) ---------------------


def _fake_matches(count: int, score: float = 97.0) -> list[dict[str, object]]:
    return [
        {
            "track_id": index + 1,
            "artist": f"Artist {index}",
            "title": f"Title {index}",
            "score": score - index,
            "classification": (
                MatchClassification.HIGH_CONFIDENCE
                if score - index >= 95
                else MatchClassification.REVIEW
            ),
            "match_method": MatchMethod.METADATA,
        }
        for index in range(count)
    ]


@pytest.fixture
def stub_engine(monkeypatch):
    responses = {
        "matched": _fake_matches(1, 97.0),
        "review": _fake_matches(1, 85.0),
        "unmatched": [],
        "many": _fake_matches(8, 99.0),
    }
    calls = []

    def fake_find_similar_tracks(db, track_data):
        calls.append(track_data)
        return responses.get(track_data.title.lower(), [])

    monkeypatch.setattr(catalog_service, "find_similar_tracks", fake_find_similar_tracks)

    return calls


def test_match_catalog_classifies_rows_in_input_order(stub_engine) -> None:
    content = (
        "artist,title,isrc\n"
        "A,Review,\n"
        " ,Matched,\n"
        "B,Matched,us-ug1-19-04206\n"
        "C,Unmatched,\n"
        "D,Matched,INVALID\n"
    ).encode("utf-8")

    result = match_catalog(None, CatalogFormat.CSV, content)

    assert [r.status for r in result.results] == [
        CatalogRowStatus.REVIEW,
        CatalogRowStatus.INVALID,
        CatalogRowStatus.MATCHED,
        CatalogRowStatus.UNMATCHED,
        CatalogRowStatus.INVALID,
    ]
    assert [r.input_index for r in result.results] == [0, 1, 2, 3, 4]
    assert result.summary.model_dump() == {
        "total": 5,
        "matched": 1,
        "review": 1,
        "unmatched": 1,
        "invalid": 2,
    }
    # Invalid rows never reach the matching engine.
    assert len(stub_engine) == 3
    # Valid rows are returned cleaned/normalized.
    assert result.results[2].isrc == "USUG11904206"


def test_invalid_rows_keep_raw_values_and_field_errors(stub_engine) -> None:
    result = match_catalog(
        None,
        CatalogFormat.JSON,
        b'[{"artist": "!!!", "title": 42, "isrc": "BAD"}]',
    )

    row = result.results[0]

    assert row.status == CatalogRowStatus.INVALID
    assert row.artist == "!!!"
    assert row.title == "42"
    assert row.isrc == "BAD"
    assert {error.field for error in row.errors} == {"artist", "title", "isrc"}
    assert all(not e.message.startswith("Value error") for e in row.errors)


def test_missing_required_json_fields_are_reported(stub_engine) -> None:
    result = match_catalog(None, CatalogFormat.JSON, b'[{"album": "X"}]')

    assert {(e.field, e.message) for e in result.results[0].errors} == {
        ("artist", "Field required"),
        ("title", "Field required"),
    }


def test_candidates_per_row_are_capped(stub_engine) -> None:
    result = match_catalog(None, CatalogFormat.CSV, b"artist,title\nA,Many\n")

    assert len(result.results[0].matches) == catalog_service.MAX_CANDIDATES_PER_ROW
    assert result.results[0].status == CatalogRowStatus.MATCHED


def test_unicode_metadata_is_preserved(stub_engine) -> None:
    content = "﻿artist,title\nКино,Unmatched\n宇多田ヒカル,Unmatched\n".encode("utf-8")

    result = match_catalog(None, CatalogFormat.CSV, content)

    assert [r.artist for r in result.results] == ["Кино", "宇多田ヒカル"]
    assert all(r.status == CatalogRowStatus.UNMATCHED for r in result.results)


# --- Export ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("+SUM(A1)", "'+SUM(A1)"),
        ("-2+3", "'-2+3"),
        ("@cmd", "'@cmd"),
        ("\t=x", "'\t=x"),
        ("\r=x", "'\r=x"),
        ("  =x", "'  =x"),
        ("＝1+1", "'＝1+1"),
        ("The Weeknd", "The Weeknd"),
        ("", ""),
        (42, 42),
        (95.5, 95.5),
    ],
)
def test_sanitize_csv_cell(value, expected) -> None:
    assert sanitize_csv_cell(value) == expected


def _export_rows(result) -> list[dict[str, str]]:
    text = export_results_csv(result).decode("utf-8-sig")

    return list(csv.DictReader(io.StringIO(text, newline="")))


def test_csv_export_is_ordered_sanitized_and_utf8(stub_engine) -> None:
    content = (
        'artist,title\n'
        '"=HYPERLINK(""http://example.com"")",Unmatched\n'
        'Кино,Matched\n'
        ' ,Review\n'
    ).encode("utf-8")
    result = match_catalog(None, CatalogFormat.CSV, content)

    raw = export_results_csv(result)
    rows = _export_rows(result)

    assert raw.startswith(b"\xef\xbb\xbf")
    assert list(rows[0]) == list(catalog_service.CSV_EXPORT_COLUMNS)
    assert [row["input_index"] for row in rows] == ["0", "1", "2"]
    assert rows[0]["artist"] == "'=HYPERLINK(\"http://example.com\")"
    assert rows[0]["status"] == "unmatched"
    assert rows[1]["artist"] == "Кино"
    assert rows[1]["best_match_track_id"] == "1"
    assert rows[1]["best_match_score"] == "97.0"
    assert rows[1]["best_match_method"] == "metadata"
    assert rows[2]["status"] == "invalid"
    assert rows[2]["errors"].startswith("artist: ")
    assert rows[2]["line_number"] == "4"


def test_csv_export_has_no_unescaped_formula_cells(stub_engine) -> None:
    content = (
        "artist,title,album\n"
        "@evil,Unmatched,=cmd|' /C calc'!A0\n"
        "-1+2,+Unmatched,\n"
    ).encode("utf-8")
    result = match_catalog(None, CatalogFormat.CSV, content)

    for row in _export_rows(result):
        for value in row.values():
            assert not value or value[0] not in "=+-@\t\r"


def test_json_export_matches_response(stub_engine) -> None:
    result = match_catalog(None, CatalogFormat.CSV, "artist,title\nКино,Matched\n".encode())

    exported = json.loads(export_results_json(result).decode("utf-8"))

    assert exported == json.loads(result.model_dump_json())
    assert exported["results"][0]["artist"] == "Кино"

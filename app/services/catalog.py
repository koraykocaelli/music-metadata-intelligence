"""Catalog file matching: parse an uploaded CSV/JSON catalog, validate each
record with the existing TrackCreate rules, and match valid records with the
existing matching engine (find_similar_tracks).

Processing is read-only: nothing is inserted into the reference catalog and
uploaded content is never written to disk.
"""

import csv
import io
import json
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.schemas.catalog import (
    CatalogFormat,
    CatalogMatchResponse,
    CatalogMatchSummary,
    CatalogRowError,
    CatalogRowResult,
    CatalogRowStatus,
)
from app.schemas.track import MatchCandidate, TrackCreate
from app.services.track import determine_match_status, find_similar_tracks


MAX_UPLOAD_BYTES = 1024 * 1024  # 1 MiB
MAX_CATALOG_ROWS = 1000
MAX_CSV_COLUMNS = 50
MAX_CANDIDATES_PER_ROW = 5
MAX_REPORTED_NAME_LENGTH = 64
MAX_ECHO_LENGTH = 255

REQUIRED_COLUMNS = ("artist", "title")
OPTIONAL_COLUMNS = ("album", "isrc")
KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

SUPPORTED_MEDIA_TYPES = {
    "text/csv": CatalogFormat.CSV,
    "application/json": CatalogFormat.JSON,
}
SUPPORTED_CHARSETS = {"utf-8", "utf8"}

# Characters that make spreadsheet applications interpret a cell as a formula
# (OWASP CSV injection guidance), including full-width variants.
FORMULA_TRIGGER_CHARACTERS = frozenset("=+-@\t\r\n＝＋－＠")

CSV_EXPORT_COLUMNS = (
    "input_index",
    "line_number",
    "artist",
    "title",
    "album",
    "isrc",
    "status",
    "best_match_track_id",
    "best_match_artist",
    "best_match_title",
    "best_match_score",
    "best_match_classification",
    "best_match_method",
    "candidate_count",
    "errors",
)


class CatalogFileError(Exception):
    """The uploaded file as a whole cannot be processed."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class RawRecord:
    input_index: int
    line_number: int | None
    values: dict[str, object]
    errors: list[CatalogRowError] = field(default_factory=list)


@dataclass
class ParsedCatalog:
    records: list[RawRecord]
    ignored_columns: list[str]


# --- Format detection and decoding ----------------------------------------


def detect_catalog_format(content_type: str | None) -> CatalogFormat:
    if not content_type:
        raise CatalogFileError(
            "Missing Content-Type. Use 'text/csv' or 'application/json'.",
            status_code=415,
        )

    media_type, _, parameters = content_type.partition(";")
    catalog_format = SUPPORTED_MEDIA_TYPES.get(media_type.strip().lower())

    if catalog_format is None:
        raise CatalogFileError(
            "Unsupported Content-Type. Use 'text/csv' or 'application/json'.",
            status_code=415,
        )

    for parameter in parameters.split(";"):
        name, _, value = parameter.partition("=")

        if name.strip().lower() == "charset":
            if value.strip().strip('"').lower() not in SUPPORTED_CHARSETS:
                raise CatalogFileError(
                    "Unsupported charset. Catalog files must be UTF-8.",
                    status_code=415,
                )

    return catalog_format


def decode_catalog(content: bytes) -> str:
    if not content.strip():
        raise CatalogFileError("The uploaded file is empty.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CatalogFileError(
            f"The file is not valid UTF-8 (invalid byte at offset {error.start})."
        ) from error

    if "\x00" in text:
        raise CatalogFileError(
            "The file contains NUL bytes; binary files are not supported."
        )

    return text


def _short(name: str) -> str:
    if len(name) <= MAX_REPORTED_NAME_LENGTH:
        return name

    return name[:MAX_REPORTED_NAME_LENGTH] + "…"


def _check_row_limit(count: int) -> None:
    if count > MAX_CATALOG_ROWS:
        raise CatalogFileError(
            f"The file contains more than {MAX_CATALOG_ROWS} records."
        )


# --- Parsing --------------------------------------------------------------


def parse_csv_catalog(text: str) -> ParsedCatalog:
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)

    try:
        header = next(reader, None) or []
        columns = [column.strip().lower() for column in header]

        if len(columns) > MAX_CSV_COLUMNS:
            raise CatalogFileError(
                f"The CSV header has more than {MAX_CSV_COLUMNS} columns."
            )

        if any(not column for column in columns):
            raise CatalogFileError("The CSV header contains an empty column name.")

        duplicates = sorted({c for c in columns if columns.count(c) > 1})
        if duplicates:
            raise CatalogFileError(
                "The CSV header contains duplicate columns: "
                + ", ".join(_short(c) for c in duplicates)
                + "."
            )

        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise CatalogFileError(
                "The CSV header is missing required column(s): "
                + ", ".join(missing)
                + ". Expected a comma-separated header such as "
                "'artist,title,album,isrc'."
            )

        ignored_columns = [_short(c) for c in columns if c not in KNOWN_COLUMNS]
        records: list[RawRecord] = []
        previous_line = reader.line_num

        for row in reader:
            start_line = previous_line + 1
            previous_line = reader.line_num

            if not row:
                # A completely empty line is not a record.
                continue

            _check_row_limit(len(records) + 1)

            values: dict[str, object] = {}
            for column, value in zip(columns, row):
                if column in KNOWN_COLUMNS:
                    # An empty optional cell means "not provided".
                    if column in OPTIONAL_COLUMNS and not value.strip():
                        values[column] = None
                    else:
                        values[column] = value

            errors: list[CatalogRowError] = []
            if len(row) != len(columns):
                errors.append(
                    CatalogRowError(
                        field=None,
                        message=(
                            f"Row has {len(row)} fields but the header has "
                            f"{len(columns)}."
                        ),
                    )
                )

            records.append(RawRecord(len(records), start_line, values, errors))
    except csv.Error as error:
        raise CatalogFileError(
            f"Malformed CSV near line {reader.line_num}: {error}."
        ) from error

    return ParsedCatalog(records=records, ignored_columns=ignored_columns)


def _reject_json_constant(name: str) -> None:
    raise ValueError(f"Invalid JSON constant: {name}")


def parse_json_catalog(text: str) -> ParsedCatalog:
    try:
        data = json.loads(text, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as error:
        raise CatalogFileError(
            f"Malformed JSON at line {error.lineno}, column {error.colno}: "
            f"{error.msg}."
        ) from error
    except (ValueError, RecursionError) as error:
        raise CatalogFileError(f"Invalid JSON: {error}.") from error

    if isinstance(data, dict) and set(data) == {"tracks"}:
        data = data["tracks"]

    if not isinstance(data, list):
        raise CatalogFileError(
            'JSON catalogs must be an array of track objects or an object '
            'of the form {"tracks": [...]}.'
        )

    _check_row_limit(len(data))

    records: list[RawRecord] = []
    ignored: dict[str, None] = {}

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            records.append(
                RawRecord(
                    index,
                    None,
                    {},
                    [CatalogRowError(field=None, message="Record must be a JSON object.")],
                )
            )
            continue

        for key in item:
            if key not in KNOWN_COLUMNS and len(ignored) < MAX_CSV_COLUMNS:
                ignored.setdefault(_short(str(key)), None)

        values = {key: item[key] for key in KNOWN_COLUMNS if key in item}
        records.append(RawRecord(index, None, values))

    return ParsedCatalog(records=records, ignored_columns=list(ignored))


def parse_catalog(catalog_format: CatalogFormat, content: bytes) -> ParsedCatalog:
    text = decode_catalog(content)

    if catalog_format == CatalogFormat.CSV:
        parsed = parse_csv_catalog(text)
    else:
        parsed = parse_json_catalog(text)

    if not parsed.records:
        raise CatalogFileError("The file contains no records.")

    return parsed


# --- Validation and matching ----------------------------------------------


def _clean_message(message: str) -> str:
    return message.removeprefix("Value error, ")


def validate_record(record: RawRecord) -> tuple[TrackCreate | None, list[CatalogRowError]]:
    if record.errors:
        return None, record.errors

    try:
        return TrackCreate.model_validate(record.values), []
    except ValidationError as error:
        return None, [
            CatalogRowError(
                field=str(detail["loc"][0]) if detail["loc"] else None,
                message=_clean_message(detail["msg"]),
            )
            for detail in error.errors()
        ]


def _echo(value: object) -> str | None:
    # Echo raw values of invalid records (bounded) so they are never lost.
    if value is None:
        return None

    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    return text[:MAX_ECHO_LENGTH]


def match_catalog(
    db: Session,
    catalog_format: CatalogFormat,
    content: bytes,
) -> CatalogMatchResponse:
    parsed = parse_catalog(catalog_format, content)

    results: list[CatalogRowResult] = []
    counts = {status: 0 for status in CatalogRowStatus}

    for record in parsed.records:
        track, errors = validate_record(record)

        if track is None:
            status = CatalogRowStatus.INVALID
            matches: list[dict[str, object]] = []
            artist = _echo(record.values.get("artist"))
            title = _echo(record.values.get("title"))
            album = _echo(record.values.get("album"))
            isrc = _echo(record.values.get("isrc"))
        else:
            # Same engine, thresholds and status rule as the batch API.
            matches = find_similar_tracks(db, track)
            status = CatalogRowStatus(determine_match_status(matches).value)
            artist, title, album, isrc = (
                track.artist,
                track.title,
                track.album,
                track.isrc,
            )

        counts[status] += 1
        results.append(
            CatalogRowResult(
                input_index=record.input_index,
                line_number=record.line_number,
                artist=artist,
                title=title,
                album=album,
                isrc=isrc,
                status=status,
                matches=[
                    MatchCandidate(**match)
                    for match in matches[:MAX_CANDIDATES_PER_ROW]
                ],
                errors=errors,
            )
        )

    return CatalogMatchResponse(
        input_format=catalog_format,
        ignored_columns=parsed.ignored_columns,
        summary=CatalogMatchSummary(
            total=len(results),
            matched=counts[CatalogRowStatus.MATCHED],
            review=counts[CatalogRowStatus.REVIEW],
            unmatched=counts[CatalogRowStatus.UNMATCHED],
            invalid=counts[CatalogRowStatus.INVALID],
        ),
        results=results,
    )


# --- Export ---------------------------------------------------------------


def sanitize_csv_cell(value: object) -> object:
    """Neutralize spreadsheet formula injection in exported text cells."""

    if isinstance(value, str) and value:
        stripped = value.lstrip(" ")

        if value[0] in FORMULA_TRIGGER_CHARACTERS or (
            stripped and stripped[0] in FORMULA_TRIGGER_CHARACTERS
        ):
            return "'" + value

    return value


def export_results_csv(response: CatalogMatchResponse) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CSV_EXPORT_COLUMNS)

    for row in response.results:
        best = row.matches[0] if row.matches else None
        values = [
            row.input_index,
            row.line_number,
            row.artist,
            row.title,
            row.album,
            row.isrc,
            row.status.value,
            best.track_id if best else None,
            best.artist if best else None,
            best.title if best else None,
            best.score if best else None,
            best.classification.value if best else None,
            best.match_method.value if best else None,
            len(row.matches),
            "; ".join(
                f"{error.field}: {error.message}" if error.field else error.message
                for error in row.errors
            ),
        ]
        writer.writerow(
            ["" if value is None else sanitize_csv_cell(value) for value in values]
        )

    # BOM so spreadsheet applications detect UTF-8 (non-Latin metadata).
    return buffer.getvalue().encode("utf-8-sig")


def export_results_json(response: CatalogMatchResponse) -> bytes:
    return response.model_dump_json(indent=2).encode("utf-8")

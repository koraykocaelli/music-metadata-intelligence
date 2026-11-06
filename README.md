# Music Metadata Intelligence

A backend-first music metadata processing and matching platform built with Python, FastAPI, PostgreSQL, and SQLAlchemy.

The project focuses on cleaning, normalizing, comparing, and matching inconsistent music metadata through a structured matching pipeline.

## Current Features

- Track creation and retrieval
- Metadata normalization and music-specific title cleaning
- Duplicate detection using ISRC and normalized metadata
- Fuzzy metadata matching with RapidFuzz
- Weighted similarity scoring
- Match confidence classification
- ISRC-aware matching with metadata fallback
- Batch metadata matching with matched, review, and unmatched results
- CSV/JSON catalog file matching with row-level validation and CSV/JSON export
- Match method tracking for ISRC and metadata-based matches
- Track version detection for remix, live, acoustic, and other version variants
- PostgreSQL trigram-based candidate retrieval for typo-tolerant matching
- Metadata backfill for existing records
- Integration testing against a dedicated PostgreSQL test database
- Evaluation pipeline with accuracy, precision, recall, and F1 metrics
- False-positive and false-negative error analysis
- Threshold analysis for similarity calibration

## Matching Pipeline

Incoming metadata is processed through a structured matching pipeline:

1. Check for an exact ISRC match when available
2. Normalize artist and track title metadata
3. Retrieve potential candidates from PostgreSQL
4. Compare artist and title metadata using fuzzy string matching
5. Calculate artist, title, and weighted similarity scores
6. Validate track-version compatibility
7. Apply calibrated matching thresholds
8. Classify matches by confidence level

This reduces unnecessary comparisons while handling spelling differences, formatting inconsistencies, title variations, and distinct track versions such as remixes, live recordings, and acoustic versions.

## API Endpoints

- `POST /api/v1/tracks` — Create a track
- `GET /api/v1/tracks` — Retrieve tracks
- `GET /api/v1/tracks/{track_id}` — Retrieve a track by ID
- `POST /api/v1/tracks/similar` — Find similar tracks
- `POST /api/v1/tracks/batch/match` — Match up to 100 tracks and return categorized results
- `POST /api/v1/catalog/match` — Match an uploaded CSV/JSON catalog file (read-only)
- `POST /api/v1/catalog/match/export?format=csv|json` — Same, returned as a downloadable file

## Catalog File Matching

Upload a catalog file to match every record against the reference catalog in
PostgreSQL. It uses the same ISRC-first and metadata matching engine,
thresholds, and status rules as the batch API. Processing is **read-only**:
uploads never insert tracks, and uploaded files are not stored.

### Supported Formats

The file is sent as the raw request body; the format is chosen by `Content-Type`.

| Format | `Content-Type` | Structure |
|---|---|---|
| CSV | `text/csv` | Comma-separated, header row required |
| JSON | `application/json` | Array of objects, or `{"tracks": [...]}` |

- Encoding must be UTF-8 (a BOM is allowed); any other `charset` returns `415`.
- Fields: `artist`, `title` (required), `album`, `isrc` (optional). CSV
  headers are case-insensitive. Unknown columns/keys are ignored and listed
  in `ignored_columns`.
- In CSV, an empty `album`/`isrc` cell means "not provided"; empty lines are
  skipped.
- Each record is validated with the same rules as `POST /api/v1/tracks`
  (see [Input Validation](#input-validation)).

### Limits

| Limit | Value | Response |
|---|---|---|
| File size | 1 MiB | `413` |
| Records per file | 1000 | `422` |
| CSV columns | 50 | `422` |
| Candidate matches returned per record | 5 (best first) | — |

The body is read in memory and reading stops as soon as the size limit is
exceeded, also for chunked uploads without `Content-Length`.

### Results

Every record appears in the result, in input order, with one status:
`matched`, `review`, `unmatched`, or `invalid`. Invalid records are never
dropped; they keep their raw values and list field-level `errors`. File-level
problems (unsupported type, invalid UTF-8, malformed CSV/JSON, missing
required columns, too many records) reject the whole file with a clear
`detail` message.

### Example

Synthetic example files are in [`examples/`](examples/). Load the reference
tracks first (this *does* write to the database, so use a development database):

```bash
python -c "import json,urllib.request as u; [u.urlopen(u.Request('http://127.0.0.1:8000/api/v1/tracks', json.dumps(t).encode(), {'Content-Type': 'application/json'})) for t in json.load(open('examples/reference_tracks.json', encoding='utf-8'))]"
```

Match a CSV or JSON catalog:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/catalog/match \
  -H "Content-Type: text/csv" --data-binary @examples/catalog.csv

curl -X POST http://127.0.0.1:8000/api/v1/catalog/match \
  -H "Content-Type: application/json" --data-binary @examples/catalog.json
```

Use `--data-binary`, not `-d`, so that line breaks are preserved.

Response (abbreviated; track IDs depend on your database):

```json
{
  "input_format": "csv",
  "ignored_columns": ["source_id"],
  "summary": {"total": 8, "matched": 3, "review": 1, "unmatched": 2, "invalid": 2},
  "results": [
    {
      "input_index": 0,
      "line_number": 2,
      "artist": "Neon Harbor",
      "title": "Midnight Signal (Official Audio)",
      "album": null,
      "isrc": "ZZNHB2600001",
      "status": "matched",
      "matches": [
        {"track_id": 1, "artist": "Neon Harbor", "title": "Midnight Signal",
         "score": 100.0, "classification": "high_confidence", "match_method": "isrc"}
      ],
      "errors": []
    },
    {
      "input_index": 2,
      "line_number": 4,
      "artist": "Glass Orchard",
      "title": "Slow Motion Summer",
      "album": null,
      "isrc": null,
      "status": "review",
      "matches": [
        {"track_id": 3, "artist": "The Glass Orchard", "title": "Slow Motion Summer",
         "score": 94.67, "classification": "review", "match_method": "metadata"}
      ],
      "errors": []
    },
    {
      "input_index": 5,
      "line_number": 7,
      "artist": "Neon Harbor",
      "title": "Midnight Signal",
      "album": null,
      "isrc": "BAD-ISRC",
      "status": "invalid",
      "matches": [],
      "errors": [{"field": "isrc", "message": "ISRC must be 12 characters: ..."}]
    }
  ]
}
```

`line_number` is the CSV line where the record starts (`null` for JSON).

### Export

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/catalog/match/export?format=csv" \
  -H "Content-Type: text/csv" --data-binary @examples/catalog.csv -o results.csv

curl -X POST "http://127.0.0.1:8000/api/v1/catalog/match/export?format=json" \
  -H "Content-Type: application/json" --data-binary @examples/catalog.json -o results.json
```

- The CSV export has one row per input record, in input order, with the best
  match (`best_match_*`), `candidate_count`, and `errors`. It is UTF-8 with a
  BOM so spreadsheet apps detect non-Latin text.
- Cells starting with `=`, `+`, `-`, `@`, tab, or CR (including full-width
  variants) are prefixed with `'` to prevent spreadsheet formula injection.
- The JSON export is identical to the `/catalog/match` response.

## Input Validation

Track payloads (create, similar, and each batch item) are validated; invalid
input returns `422`:

- `artist` and `title` are trimmed, must be 1–255 characters, and must contain
  at least one letter or digit after normalization (`"!!!"`, whitespace-only,
  or noise-only titles such as `"(Official Audio)"` are rejected).
- `album` is trimmed; a blank album is stored as `null`.
- `isrc` must follow the ISO 3901 structure: 2-letter country code,
  3 alphanumeric registrant characters, 2-digit year, 5-digit designation.
  Lowercase and the hyphenated form (`us-ug1-19-04206`) are accepted and
  stored as `USUG11904206`.

Normalization folds Latin diacritics to ASCII (`Beyoncé` → `beyonce`,
`Straße` → `strasse`) and keeps other scripts (`Кино` → `кино`), so non-Latin
metadata is no longer reduced to an empty string. Empty normalized metadata
never counts as a match.

## Data Integrity

- ISRCs are unique at the database level (unique index `ix_tracks_isrc`;
  tracks without an ISRC are unaffected). A concurrent duplicate insert is
  rolled back and returns `409`.
- Normalized artist/title duplicates are rejected by the application (`409`),
  but intentionally not by a database constraint, since distinct recordings
  can share metadata.
- The ISRC uniqueness migration refuses to run while duplicate ISRCs exist and
  lists them; it never modifies or deletes rows. Resolve duplicates manually
  before `alembic upgrade head`.

## Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- RapidFuzz
- Pytest
- Docker

## Development

### Start PostgreSQL

```bash
docker compose up -d
```

### Run Database Migrations

```bash
alembic upgrade head
```

### Start the API

```bash
uvicorn app.main:app --reload
```

Swagger UI will be available at `http://127.0.0.1:8000/docs`.

### Run Tests

Unit tests need no PostgreSQL, Docker, or `.env`:

```bash
pytest -m "not integration"
```

Integration tests (`tests/integration`, marked `integration`) need a separate,
dedicated PostgreSQL test database. One-time setup with the Docker database:

```bash
docker compose exec postgres createdb -U music_user music_metadata_test
docker compose exec postgres psql -U music_user -d music_metadata_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm"
```

Set `TEST_DATABASE_URL` in `.env` (see `.env.example`), then run:

```bash
pytest -m integration -rs
```

Safety rules enforced before any schema change:

- `TEST_DATABASE_URL` must be a PostgreSQL URL with an explicit host and a
  lowercase database name ending in `_test`.
- Its database name must differ from the one in `DATABASE_URL`.
- Query parameters that could redirect the connection (`dbname`, `host`,
  `port`, `service`, `options`, ...) are rejected.
- After connecting, `current_database()` must match the validated name.
- Tables are created in a disposable `pytest_<random>` schema, which is the only
  thing dropped on teardown. The application database is never touched.

If `TEST_DATABASE_URL` is missing, integration tests are skipped; if it is
malformed or unsafe, or PostgreSQL is unreachable, they error out without
running any DDL. Plain `pytest` runs both suites.

### Run Matching Evaluation

```bash
python -m scripts.evaluate_matching
```

### Analyze Matching Thresholds

```bash
python -m scripts.analyze_thresholds
```

## Project Status

In active development.


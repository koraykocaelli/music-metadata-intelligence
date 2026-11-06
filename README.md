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


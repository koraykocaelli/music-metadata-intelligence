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
- Database-level candidate retrieval before fuzzy comparison
- Metadata backfill for existing records
- - Integration testing against a dedicated PostgreSQL test database

## Matching Pipeline

Incoming metadata is processed through a structured matching pipeline:

1. Normalize artist and track title metadata
2. Retrieve potential candidates from PostgreSQL
3. Compare candidates using fuzzy string matching
4. Calculate a weighted similarity score
5. Classify matches by confidence level

This reduces unnecessary comparisons while handling spelling differences, formatting inconsistencies, and common title variations.

## API Endpoints

- `POST /api/v1/tracks` — Create a track
- `GET /api/v1/tracks` — Retrieve tracks
- `GET /api/v1/tracks/{track_id}` — Retrieve a track by ID
- `POST /api/v1/tracks/similar` — Find similar tracks

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

```bash
pytest
```

## Project Status

In active development.


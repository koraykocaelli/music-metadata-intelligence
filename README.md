# Music Metadata Intelligence

A backend-first music metadata processing and matching platform built with Python, FastAPI, PostgreSQL, and SQLAlchemy.

## Current Features

- FastAPI REST API
- PostgreSQL persistence with Docker
- SQLAlchemy ORM
- Alembic database migrations
- Track creation and retrieval endpoints
- Metadata normalization
- Music-specific title cleaning
- Duplicate detection by ISRC
- Duplicate detection by normalized artist and title

## Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker
- Pydantic

## API Endpoints

- `POST /api/v1/tracks`
- `GET /api/v1/tracks`
- `GET /api/v1/tracks/{track_id}`
- `GET /health`
- `GET /health/database`

## Project Status

In active development.

The current matching pipeline includes metadata normalization, duplicate detection, candidate retrieval, fuzzy similarity scoring, and confidence classification.
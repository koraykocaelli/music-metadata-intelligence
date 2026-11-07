# Music Metadata Intelligence

A backend service and web dashboard that links incoming music metadata to the
recordings in a reference catalog, even when names are misspelled, formatted
differently, or missing identifiers. Every match comes with a score, a
classification, and the evidence behind it.

Built with Python 3.12, FastAPI, PostgreSQL (`pg_trgm`), SQLAlchemy, Alembic,
RapidFuzz, and Docker. Matching is deterministic and rule-based; there is no
machine learning.

## Why this is hard

The same recording rarely looks the same in two catalogs:

| Source A | Source B | Same recording? |
|---|---|---|
| `The Weeknd — Blinding Lights` | `THE WEEKND!!! — Blinding Lights (Official Audio)` | Yes |
| `Beyoncé — Halo` | `Beyonce — Halo` | Yes |
| `Luna Vale — Paper Satellites` | `Luna Vale — Paper Satelites` | Yes (typo) |
| `Luna Vale — Paper Satellites` | `Luna Vale — Paper Satellites (Remix)` | **No**, a different version |

Exact string matching misses the first three. Naive fuzzy matching wrongly
merges the last one. ISRC codes solve the problem when they are present and
correct, which in real data they often are not. This project combines all
three signals: identifiers, normalized text, and fuzzy similarity with explicit
rules.

## Quick start

Requirements: [Docker](https://docs.docker.com/get-docker/) with Compose v2
and Git. Docker Compose runs two containers, PostgreSQL and the API (which also
serves the web dashboard). Both are reachable only from your own machine.

### 1. Clone and configure

macOS / Linux:

```bash
git clone https://github.com/koraykocaelli/music-metadata-intelligence.git
cd music-metadata-intelligence
cp .env.example .env
```

Windows PowerShell:

```powershell
git clone https://github.com/koraykocaelli/music-metadata-intelligence.git
cd music-metadata-intelligence
Copy-Item .env.example .env
```

Open `.env` and replace the placeholders. The same user and password must
appear in three places:

```dotenv
POSTGRES_USER=music_user
POSTGRES_PASSWORD=choose-a-password
DATABASE_URL=postgresql+psycopg://music_user:choose-a-password@localhost:5432/music_metadata
TEST_DATABASE_URL=postgresql+psycopg://music_user:choose-a-password@localhost:5432/music_metadata_test
```

- `POSTGRES_USER` / `POSTGRES_PASSWORD` are used by Docker Compose, both to
  create the database and to connect the app container to it.
- `DATABASE_URL` / `TEST_DATABASE_URL` are used when you run Python on your
  machine (local development, tests).
- Use a URL-safe password (letters, digits, `-`, `_`, `.`, `~`).

The other values in `.env.example` can stay as they are. Compose refuses to
run any command while `POSTGRES_PASSWORD` is unset.

### 2. Start the stack and create the schema

```bash
docker compose build
docker compose run --rm app alembic upgrade head
docker compose up -d
```

These commands are the same in PowerShell and bash. Migrations never run
automatically: `alembic upgrade head` creates the tables and enables
`pg_trgm`. Check the result with `docker compose ps` (both services should
report `healthy`).

- Dashboard: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>

### 3. Load the demo catalog (optional)

The main database starts empty. To try the examples without putting sample
data into it, use a separate demo database with four fictional tracks.
Replace `music_user` with your `POSTGRES_USER`:

```bash
docker compose exec postgres createdb -U music_user music_metadata_demo
```

Then set `APP_DATABASE_NAME=music_metadata_demo` in `.env` and run:

```bash
docker compose run --rm app alembic upgrade head
docker compose run --rm app python -m scripts.seed_demo_catalog
docker compose up -d
```

The seed script refuses to run unless the database name ends in `_demo`, and
it skips tracks that already exist. To switch back to the main database, set
`APP_DATABASE_NAME=music_metadata` and run `docker compose up -d` again.

### 4. Try it

Open <http://127.0.0.1:8000>:

- **Match a file** → click **example CSV**. Against the demo catalog you get
  3 matched, 1 review, 2 unmatched, and 2 invalid rows.
- **Match a track** → artist `Luna Vale`, title `Paper Satelites` → one
  candidate, score 98.06, matched by metadata. Add ISRC `ZZLVL2600002` and it
  matches by ISRC with score 100.

### 5. Stop

```bash
docker compose stop     # stop the containers; start again with: docker compose up -d
docker compose down     # remove the containers; the database volume is kept
```

Do not add `-v` to `docker compose down`: that deletes the database volume
and all its data.

### Fresh vs. existing database volume

Data lives in the Docker volume `music-metadata-intelligence_postgres_data`.

- **Fresh volume** (first run): PostgreSQL creates the user, password, and
  `music_metadata` database from `POSTGRES_USER`, `POSTGRES_PASSWORD`, and
  `POSTGRES_DB`.
- **Existing volume**: those variables are ignored. The database keeps the
  credentials it was created with, so `.env` must contain *those* credentials.
  Changing `POSTGRES_PASSWORD` later does not change the database password;
  if you need to, change it in PostgreSQL (`ALTER USER … PASSWORD …`), then
  update `.env`. You don't need to delete the volume.

If the app container reports `unhealthy` and its logs show
`password authentication failed`, the password in `.env` does not match the
database.

## What you can do

| Dashboard view | What it does | Writes to the database? |
|---|---|---|
| **Overview** | Track count, ISRC coverage, artists, and last added track, from real data | No |
| **Track library** | Browse, search, and sort the reference catalog | Only **Add track** |
| **Match a track** | Match one track; inspect each candidate's score, classification, and method | No |
| **Batch match** | Match up to 100 tracks; filter by status; review uncertain rows | No |
| **Match a file** | Match a CSV or JSON file (up to 1 MB, 1,000 rows); download results as CSV or JSON | No |
| **How matching works** | The rules and thresholds, in plain language | No |

**Matching never imports anything.** Single, batch, and file matching only read
the reference catalog. **Add track** (or `POST /api/v1/tracks`) is the only way
to create a reference record, and it writes permanently to the database the
app is connected to. There is no edit or delete.

## How matching works

For each input track:

1. **ISRC lookup.** If the ISRC exists in the reference catalog, that recording
   is returned with score 100 and method `isrc`. Otherwise, matching continues
   with metadata.
2. **Normalization.** Lowercase, Latin accents folded (`Beyoncé` → `beyonce`),
   punctuation removed, and title noise such as "Official Audio" or "Lyrics"
   stripped. Non-Latin scripts are preserved, not discarded.
3. **Candidate retrieval.** PostgreSQL returns up to 100 tracks whose
   normalized artist *or* title has `pg_trgm` similarity ≥ 0.3.
4. **Scoring.** RapidFuzz `fuzz.ratio` compares artist and title separately:
   `score = 0.4 × artist + 0.6 × title`.
5. **Rules.** A candidate is accepted only if artist ≥ 60, title ≥ 92,
   score ≥ 80, and both titles have the same version markers (remix, live,
   acoustic, instrumental, radio edit, extended mix, remastered, sped up,
   slowed).

| Candidate classification | Score | Resulting row status |
|---|---|---|
| `high_confidence` | ≥ 95 | `matched` |
| `review` | 80 to < 95 | `review` (a person should confirm) |
| `no_match` | < 80 or rule failed; not returned | `unmatched` |
| — | — | `invalid` (file rows that fail validation) |

A score is string similarity under these rules, **not a probability**. The
same input against the same catalog always gives the same result.
`unmatched` means no reference track passed the rules, not that the recording
doesn't exist.

## Architecture

```
Dashboard (app/static: HTML, CSS, JS modules)     API clients
                       \                          /
        FastAPI routers (app/api) + Pydantic validation (app/schemas)
                                  │
        Services (app/services): normalization, matching, track, catalog
                                  │
        Repository (app/repositories) ── SQLAlchemy ── PostgreSQL + pg_trgm
                                                       (schema: Alembic)
```

The dashboard is static files served by FastAPI, with no build step and no
CDN, and it calls the same REST API as any other client. There is one matching
implementation shared by all endpoints.

```
app/          api, core (settings), db, models, repositories, schemas, services, static
alembic/      migrations (tracks table, pg_trgm, unique ISRC index)
data/         60 labeled evaluation pairs
examples/     fictional reference tracks and example catalog files
scripts/      evaluation, threshold analysis, demo seeding, metadata backfill
tests/        unit tests; tests/integration for PostgreSQL tests
```

Notable details:

- **Input validation:** artist and title must contain a letter or digit;
  ISRCs follow ISO 3901 and are normalized (`us-ug1-19-04206` →
  `USUG11904206`).
- **ISRC uniqueness** is enforced by a unique index, and concurrent
  duplicate inserts are rolled back and return `409`.
- **File uploads** are streamed into memory with a hard size limit and never
  stored. CSV exports are protected against spreadsheet formula injection.

## Databases

| Database | Purpose | Created by |
|---|---|---|
| `music_metadata` | Your reference catalog (default) | PostgreSQL on first start, schema by Alembic |
| `music_metadata_demo` | Demo with fictional tracks | `createdb` + Alembic + `seed_demo_catalog` (step 3) |
| `music_metadata_test` | Integration tests only | `createdb` (see [Testing](#testing)) |

`APP_DATABASE_NAME` in `.env` selects which database the Docker app uses.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health/database` | Database connectivity |
| `GET` | `/api/v1/tracks`, `/api/v1/tracks/{track_id}` | List or get reference tracks |
| `POST` | `/api/v1/tracks` | Add a reference track (`409` on duplicates) |
| `POST` | `/api/v1/tracks/similar` | Match one track |
| `POST` | `/api/v1/tracks/batch/match` | Match 1–100 tracks |
| `POST` | `/api/v1/catalog/match` | Match a CSV/JSON file (sent as the raw request body) |
| `POST` | `/api/v1/catalog/match/export?format=csv\|json` | Same, as a download |

Request and response schemas are in Swagger UI at `/docs`. Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tracks/similar \
  -H "Content-Type: application/json" \
  -d '{"artist": "Luna Vale", "title": "Paper Satelites"}'
```

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/tracks/similar `
  -ContentType "application/json" -Body '{"artist": "Luna Vale", "title": "Paper Satelites"}'
```

Response against the demo catalog:

```json
[{"track_id": 2, "artist": "Luna Vale", "title": "Paper Satellites",
  "score": 98.06, "classification": "high_confidence", "match_method": "metadata"}]
```

To match a file, send it as the request body:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/catalog/match \
  -H "Content-Type: text/csv" --data-binary @examples/catalog.csv
```

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/catalog/match `
  -H "Content-Type: text/csv" --data-binary "@examples/catalog.csv"
```

Use `--data-binary` (not `-d`) so line breaks are preserved. In PowerShell,
call `curl.exe` explicitly and quote the `@` argument.

## Local development without Docker

Run PostgreSQL in Docker and the application on your machine (Python 3.12).
The app container also uses port 8000, so stop it first:

```bash
docker compose up -d postgres
docker compose stop app
python -m venv .venv
source .venv/bin/activate              # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Local commands read `DATABASE_URL` from `.env`. If PowerShell blocks
`Activate.ps1`, run `Set-ExecutionPolicy -Scope Process RemoteSigned` in that
window first.

## Testing

Run the tests from the virtual environment set up above. Unit tests need no
database and no `.env`:

```bash
pytest -m "not integration"
```

Integration tests run against `music_metadata_test`, which needs `pg_trgm`
(replace `music_user` with your `POSTGRES_USER`):

```bash
docker compose exec postgres createdb -U music_user music_metadata_test
docker compose exec postgres psql -U music_user -d music_metadata_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm"
pytest -m integration -rs
```

The test setup is built to never touch real data. It checks that
`TEST_DATABASE_URL` is a PostgreSQL database whose name ends in `_test` and
differs from `DATABASE_URL`, confirms the connected database before any schema
change, and creates its tables in a temporary `pytest_*` schema that it drops
afterwards. If `TEST_DATABASE_URL` is missing, integration tests are skipped.

[CI](.github/workflows/ci.yml) runs the unit tests, applies all migrations to a
clean database, runs the integration tests (failing if any are skipped), runs
the evaluation, and builds the Docker image. It needs no secrets.

### Evaluation

```bash
python -m scripts.evaluate_matching
```

[`data/evaluation_pairs.json`](data/evaluation_pairs.json) contains 60
hand-labeled metadata pairs (25 matches, 35 non-matches) covering casing,
punctuation, title noise, typos, and version differences. The current rules
classify all 60 correctly. This is an **in-sample** result: the thresholds
were tuned on these same pairs, the set is small and Latin-script only, and
it covers metadata matching, not ISRC lookup or retrieval. It is not evidence
of real-world accuracy.

## Security and limitations

- Built as a **local, single-user demo**. There is no authentication, and
  ports are bound to localhost. Add authentication, rate limiting, and TLS
  before exposing it on a network.
- No credentials are stored in the repository. `.env` is git-ignored and
  excluded from the Docker image.
- Matching is synchronous: a 1,000-row file means up to about 2,000 queries.
- Trigram retrieval is weak for scripts written without spaces (e.g. Japanese).
- Recordings that share artist and title (such as re-recordings) can't be
  told apart without a distinguishing ISRC. Version detection relies on English
  keywords.
- Match results and review decisions are not stored. Reference tracks can't be
  edited or deleted.

## Possible improvements

- A larger, independently labeled evaluation set with a held-out split,
  including non-Latin scripts.
- Additional signals (ISWC, UPC, duration) to separate recordings with
  identical metadata.
- Bulk candidate retrieval for large files.
- Persisted review decisions with an audit trail.

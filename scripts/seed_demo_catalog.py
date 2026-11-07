"""Load the synthetic reference tracks from examples/reference_tracks.json.

Intended only for a separate, disposable demo database. To protect real data
it refuses to run unless the target database name ends with "_demo".
Already-present tracks (same ISRC or normalized metadata) are skipped, so the
script can be run repeatedly. It never updates or deletes rows.

    DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/music_metadata_demo \
        python -m scripts.seed_demo_catalog
"""

import json
import sys
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.track import TrackCreate
from app.services import track as track_service

REFERENCE_FILE = Path(__file__).resolve().parents[1] / "examples" / "reference_tracks.json"
DEMO_SUFFIX = "_demo"


def main() -> int:
    database = make_url(settings.database_url).database or ""

    if not database.endswith(DEMO_SUFFIX):
        print(
            f"Refusing to seed: DATABASE_URL must point to a database whose name "
            f"ends with '{DEMO_SUFFIX}' (got '{database}').",
            file=sys.stderr,
        )
        return 2

    tracks = json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))
    created = skipped = 0

    with SessionLocal() as db:
        connected = db.execute(text("SELECT current_database()")).scalar_one()
        if connected != database:
            print("Refusing to seed: connected database does not match.", file=sys.stderr)
            return 2

        for item in tracks:
            try:
                track_service.create_track(db, TrackCreate(**item))
                created += 1
            except HTTPException as error:
                if error.status_code != 409:
                    raise
                skipped += 1

    print(f"Seeded '{database}': {created} created, {skipped} already present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

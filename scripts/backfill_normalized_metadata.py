from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.track import Track
from app.services.normalization import normalize_text, normalize_track_title


def backfill_normalized_metadata() -> None:
    db = SessionLocal()

    try:
        tracks = db.scalars(select(Track)).all()
        updated_count = 0

        for track in tracks:
            was_updated = False

            if track.normalized_artist is None:
                track.normalized_artist = normalize_text(track.artist)
                was_updated = True

            if track.normalized_title is None:
                track.normalized_title = normalize_track_title(track.title)
                was_updated = True

            if was_updated:
                updated_count += 1

        db.commit()

        print(f"Updated {updated_count} tracks.")

    finally:
        db.close()


if __name__ == "__main__":
    backfill_normalized_metadata()
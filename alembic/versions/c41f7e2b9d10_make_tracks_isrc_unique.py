"""make tracks.isrc unique

Revision ID: c41f7e2b9d10
Revises: a2763756da39
Create Date: 2026-11-07 12:00:00.000000

Replaces the non-unique ix_tracks_isrc index with a unique index of the same
name so the database rejects duplicate ISRCs, including concurrent inserts.
NULL ISRCs remain allowed any number of times.

This migration never modifies or deletes rows. If duplicate ISRCs already
exist it aborts with a list of them; resolve those rows manually first.
PostgreSQL would also refuse to build the unique index over duplicates, and
the index swap runs in a single transaction, so a failure leaves the schema
unchanged.
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41f7e2b9d10'
down_revision: Union[str, Sequence[str], None] = 'a2763756da39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DUPLICATE_ISRC_QUERY = sa.text(
    """
    SELECT upper(trim(isrc)) AS isrc_key,
           count(*) AS track_count,
           string_agg(id::text, ', ' ORDER BY id) AS track_ids
    FROM tracks
    WHERE isrc IS NOT NULL
    GROUP BY upper(trim(isrc))
    HAVING count(*) > 1
    ORDER BY isrc_key
    """
)


def _abort_if_duplicate_isrcs() -> None:
    if context.is_offline_mode():
        # No connection in --sql mode; CREATE UNIQUE INDEX itself will fail
        # on duplicates when the generated SQL is executed.
        return

    duplicates = op.get_bind().execute(DUPLICATE_ISRC_QUERY).all()

    if duplicates:
        details = "; ".join(
            f"{row.isrc_key} (track ids: {row.track_ids})" for row in duplicates
        )
        raise RuntimeError(
            "Cannot make tracks.isrc unique: duplicate ISRCs exist "
            "(compared case-insensitively). No data was changed. Resolve "
            f"these rows manually, then rerun the migration: {details}"
        )


def upgrade() -> None:
    """Upgrade schema."""
    _abort_if_duplicate_isrcs()

    op.drop_index(op.f('ix_tracks_isrc'), table_name='tracks')
    op.create_index(op.f('ix_tracks_isrc'), 'tracks', ['isrc'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tracks_isrc'), table_name='tracks')
    op.create_index(op.f('ix_tracks_isrc'), 'tracks', ['isrc'], unique=False)

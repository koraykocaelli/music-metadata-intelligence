"""enable pg_trgm extension

Revision ID: a2763756da39
Revises: a38c470f1289
Create Date: 2026-09-13 20:28:46.288492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2763756da39'
down_revision: Union[str, Sequence[str], None] = 'a38c470f1289'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")

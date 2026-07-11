"""add chunk full-text search vector

Revision ID: dd7bdb752c64
Revises: 9bff93bd4d29
Create Date: 2026-07-11 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dd7bdb752c64'
down_revision: str | Sequence[str] | None = '9bff93bd4d29'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # A STORED generated column keeps search_vector in sync with `text`
    # automatically -- no application code or trigger has to remember to
    # update it. See ADR-0007.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )
    op.create_index(
        "ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chunks_search_vector", table_name="chunks")
    op.execute("ALTER TABLE chunks DROP COLUMN search_vector")

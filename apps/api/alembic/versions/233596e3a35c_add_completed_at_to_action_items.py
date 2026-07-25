"""add completed_at to action_items

Revision ID: 233596e3a35c
Revises: 14d083c62844
Create Date: 2026-07-23 09:35:59.370577

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '233596e3a35c'
down_revision: str | Sequence[str] | None = '14d083c62844'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('action_items', sa.Column('completed_at', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('action_items', 'completed_at')

"""add severity to decisions

Revision ID: 14d083c62844
Revises: f7222b85a8b6
Create Date: 2026-07-19 09:57:36.861567

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '14d083c62844'
down_revision: str | Sequence[str] | None = 'f7222b85a8b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

severity_enum = sa.Enum('low', 'medium', 'high', name='severity_category_items')


def upgrade() -> None:
    """Upgrade schema."""
    severity_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'decisions',
        sa.Column('severity', severity_enum, nullable=False, server_default='low'),
    )
    op.alter_column('decisions', 'severity', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('decisions', 'severity')
    severity_enum.drop(op.get_bind(), checkfirst=True)

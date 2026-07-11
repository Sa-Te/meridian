"""add traces table

Revision ID: f7222b85a8b6
Revises: dd7bdb752c64
Create Date: 2026-07-11 17:29:32.395715

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7222b85a8b6'
down_revision: str | Sequence[str] | None = 'dd7bdb752c64'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('traces',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('endpoint', sa.String(length=255), nullable=False),
    sa.Column('stages', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('total_duration_ms', sa.Float(), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('models_used', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('outcome', sa.Enum('answered', 'declined', 'error', name='trace_outcome'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_traces_created_at'), 'traces', ['created_at'], unique=False)
    op.create_index(op.f('ix_traces_endpoint'), 'traces', ['endpoint'], unique=False)
    op.create_index(op.f('ix_traces_outcome'), 'traces', ['outcome'], unique=False)
    # NOTE: autogenerate also proposed dropping/recreating chunks'
    # ix_chunks_search_vector (a GIN index over a STORED generated column,
    # migration dd7bdb752c64) -- a known alembic reflection limitation with
    # generated-column indexes, not a real schema diff. Removed from both
    # upgrade and downgrade below; that index is untouched by this revision.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_traces_outcome'), table_name='traces')
    op.drop_index(op.f('ix_traces_endpoint'), table_name='traces')
    op.drop_index(op.f('ix_traces_created_at'), table_name='traces')
    op.drop_table('traces')

    # Same reasoning as Trace.status/ActionItemStatus in migration
    # 9bff93bd4d29: dropping the traces table doesn't drop the Postgres
    # ENUM type backing its outcome column -- it's an independent named
    # object that must be dropped explicitly, or a later re-upgrade fails
    # with "type already exists".
    sa.Enum(name='trace_outcome').drop(op.get_bind(), checkfirst=True)

"""Add configurable agent chunking settings.

Revision ID: 20261022_0002
Revises: 20261022_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0002"
down_revision: str | None = "20261022_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "chunk_strategy",
            sa.String(length=20),
            nullable=False,
            server_default="recursive",
        ),
    )
    op.add_column(
        "agents",
        sa.Column("chunk_size_tokens", sa.Integer(), nullable=False, server_default="650"),
    )
    op.add_column(
        "agents",
        sa.Column(
            "chunk_overlap_percent", sa.Float(), nullable=False, server_default="0.12"
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "chunk_overlap_percent")
    op.drop_column("agents", "chunk_size_tokens")
    op.drop_column("agents", "chunk_strategy")

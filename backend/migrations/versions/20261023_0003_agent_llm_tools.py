"""Add per-agent LLM provider and tool configuration.

Revision ID: 20261023_0003
Revises: 20261022_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0003"
down_revision: str | None = "20261022_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("llm_provider", sa.String(length=20), nullable=False, server_default="openai"),
    )
    op.add_column(
        "agents",
        sa.Column(
            "tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "tools")
    op.drop_column("agents", "llm_provider")

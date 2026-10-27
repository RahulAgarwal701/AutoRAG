"""Add public widget configuration to agents.

Revision ID: 20261024_0005
Revises: 20261023_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261024_0005"
down_revision: str | None = "20261023_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "greeting",
            sa.String(length=500),
            nullable=False,
            server_default="Hi! How can I help?",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "theme",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'{"primary_color": "#111827", "position": "bottom-right"}\'::jsonb'
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "theme")
    op.drop_column("agents", "greeting")

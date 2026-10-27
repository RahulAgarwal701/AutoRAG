"""Use the Gemini free-tier model as the default answer provider.

Revision ID: 20261023_0004
Revises: 20261023_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0004"
down_revision: str | None = "20261023_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE agents SET llm_provider = 'gemini', "
            "model = 'gemini-2.5-flash-lite' WHERE llm_provider = 'openai'"
        )
    )
    op.alter_column(
        "agents",
        "llm_provider",
        existing_type=sa.String(length=20),
        server_default="gemini",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE agents SET llm_provider = 'openai' WHERE llm_provider = 'gemini'"))
    op.alter_column(
        "agents",
        "llm_provider",
        existing_type=sa.String(length=20),
        server_default="openai",
        existing_nullable=False,
    )

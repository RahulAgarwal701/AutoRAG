import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, JSON, Boolean, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.chat import ChatSession
    from app.models.document import Document
    from app.models.user import User


class Agent(CreatedAtMixin, Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    greeting: Mapped[str] = mapped_column(
        String(500), nullable=False, default="Hi! How can I help?"
    )
    theme: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {"primary_color": "#111827", "position": "bottom-right"},
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    llm_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="gemini"
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    use_reranker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chunk_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="recursive"
    )
    chunk_size_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=650)
    chunk_overlap_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.12
    )
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(String()).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    tools: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    user: Mapped["User"] = relationship(back_populates="agents")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", passive_deletes=True
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", passive_deletes=True
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", passive_deletes=True
    )


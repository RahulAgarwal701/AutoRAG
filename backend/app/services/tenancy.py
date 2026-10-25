import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.models.document import Document


async def get_owned_agent(
    session: AsyncSession, user_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent | None:
    return await session.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    )


async def get_owned_document(
    session: AsyncSession,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document | None:
    return await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.agent_id == agent_id,
            Document.user_id == user_id,
        )
    )


async def get_owned_api_key(
    session: AsyncSession,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    api_key_id: uuid.UUID,
) -> ApiKey | None:
    return await session.scalar(
        select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.agent_id == agent_id,
            ApiKey.user_id == user_id,
        )
    )


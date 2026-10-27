import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key
from app.models.api_key import ApiKey


async def create_api_key(
    session: AsyncSession, user_id: uuid.UUID, agent_id: uuid.UUID
) -> tuple[ApiKey, str]:
    full_key, prefix, hashed_key = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        agent_id=agent_id,
        hashed_key=hashed_key,
        prefix=prefix,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key, full_key

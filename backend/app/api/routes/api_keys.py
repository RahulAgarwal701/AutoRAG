import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreated, ApiKeyRead
from app.services.api_keys import create_api_key
from app.services.tenancy import get_owned_agent, get_owned_api_key

router = APIRouter(prefix="/agents/{agent_id}/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def issue_api_key(
    agent_id: uuid.UUID, session: DatabaseSession, current_user: CurrentUser
) -> ApiKeyCreated:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    api_key, full_key = await create_api_key(session, current_user.id, agent.id)
    safe_fields = ApiKeyRead.model_validate(api_key).model_dump()
    return ApiKeyCreated(**safe_fields, key=full_key)


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(
    agent_id: uuid.UUID, session: DatabaseSession, current_user: CurrentUser
) -> list[ApiKey]:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    result = await session.scalars(
        select(ApiKey)
        .where(ApiKey.agent_id == agent_id, ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result)


@router.post("/{api_key_id}/revoke", response_model=ApiKeyRead)
async def revoke_api_key(
    agent_id: uuid.UUID,
    api_key_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> ApiKey:
    api_key = await get_owned_api_key(session, current_user.id, agent_id, api_key_id)
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.revoked = True
    await session.commit()
    await session.refresh(api_key)
    return api_key


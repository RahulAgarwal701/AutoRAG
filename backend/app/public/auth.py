import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InvalidTokenError,
    decode_widget_session_token,
    hash_api_key,
)
from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.public.errors import PublicApiError


@dataclass(frozen=True)
class PublicAuthContext:
    user_id: uuid.UUID
    agent: Agent
    credential_id: str
    auth_type: str


def require_allowed_origin(agent: Agent, origin: str | None) -> str:
    if origin is None or origin not in agent.allowed_origins:
        raise PublicApiError(403, "origin_not_allowed", "Origin is not allowed")
    return origin


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client is not None else "unknown"


async def authenticate_public_chat(
    *,
    session: AsyncSession,
    request: Request,
    agent_id: uuid.UUID,
    token: str | None = None,
) -> PublicAuthContext:
    if not token:
        raise PublicApiError(
            401,
            "authentication_required",
            "A Bearer API key or widget session token is required",
            {"WWW-Authenticate": "Bearer"},
        )
    origin = request.headers.get("origin")
    if token.startswith("ark_live_"):
        row = (
            await session.execute(
                select(ApiKey, Agent)
                .join(Agent, Agent.id == ApiKey.agent_id)
                .where(
                    ApiKey.hashed_key == hash_api_key(token),
                    ApiKey.agent_id == agent_id,
                    ApiKey.revoked.is_(False),
                )
            )
        ).first()
        if row is None:
            raise PublicApiError(401, "invalid_api_key", "API key is invalid or revoked")
        api_key, agent = row
        if origin is not None:
            require_allowed_origin(agent, origin)
        api_key.last_used_at = datetime.now(UTC)
        await session.commit()
        return PublicAuthContext(
            user_id=api_key.user_id,
            agent=agent,
            credential_id=str(api_key.id),
            auth_type="api_key",
        )
    try:
        claims = decode_widget_session_token(token)
    except InvalidTokenError as exc:
        raise PublicApiError(
            401, "invalid_widget_token", "Widget session token is invalid or expired"
        ) from exc
    if claims.agent_id != agent_id:
        raise PublicApiError(401, "invalid_widget_token", "Token is for another agent")
    agent = await session.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == claims.user_id)
    )
    if agent is None:
        raise PublicApiError(404, "agent_not_found", "Agent not found")
    request_origin = require_allowed_origin(agent, origin)
    if request_origin != claims.origin:
        raise PublicApiError(403, "origin_mismatch", "Token is bound to another origin")
    return PublicAuthContext(
        user_id=claims.user_id,
        agent=agent,
        credential_id=str(claims.token_id),
        auth_type="widget",
    )


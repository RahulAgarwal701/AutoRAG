import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.models.agent import Agent

router = APIRouter(prefix="/internal/widget-frame-policy", tags=["internal"])


class WidgetFramePolicy(BaseModel):
    allowed_origins: list[str]


@router.get("/{agent_id}", response_model=WidgetFramePolicy, include_in_schema=False)
async def widget_frame_policy(
    agent_id: uuid.UUID,
    session: DatabaseSession,
    x_widget_policy_token: Annotated[str | None, Header()] = None,
) -> WidgetFramePolicy:
    configured = get_settings().widget_policy_token
    if configured is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Widget frame policy endpoint is not configured",
        )
    supplied = x_widget_policy_token or ""
    if not secrets.compare_digest(supplied, configured.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid widget policy token",
        )
    allowed_origins = await session.scalar(
        select(Agent.allowed_origins).where(Agent.id == agent_id)
    )
    if allowed_origins is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return WidgetFramePolicy(allowed_origins=allowed_origins)

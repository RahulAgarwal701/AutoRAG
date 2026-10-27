import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.agent import Agent
from app.schemas.agent import (
    AgentCreate,
    AgentLLMUpdate,
    AgentRead,
    AgentUpdate,
    AgentWidgetUpdate,
)
from app.services.tenancy import get_owned_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate, session: DatabaseSession, current_user: CurrentUser
) -> Agent:
    agent = Agent(user_id=current_user.id, **payload.model_dump())
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@router.get("", response_model=list[AgentRead])
async def list_agents(session: DatabaseSession, current_user: CurrentUser) -> list[Agent]:
    result = await session.scalars(
        select(Agent).where(Agent.user_id == current_user.id).order_by(Agent.created_at.desc())
    )
    return list(result)


@router.get("/{agent_id}", response_model=AgentRead)
async def read_agent(
    agent_id: uuid.UUID, session: DatabaseSession, current_user: CurrentUser
) -> Agent:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Agent:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await session.commit()
    await session.refresh(agent)
    return agent


@router.patch("/{agent_id}/llm", response_model=AgentRead)
async def update_agent_llm(
    agent_id: uuid.UUID,
    payload: AgentLLMUpdate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Agent:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent.llm_provider = payload.llm_provider
    agent.model = payload.model or agent.model
    await session.commit()
    await session.refresh(agent)
    return agent


@router.patch("/{agent_id}/widget-config", response_model=AgentRead)
async def update_agent_widget_config(
    agent_id: uuid.UUID,
    payload: AgentWidgetUpdate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Agent:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agent.greeting = payload.greeting
    agent.theme = payload.theme
    agent.allowed_origins = payload.allowed_origins
    await session.commit()
    await session.refresh(agent)
    return agent

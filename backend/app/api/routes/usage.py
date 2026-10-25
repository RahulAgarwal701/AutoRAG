from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.models.chat import ChatSession, Message
from app.models.document import Document, DocumentStatus
from app.schemas.usage import DocumentUsage, UsageSummary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageSummary)
async def read_usage(
    session: DatabaseSession,
    current_user: CurrentUser,
) -> UsageSummary:
    user_id = current_user.id
    agents = await session.scalar(
        select(func.count()).select_from(Agent).where(Agent.user_id == user_id)
    )
    document_counts = (
        await session.execute(
            select(
                func.count(Document.id),
                func.sum(case((Document.status == DocumentStatus.PENDING, 1), else_=0)),
                func.sum(case((Document.status == DocumentStatus.PROCESSING, 1), else_=0)),
                func.sum(case((Document.status == DocumentStatus.READY, 1), else_=0)),
                func.sum(case((Document.status == DocumentStatus.FAILED, 1), else_=0)),
                func.coalesce(func.sum(Document.chunk_count), 0),
            ).where(Document.user_id == user_id)
        )
    ).one()
    chat_sessions = await session.scalar(
        select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
    )
    messages = await session.scalar(
        select(func.count()).select_from(Message).where(Message.user_id == user_id)
    )
    active_api_keys = await session.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.revoked.is_(False))
    )
    return UsageSummary(
        agents=agents or 0,
        documents=DocumentUsage(
            total=document_counts[0] or 0,
            pending=document_counts[1] or 0,
            processing=document_counts[2] or 0,
            ready=document_counts[3] or 0,
            failed=document_counts[4] or 0,
            indexed_chunks=document_counts[5] or 0,
        ),
        chat_sessions=chat_sessions or 0,
        messages=messages or 0,
        active_api_keys=active_api_keys or 0,
    )

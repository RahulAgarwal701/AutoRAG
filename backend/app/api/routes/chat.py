import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.agents.service import ChatAgentService, encode_sse
from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest
from app.services.tenancy import get_owned_agent

router = APIRouter(prefix="/agents/{agent_id}/chat", tags=["chat"])
settings = get_settings()
logger = get_logger(__name__)


@router.post("/stream")
async def stream_chat(
    agent_id: uuid.UUID,
    payload: ChatRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    service = ChatAgentService(session)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in service.stream(
                tenant_id=current_user.id,
                agent=agent,
                question=payload.message,
                session_id=payload.session_id,
            ):
                yield event
        except LookupError as exc:
            yield encode_sse("error", {"detail": str(exc), "status": 404})
        except Exception as exc:
            logger.exception(
                "chat_stream_failed",
                extra={
                    "agent_id": str(agent.id),
                    "user_id": str(current_user.id),
                    "error_type": type(exc).__name__,
                },
            )
            detail = (
                f"{type(exc).__name__}: {str(exc)[:500]}"
                if settings.debug
                else "The agent could not complete this request"
            )
            yield encode_sse(
                "error",
                {"detail": detail, "status": 500},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

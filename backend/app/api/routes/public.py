import math
import time
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.agents.service import ChatAgentService, encode_sse
from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_widget_session_token
from app.models.agent import Agent
from app.public.auth import (
    PublicAuthContext,
    authenticate_public_chat,
    get_client_ip,
    require_allowed_origin,
)
from app.public.errors import PublicApiError
from app.public.rate_limit import SlidingWindowRateLimiter, get_rate_limiter
from app.schemas.public_api import (
    ErrorResponse,
    PublicAgentConfig,
    PublicChatRequest,
    PublicChatResponse,
    TokenUsage,
    WidgetSessionResponse,
)

router = APIRouter(prefix="/v1/agents/{agent_id}", tags=["public-api"])
settings = get_settings()
logger = get_logger(__name__)
bearer = HTTPBearer(
    auto_error=False,
    scheme_name="AgentBearerAuth",
    description="Use an ark_live_ API key or a short-lived widget session token.",
)
RateLimiter = Annotated[SlidingWindowRateLimiter, Depends(get_rate_limiter)]

ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Invalid credentials"},
    403: {"model": ErrorResponse, "description": "Origin not allowed"},
    404: {"model": ErrorResponse, "description": "Agent or session not found"},
    422: {"model": ErrorResponse, "description": "Invalid request"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
}


async def _agent_or_404(session: DatabaseSession, agent_id: uuid.UUID) -> Agent:
    agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
    if agent is None:
        raise PublicApiError(404, "agent_not_found", "Agent not found")
    return agent


async def _limit(
    limiter: SlidingWindowRateLimiter,
    identifier: str,
    limit: int,
) -> dict[str, str]:
    result = await limiter.check(identifier, limit)
    reset_seconds = max(0, math.ceil((result.reset_at_ms / 1000) - time.time()))
    headers = {
        "RateLimit-Limit": str(limit),
        "RateLimit-Remaining": str(result.remaining),
        "RateLimit-Reset": str(reset_seconds),
    }
    if not result.allowed:
        headers["Retry-After"] = str(reset_seconds)
        raise PublicApiError(429, "rate_limit_exceeded", "Too many requests", headers)
    return headers


async def _authenticate(
    agent_id: uuid.UUID,
    request: Request,
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
    limiter: RateLimiter,
) -> PublicAuthContext:
    request.state.rate_limit_headers = await _limit(
        limiter,
        f"ip:{get_client_ip(request)}",
        settings.ip_rate_limit,
    )
    return await authenticate_public_chat(
        session=session,
        request=request,
        agent_id=agent_id,
        token=credentials.credentials if credentials is not None else None,
    )


PublicAuth = Annotated[PublicAuthContext, Depends(_authenticate)]


@router.post(
    "/chat",
    response_model=None,
    responses={
        200: {
            "description": "JSON response or text/event-stream when stream=true",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "9afdb85c-a49e-4c70-b3d8-eaa09a94ac5f",
                        "answer": "The total is INR 42,750 [1].",
                        "citations": [
                            {
                                "document": "invoice.pdf",
                                "page": 1,
                                "snippet": "Total payable INR 42,750",
                                "link": "https://storage.example/source",
                            }
                        ],
                        "usage": {
                            "input_tokens": 340,
                            "output_tokens": 18,
                            "total_tokens": 358,
                            "estimated": True,
                        },
                    }
                },
                "text/event-stream": {"example": 'event: token\ndata: {"text":"The total"}\n\n'},
            },
        },
        **ERROR_RESPONSES,
    },
    summary="Chat with a document-grounded agent",
)
async def public_chat(
    agent_id: uuid.UUID,
    payload: PublicChatRequest,
    request: Request,
    session: DatabaseSession,
    auth: PublicAuth,
    limiter: RateLimiter,
) -> Response:
    headers = dict(getattr(request.state, "rate_limit_headers", {}))
    if auth.auth_type == "api_key":
        headers.update(
            await _limit(
                limiter,
                f"api-key:{auth.credential_id}",
                settings.api_key_rate_limit,
            )
        )
    service = ChatAgentService(session)
    if payload.stream:

        async def events() -> AsyncIterator[str]:
            try:
                async for event, data in service.stream_events(
                    tenant_id=auth.user_id,
                    agent=auth.agent,
                    question=payload.message,
                    session_id=payload.session_id,
                ):
                    yield encode_sse(event, data)
            except Exception:
                request_id = getattr(request.state, "request_id", "unknown")
                logger.exception(
                    "public_chat_stream_failed",
                    extra={"request_id": request_id, "agent_id": str(agent_id)},
                )
                yield encode_sse(
                    "error",
                    {
                        "error": {
                            "code": "chat_failed",
                            "message": "The agent could not complete this request",
                            "request_id": request_id,
                        }
                    },
                )

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={**headers, "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    session_id: uuid.UUID | None = None
    answer = ""
    citations: list[dict[str, object]] = []
    usage: dict[str, object] = {}
    try:
        async for event, data in service.stream_events(
            tenant_id=auth.user_id,
            agent=auth.agent,
            question=payload.message,
            session_id=payload.session_id,
        ):
            if event == "session":
                session_id = uuid.UUID(str(data["session_id"]))  # type: ignore[index]
            elif event == "token":
                answer += str(data["text"])  # type: ignore[index]
            elif event == "citations":
                citations = data  # type: ignore[assignment]
            elif event == "usage":
                usage = data  # type: ignore[assignment]
    except PublicApiError:
        raise
    except Exception as exc:
        logger.exception(
            "public_chat_failed",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "agent_id": str(agent_id),
            },
        )
        raise PublicApiError(
            500, "chat_failed", "The agent could not complete this request"
        ) from exc
    if session_id is None:
        raise PublicApiError(500, "chat_failed", "Chat did not create a session")
    body = PublicChatResponse(
        session_id=session_id,
        answer=answer,
        citations=citations,
        usage=TokenUsage.model_validate(usage),
    )
    return Response(
        content=body.model_dump_json(),
        media_type="application/json",
        headers=headers,
    )


@router.get(
    "/public-config",
    response_model=PublicAgentConfig,
    responses=ERROR_RESPONSES,
    summary="Get widget-safe agent configuration",
)
async def public_config(
    agent_id: uuid.UUID,
    request: Request,
    response: Response,
    session: DatabaseSession,
    limiter: RateLimiter,
) -> PublicAgentConfig:
    agent = await _agent_or_404(session, agent_id)
    require_allowed_origin(agent, request.headers.get("origin"))
    response.headers.update(
        await _limit(
            limiter,
            f"ip:{get_client_ip(request)}",
            settings.ip_rate_limit,
        )
    )
    return PublicAgentConfig(name=agent.name, greeting=agent.greeting, theme=agent.theme)


@router.post(
    "/widget/session",
    response_model=WidgetSessionResponse,
    responses=ERROR_RESPONSES,
    summary="Issue a short-lived browser widget token",
)
async def issue_widget_session(
    agent_id: uuid.UUID,
    request: Request,
    response: Response,
    session: DatabaseSession,
    limiter: RateLimiter,
) -> WidgetSessionResponse:
    agent = await _agent_or_404(session, agent_id)
    origin = require_allowed_origin(agent, request.headers.get("origin"))
    response.headers.update(
        await _limit(
            limiter,
            f"widget-session-ip:{get_client_ip(request)}",
            settings.widget_session_ip_rate_limit,
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return WidgetSessionResponse(
        token=create_widget_session_token(agent.id, agent.user_id, origin),
        expires_in=settings.widget_session_token_expire_minutes * 60,
    )

import re
import time
import uuid

from fastapi import Request, Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.agent import Agent

logger = get_logger(__name__)
_PUBLIC_AGENT_PATH = re.compile(r"^/v1/agents/([0-9a-fA-F-]{36})/")


def _error_response(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


class PublicRequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id[:100]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            if not request.url.path.startswith("/v1/"):
                raise
            logger.exception(
                "public_api_unhandled_error",
                extra={
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            response = _error_response(
                500,
                "internal_error",
                "An internal error occurred",
                request.state.request_id,
            )
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/v1/"):
            logger.info(
                "public_api_request",
                extra={
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
        return response


class AgentCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        match = _PUBLIC_AGENT_PATH.match(request.url.path)
        origin = request.headers.get("origin")
        if match is None or origin is None:
            return await call_next(request)
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        try:
            agent_id = uuid.UUID(match.group(1))
        except ValueError:
            return _error_response(404, "agent_not_found", "Agent not found", request_id)
        async with async_session_factory() as session:
            allowed_origins = await session.scalar(
                select(Agent.allowed_origins).where(Agent.id == agent_id)
            )
        if allowed_origins is None:
            return _error_response(404, "agent_not_found", "Agent not found", request_id)
        if origin not in allowed_origins:
            return _error_response(403, "origin_not_allowed", "Origin is not allowed", request_id)
        cors_headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Request-ID",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors_headers)
        response = await call_next(request)
        response.headers.update(cors_headers)
        return response

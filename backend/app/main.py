import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.middleware.public_api import AgentCORSMiddleware, PublicRequestLoggingMiddleware
from app.public.errors import PublicApiError

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


async def public_api_error_handler(
    request: Request, exc: PublicApiError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if not request.url.path.startswith("/v1/"):
        return await request_validation_exception_handler(request, exc)
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": request_id,
            }
        },
    )


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if not request.url.path.startswith("/v1/"):
        return await http_exception_handler(request, exc)
    request_id = getattr(request.state, "request_id", "unknown")
    message = str(exc.detail) if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": message,
                "request_id": request_id,
            }
        },
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker_task: asyncio.Task[None] | None = None
    if settings.run_temporal_worker_in_process:
        from app.workflows.worker import run_worker

        worker_task = asyncio.create_task(run_worker(), name="temporal-worker")
    logger.info("application_started", extra={"environment": settings.app_env})
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        logger.info("application_stopped")


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(AgentCORSMiddleware)
    application.add_middleware(PublicRequestLoggingMiddleware)
    application.add_exception_handler(PublicApiError, public_api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_error_handler)
    application.include_router(api_router)
    return application


app = create_application()


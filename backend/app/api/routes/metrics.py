import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.middleware.metrics import request_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics(
    authorization: Annotated[str | None, Header()] = None,
    x_metrics_token: Annotated[str | None, Header()] = None,
) -> PlainTextResponse:
    expected_secret = get_settings().metrics_token
    if expected_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics endpoint is not configured",
        )
    supplied = x_metrics_token
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    expected = expected_secret.get_secret_value()
    if supplied is None or not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid metrics token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return PlainTextResponse(
        request_metrics.render(),
        media_type="text/plain; version=0.0.4",
    )

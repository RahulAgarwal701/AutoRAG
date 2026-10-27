import json
import logging
from typing import cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.core.logging import JsonFormatter
from app.middleware.request_size import RequestBodyLimitMiddleware


def test_json_logging_redacts_pii_and_credentials() -> None:
    record = logging.LogRecord(
        name="autorag.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            "Login failed for person@example.com with Bearer secret-token password=another-secret"
        ),
        args=(),
        exc_info=None,
    )
    record.email = "person@example.com"
    record.metadata = {
        "api_key": "ark_live_supersecret",
        "database": "postgresql://user:password@db/autorag",
    }

    payload = json.loads(JsonFormatter().format(record))
    serialized = json.dumps(payload)

    assert "person@example.com" not in serialized
    assert "secret-token" not in serialized
    assert "supersecret" not in serialized
    assert "another-secret" not in serialized
    assert "password@" not in serialized
    assert payload["email"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_request_body_limit_rejects_chunked_body_without_content_length() -> None:
    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope
        while (await receive()).get("more_body", False):
            pass
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    messages = iter(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ]
    )
    sent: list[Message] = []

    async def receive() -> Message:
        return cast(Message, next(messages))

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(downstream, max_body_size=8)
    scope = cast(
        Scope,
        {"type": "http", "method": "POST", "path": "/", "headers": []},
    )

    await middleware(scope, receive, send)

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413

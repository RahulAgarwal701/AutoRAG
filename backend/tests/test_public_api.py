import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import (
    create_widget_session_token,
    decode_widget_session_token,
)
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.agent import Agent
from app.public.auth import require_allowed_origin
from app.public.errors import PublicApiError
from app.public.rate_limit import RateLimitResult, SlidingWindowRateLimiter, get_rate_limiter
from tests.test_tenant_isolation import authorization, signup


class AllowAllRateLimiter:
    async def check(self, identifier: str, limit: int) -> RateLimitResult:
        del identifier
        return RateLimitResult(True, limit - 1, 0)


@pytest.fixture
async def api_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_rate_limiter] = lambda: AllowAllRateLimiter()
    monkeypatch.setattr(
        "app.middleware.public_api.async_session_factory", session_factory
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


def test_widget_session_token_is_bound_to_agent_tenant_and_origin() -> None:
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_widget_session_token(agent_id, user_id, "https://widget.example")

    claims = decode_widget_session_token(token)

    assert claims.agent_id == agent_id
    assert claims.user_id == user_id
    assert claims.origin == "https://widget.example"


def test_origin_check_requires_exact_agent_allowlist_match() -> None:
    agent = Agent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Widget agent",
        greeting="Hello",
        theme={},
        system_prompt="Stay grounded",
        model="test",
        allowed_origins=["https://allowed.example"],
        tools=[],
    )

    assert require_allowed_origin(agent, "https://allowed.example") == (
        "https://allowed.example"
    )
    with pytest.raises(PublicApiError) as exc_info:
        require_allowed_origin(agent, "https://attacker.example")
    assert exc_info.value.code == "origin_not_allowed"


class FakeRedis:
    def __init__(self, result: list[int]) -> None:
        self.result = result
        self.arguments: tuple[object, ...] | None = None

    async def eval(self, *arguments: object) -> list[int]:
        self.arguments = arguments
        return self.result


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_uses_namespaced_redis_key() -> None:
    redis = FakeRedis([1, 8, 123456])
    limiter = SlidingWindowRateLimiter(redis, 60)  # type: ignore[arg-type]

    result = await limiter.check("api-key:key-id", 10)

    assert result.allowed is True
    assert result.remaining == 8
    assert redis.arguments is not None
    assert redis.arguments[2] == "autorag:rate:api-key:key-id"
    assert redis.arguments[5] == 10


@pytest.mark.asyncio
async def test_public_api_returns_consistent_error_for_invalid_api_key(
    api_client: AsyncClient,
) -> None:
    user = await signup(api_client, "public-api-owner@example.com")
    created = await api_client.post(
        "/api/v1/agents",
        headers=authorization(user["access_token"]),
        json={"name": "Public API agent", "system_prompt": "Stay grounded."},
    )
    agent_id = created.json()["id"]

    response = await api_client.post(
        f"/v1/agents/{agent_id}/chat",
        headers={"Authorization": "Bearer ark_live_invalid"},
        json={"message": "Hello", "stream": False},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_api_key"
    assert body["error"]["request_id"] == response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_public_config_rejects_requests_without_origin(
    api_client: AsyncClient,
) -> None:
    user = await signup(api_client, "public-config-owner@example.com")
    created = await api_client.post(
        "/api/v1/agents",
        headers=authorization(user["access_token"]),
        json={
            "name": "Widget agent",
            "system_prompt": "Stay grounded.",
            "allowed_origins": ["https://allowed.example"],
        },
    )

    response = await api_client.get(
        f"/v1/agents/{created.json()['id']}/public-config"
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"


def test_openapi_documents_public_chat_examples() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/v1/agents/{agent_id}/chat"]["post"]

    assert "AgentBearerAuth" in schema["components"]["securitySchemes"]
    assert "application/json" in operation["responses"]["200"]["content"]
    assert "text/event-stream" in operation["responses"]["200"]["content"]


class FakeChatAgentService:
    def __init__(self, session: AsyncSession) -> None:
        del session

    async def stream_events(self, **_: object) -> AsyncIterator[tuple[str, Any]]:
        yield "session", {"session_id": "9afdb85c-a49e-4c70-b3d8-eaa09a94ac5f"}
        yield "token", {"text": "The total is INR 42,750 [1]."}
        yield "usage", {
            "input_tokens": 20,
            "output_tokens": 9,
            "total_tokens": 29,
            "estimated": True,
        }
        yield "citations", [
            {
                "document": "invoice.pdf",
                "page": 1,
                "snippet": "Total payable INR 42,750",
                "link": "https://storage.test/invoice.pdf",
            }
        ]


async def create_agent_and_key(client: AsyncClient, email: str) -> tuple[str, str]:
    user = await signup(client, email)
    headers = authorization(user["access_token"])
    agent = await client.post(
        "/api/v1/agents",
        headers=headers,
        json={"name": "External agent", "system_prompt": "Stay grounded."},
    )
    agent_id = agent.json()["id"]
    issued = await client.post(
        f"/api/v1/agents/{agent_id}/api-keys", headers=headers
    )
    return agent_id, issued.json()["key"]


@pytest.mark.asyncio
async def test_api_key_chat_supports_json_and_streaming_sse(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_id, api_key = await create_agent_and_key(
        api_client, "external-chat@example.com"
    )
    monkeypatch.setattr(
        "app.api.routes.public.ChatAgentService", FakeChatAgentService
    )
    headers = {"Authorization": f"Bearer {api_key}"}

    json_response = await api_client.post(
        f"/v1/agents/{agent_id}/chat",
        headers=headers,
        json={"message": "What is the total?", "stream": False},
    )

    assert json_response.status_code == 200
    assert json_response.json()["answer"] == "The total is INR 42,750 [1]."
    assert json_response.json()["citations"][0]["document"] == "invoice.pdf"
    assert json_response.json()["usage"]["total_tokens"] == 29
    assert json_response.headers["ratelimit-limit"] == "60"

    stream_response = await api_client.post(
        f"/v1/agents/{agent_id}/chat",
        headers=headers,
        json={"message": "What is the total?", "stream": True},
    )

    assert stream_response.status_code == 200
    assert stream_response.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in stream_response.text
    assert stream_response.text.rstrip().endswith(
        'data: [{"document":"invoice.pdf","page":1,"snippet":"Total payable INR '
        '42,750","link":"https://storage.test/invoice.pdf"}]'
    )


@pytest.mark.asyncio
async def test_widget_flow_uses_origin_bound_token_without_exposing_api_key(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await signup(api_client, "widget-flow@example.com")
    dashboard_headers = authorization(user["access_token"])
    created = await api_client.post(
        "/api/v1/agents",
        headers=dashboard_headers,
        json={
            "name": "Support bot",
            "greeting": "Ask about your invoice",
            "theme": {"primary_color": "#2563eb", "position": "bottom-right"},
            "system_prompt": "Stay grounded.",
            "allowed_origins": ["https://customer.example"],
        },
    )
    agent_id = created.json()["id"]
    origin_headers = {"Origin": "https://customer.example"}

    preflight = await api_client.options(
        f"/v1/agents/{agent_id}/chat",
        headers={
            **origin_headers,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == (
        "https://customer.example"
    )

    config = await api_client.get(
        f"/v1/agents/{agent_id}/public-config", headers=origin_headers
    )
    assert config.status_code == 200
    assert config.json() == {
        "name": "Support bot",
        "greeting": "Ask about your invoice",
        "theme": {"primary_color": "#2563eb", "position": "bottom-right"},
    }

    issued = await api_client.post(
        f"/v1/agents/{agent_id}/widget/session", headers=origin_headers
    )
    assert issued.status_code == 200
    assert "ark_live_" not in issued.text
    widget_token = issued.json()["token"]
    claims = decode_widget_session_token(widget_token)
    assert claims.origin == "https://customer.example"

    monkeypatch.setattr(
        "app.api.routes.public.ChatAgentService", FakeChatAgentService
    )
    chat = await api_client.post(
        f"/v1/agents/{agent_id}/chat",
        headers={
            **origin_headers,
            "Authorization": f"Bearer {widget_token}",
        },
        json={"message": "What is the total?", "stream": False},
    )
    assert chat.status_code == 200
    assert chat.json()["answer"] == "The total is INR 42,750 [1]."

    rejected = await api_client.post(
        f"/v1/agents/{agent_id}/chat",
        headers={
            "Origin": "https://attacker.example",
            "Authorization": f"Bearer {widget_token}",
        },
        json={"message": "Steal data", "stream": False},
    )
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "origin_not_allowed"

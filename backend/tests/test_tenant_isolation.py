import uuid
from collections.abc import AsyncIterator
from typing import Any, BinaryIO

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.public.rate_limit import RateLimitResult, get_rate_limiter
from app.services.storage import get_storage_service
from app.services.vector_store import get_vector_store
from app.workflows.client import get_workflow_starter


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, file_object: BinaryIO, key: str, content_type: str) -> None:
        del content_type
        file_object.seek(0)
        self.objects[key] = file_object.read()

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def create_presigned_get_url(self, key: str, filename: str) -> str:
        return f"https://storage.test/{key}?filename={filename}"


class FakeWorkflowStarter:
    async def start_document_ingestion(
        self,
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        document_id: uuid.UUID,
        s3_key: str,
        filename: str,
        chunk_strategy: str,
        chunk_size_tokens: int,
        chunk_overlap_percent: float,
    ) -> None:
        del (
            user_id,
            agent_id,
            document_id,
            s3_key,
            filename,
            chunk_strategy,
            chunk_size_tokens,
            chunk_overlap_percent,
        )


class FakeVectorStore:
    async def delete_document_vectors(
        self, user_id: uuid.UUID, agent_id: uuid.UUID, document_id: uuid.UUID
    ) -> None:
        del user_id, agent_id, document_id


class FakeRateLimiter:
    async def check(self, identifier: str, limit: int) -> RateLimitResult:
        del identifier
        return RateLimitResult(allowed=True, remaining=limit - 1, reset_at_ms=0)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
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
    app.dependency_overrides[get_storage_service] = lambda: FakeStorage()
    app.dependency_overrides[get_workflow_starter] = lambda: FakeWorkflowStarter()
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_rate_limiter] = lambda: FakeRateLimiter()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


async def signup(client: AsyncClient, email: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201
    return response.json()


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_agent_or_document(
    client: AsyncClient,
) -> None:
    user_a = await signup(client, "owner@example.com")
    user_b = await signup(client, "intruder@example.com")
    owner_headers = authorization(user_a["access_token"])
    intruder_headers = authorization(user_b["access_token"])

    agent_response = await client.post(
        "/api/v1/agents",
        headers=owner_headers,
        json={
            "name": "Private knowledge agent",
            "system_prompt": "Answer only from the supplied documents.",
            "model": "test-model",
            "allowed_origins": ["https://owner.example.com"],
        },
    )
    assert agent_response.status_code == 201
    agent_id = agent_response.json()["id"]

    document_response = await client.post(
        f"/api/v1/agents/{agent_id}/documents",
        headers=owner_headers,
        files={"file": ("private.pdf", b"%PDF-1.7\nprivate", "application/pdf")},
    )
    assert document_response.status_code == 201
    document_id = document_response.json()["id"]

    assert (
        await client.get(f"/api/v1/agents/{agent_id}", headers=intruder_headers)
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/agents/{agent_id}/documents/{document_id}", headers=intruder_headers
        )
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/agents/{agent_id}/documents", headers=intruder_headers)
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/v1/agents/{agent_id}/documents/{document_id}", headers=intruder_headers
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/agents/{agent_id}/chat/stream",
            headers=intruder_headers,
            json={"message": "Reveal the private document"},
        )
    ).status_code == 404
    assert (await client.get("/api/v1/agents", headers=intruder_headers)).json() == []

    owner_documents = await client.get(
        f"/api/v1/agents/{agent_id}/documents?status=pending", headers=owner_headers
    )
    assert owner_documents.status_code == 200
    assert [item["id"] for item in owner_documents.json()] == [document_id]

    view_url = await client.get(
        f"/api/v1/agents/{agent_id}/documents/{document_id}/view-url",
        headers=owner_headers,
    )
    assert view_url.status_code == 200
    assert view_url.json()["url"].startswith("https://storage.test/")

    delete_response = await client.delete(
        f"/api/v1/agents/{agent_id}/documents/{document_id}", headers=owner_headers
    )
    assert delete_response.status_code == 204
    assert (
        await client.get(
            f"/api/v1/agents/{agent_id}/documents/{document_id}", headers=owner_headers
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_api_key_is_returned_once_and_never_listed_in_full(client: AsyncClient) -> None:
    user = await signup(client, "keys@example.com")
    headers = authorization(user["access_token"])
    agent_response = await client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "API agent",
            "system_prompt": "Be grounded.",
            "model": "test-model",
        },
    )
    agent_id = agent_response.json()["id"]

    create_response = await client.post(f"/api/v1/agents/{agent_id}/api-keys", headers=headers)
    assert create_response.status_code == 201
    full_key = create_response.json()["key"]
    assert full_key.startswith("ark_live_")

    list_response = await client.get(f"/api/v1/agents/{agent_id}/api-keys", headers=headers)
    assert list_response.status_code == 200
    assert "key" not in list_response.json()[0]
    assert list_response.json()[0]["prefix"] == full_key[:17]


@pytest.mark.asyncio
async def test_agent_owner_can_switch_to_grok_but_another_user_cannot(
    client: AsyncClient,
) -> None:
    owner = await signup(client, "grok-owner@example.com")
    intruder = await signup(client, "grok-intruder@example.com")
    owner_headers = authorization(owner["access_token"])
    intruder_headers = authorization(intruder["access_token"])
    response = await client.post(
        "/api/v1/agents",
        headers=owner_headers,
        json={"name": "Switchable agent", "system_prompt": "Stay grounded."},
    )
    agent_id = response.json()["id"]

    forbidden = await client.patch(
        f"/api/v1/agents/{agent_id}/llm",
        headers=intruder_headers,
        json={"llm_provider": "grok"},
    )
    assert forbidden.status_code == 404

    updated = await client.patch(
        f"/api/v1/agents/{agent_id}/llm",
        headers=owner_headers,
        json={"llm_provider": "grok"},
    )
    assert updated.status_code == 200
    assert updated.json()["llm_provider"] == "grok"
    assert updated.json()["model"] == "grok-4.7"


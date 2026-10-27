import os

import asyncpg
import httpx
import pytest
from redis.asyncio import Redis

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SERVICE_TESTS") != "true",
    reason="service-container smoke tests run only in CI",
)


@pytest.mark.asyncio
async def test_postgres_service_is_reachable() -> None:
    connection = await asyncpg.connect(os.environ["TEST_POSTGRES_DSN"])
    try:
        assert await connection.fetchval("SELECT 1") == 1
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_redis_service_is_reachable() -> None:
    client = Redis.from_url(os.environ["REDIS_URL"])
    try:
        assert await client.ping() is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_qdrant_service_is_ready() -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{os.environ['QDRANT_URL']}/readyz")
    assert response.status_code == 200

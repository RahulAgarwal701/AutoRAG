import uuid
from functools import lru_cache
from typing import Protocol

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings


class VectorStore(Protocol):
    async def delete_document_vectors(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID, document_id: uuid.UUID
    ) -> None: ...


class QdrantVectorStore:
    def __init__(self, client: AsyncQdrantClient, collection_name: str) -> None:
        self._client = client
        self._collection_name = collection_name

    async def delete_document_vectors(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID, document_id: uuid.UUID
    ) -> None:
        if not await self._client.collection_exists(self._collection_name):
            return
        payload_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id", match=models.MatchValue(value=str(tenant_id))
                ),
                models.FieldCondition(key="agent_id", match=models.MatchValue(value=str(agent_id))),
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=str(document_id))
                ),
            ]
        )
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.FilterSelector(filter=payload_filter),
            wait=True,
        )


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return QdrantVectorStore(client, settings.qdrant_collection_name)

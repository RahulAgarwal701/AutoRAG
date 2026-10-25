import uuid

import pytest

from app.services.vector_store import QdrantVectorStore


class FakeQdrantClient:
    def __init__(self) -> None:
        self.delete_kwargs: dict[str, object] | None = None

    async def collection_exists(self, collection_name: str) -> bool:
        assert collection_name == "chunks"
        return True

    async def delete(self, **kwargs: object) -> None:
        self.delete_kwargs = kwargs


@pytest.mark.asyncio
async def test_vector_delete_uses_tenant_agent_and_document_payload_filter() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(client, "chunks")  # type: ignore[arg-type]
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    document_id = uuid.uuid4()

    await store.delete_document_vectors(user_id, agent_id, document_id)

    assert client.delete_kwargs is not None
    selector = client.delete_kwargs["points_selector"]
    conditions = selector.filter.must
    values = {condition.key: condition.match.value for condition in conditions}
    assert values == {
        "tenant_id": str(user_id),
        "agent_id": str(agent_id),
        "document_id": str(document_id),
    }

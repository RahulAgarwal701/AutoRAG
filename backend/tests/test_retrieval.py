import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from qdrant_client import models

from app.services.ingestion_models import SparseVectorData
from app.services.retrieval import QdrantHybridSearcher, build_tenant_agent_filter


def filter_values(query_filter: models.Filter) -> dict[str, object]:
    assert query_filter.must is not None
    return {
        condition.key: condition.match.value
        for condition in query_filter.must
        if isinstance(condition, models.FieldCondition)
        and isinstance(condition.match, models.MatchValue)
    }


def test_tenant_agent_filter_contains_both_required_scopes() -> None:
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    values = filter_values(build_tenant_agent_filter(tenant_id, agent_id))

    assert values == {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
    }


class FakeQdrantClient:
    def __init__(self) -> None:
        self.query_kwargs: dict[str, object] | None = None

    async def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.query_kwargs = kwargs
        return SimpleNamespace(points=[])


@pytest.mark.asyncio
async def test_hybrid_search_filters_dense_sparse_and_fused_query() -> None:
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    client = FakeQdrantClient()
    searcher = QdrantHybridSearcher(client, "chunks")  # type: ignore[arg-type]

    await searcher.search(
        tenant_id=tenant_id,
        agent_id=agent_id,
        dense_vector=[0.1, 0.2],
        sparse_vector=SparseVectorData(indices=[7], values=[0.9]),
        limit=12,
    )

    assert client.query_kwargs is not None
    expected = {"tenant_id": str(tenant_id), "agent_id": str(agent_id)}
    query_filter = cast(models.Filter, client.query_kwargs["query_filter"])
    assert filter_values(query_filter) == expected
    prefetch = cast(list[models.Prefetch], client.query_kwargs["prefetch"])
    assert len(prefetch) == 2
    assert all(filter_values(item.filter) == expected for item in prefetch)
    assert prefetch[0].using == "dense"
    assert prefetch[1].using == "sparse"
    query = cast(models.FusionQuery, client.query_kwargs["query"])
    assert query.fusion == models.Fusion.RRF

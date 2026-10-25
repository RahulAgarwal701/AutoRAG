import asyncio
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.agent import Agent
from app.models.document import Document
from app.services.embeddings import (
    BM25SparseEmbeddingProvider,
    GeminiEmbeddingProvider,
    SparseEmbeddingProvider,
    SpladeSparseEmbeddingProvider,
)
from app.services.ingestion_models import SparseVectorData
from app.services.query_rewriter import ChatTurn, GeminiQueryRewriter, QueryRewriter
from app.services.reranker import CohereReranker, Reranker
from app.services.storage import ObjectStorage, get_storage_service


class QueryEmbeddingProvider(Protocol):
    async def embed_query(self, query: str) -> list[float]: ...


class RetrievedChunk(BaseModel):
    text: str
    score: float
    document_id: uuid.UUID
    document_name: str
    page: int | None = None
    section: str | None = None
    chunk_index: int
    source_url: str


@dataclass(frozen=True)
class HybridHit:
    score: float
    payload: Mapping[str, object]


def build_tenant_agent_filter(
    tenant_id: uuid.UUID, agent_id: uuid.UUID
) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="tenant_id", match=models.MatchValue(value=str(tenant_id))
            ),
            models.FieldCondition(
                key="agent_id", match=models.MatchValue(value=str(agent_id))
            ),
        ]
    )


class QdrantHybridSearcher:
    def __init__(self, client: AsyncQdrantClient, collection_name: str) -> None:
        self._client = client
        self._collection_name = collection_name

    async def search(
        self,
        *,
        tenant_id: uuid.UUID,
        agent_id: uuid.UUID,
        dense_vector: list[float],
        sparse_vector: SparseVectorData,
        limit: int,
    ) -> list[HybridHit]:
        tenant_filter = build_tenant_agent_filter(tenant_id, agent_id)
        response = await self._client.query_points(
            collection_name=self._collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    filter=tenant_filter,
                    limit=limit,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_vector.indices,
                        values=sparse_vector.values,
                    ),
                    using="sparse",
                    filter=tenant_filter,
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=tenant_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [
            HybridHit(score=point.score, payload=point.payload or {})
            for point in response.points
        ]


class RetrievalService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        searcher: QdrantHybridSearcher,
        dense_embeddings: QueryEmbeddingProvider,
        sparse_embeddings: SparseEmbeddingProvider,
        query_rewriter: QueryRewriter,
        storage: ObjectStorage,
        reranker: Reranker | None = None,
    ) -> None:
        self._session = session
        self._searcher = searcher
        self._dense_embeddings = dense_embeddings
        self._sparse_embeddings = sparse_embeddings
        self._query_rewriter = query_rewriter
        self._storage = storage
        self._reranker = reranker

    async def retrieve(
        self,
        *,
        tenant_id: uuid.UUID,
        agent: Agent,
        question: str,
        chat_history: Sequence[ChatTurn] = (),
    ) -> list[RetrievedChunk]:
        if agent.user_id != tenant_id:
            raise ValueError("Agent does not belong to the tenant")
        if not question.strip():
            raise ValueError("Question cannot be empty")
        standalone_query = await self._query_rewriter.rewrite(question, chat_history)
        return await self.retrieve_standalone(
            tenant_id=tenant_id,
            agent=agent,
            standalone_query=standalone_query,
        )

    async def retrieve_standalone(
        self,
        *,
        tenant_id: uuid.UUID,
        agent: Agent,
        standalone_query: str,
    ) -> list[RetrievedChunk]:
        """Retrieve an already rewritten query without rewriting it a second time."""
        if agent.user_id != tenant_id:
            raise ValueError("Agent does not belong to the tenant")
        if not standalone_query.strip():
            raise ValueError("Standalone query cannot be empty")
        dense_vector, sparse_vectors = await asyncio.gather(
            self._dense_embeddings.embed_query(standalone_query),
            self._sparse_embeddings.embed([standalone_query]),
        )
        candidate_limit = max(agent.top_k * 4, 20) if agent.use_reranker else agent.top_k
        hits = await self._searcher.search(
            tenant_id=tenant_id,
            agent_id=agent.id,
            dense_vector=dense_vector,
            sparse_vector=sparse_vectors[0],
            limit=candidate_limit,
        )
        if not hits:
            return []
        if agent.use_reranker:
            if self._reranker is None:
                raise RuntimeError(
                    "Agent requires reranking, but COHERE_API_KEY is not configured"
                )
            reranked = await self._reranker.rerank(
                standalone_query,
                [str(hit.payload.get("text", "")) for hit in hits],
                agent.top_k,
            )
            hits = [
                HybridHit(score=item.score, payload=hits[item.index].payload)
                for item in reranked
            ]
        else:
            hits = hits[: agent.top_k]
        return await self._enrich_hits(tenant_id, agent.id, hits)

    async def _enrich_hits(
        self,
        tenant_id: uuid.UUID,
        agent_id: uuid.UUID,
        hits: Sequence[HybridHit],
    ) -> list[RetrievedChunk]:
        document_ids = {
            uuid.UUID(str(hit.payload["document_id"]))
            for hit in hits
            if hit.payload.get("document_id")
        }
        if not document_ids:
            return []
        documents = await self._session.scalars(
            select(Document).where(
                Document.id.in_(document_ids),
                Document.user_id == tenant_id,
                Document.agent_id == agent_id,
            )
        )
        document_map = {document.id: document for document in documents}
        source_urls = dict(
            await asyncio.gather(
                *(
                    self._source_url_pair(document)
                    for document in document_map.values()
                )
            )
        )
        results: list[RetrievedChunk] = []
        for hit in hits:
            document_id = uuid.UUID(str(hit.payload["document_id"]))
            document = document_map.get(document_id)
            if document is None:
                continue
            page = hit.payload.get("page")
            section = hit.payload.get("section")
            results.append(
                RetrievedChunk(
                    text=str(hit.payload.get("text", "")),
                    score=hit.score,
                    document_id=document_id,
                    document_name=document.filename,
                    page=int(page) if page is not None else None,
                    section=str(section) if section is not None else None,
                    chunk_index=int(hit.payload.get("chunk_index", 0)),
                    source_url=source_urls[document_id],
                )
            )
        return results

    async def _source_url_pair(self, document: Document) -> tuple[uuid.UUID, str]:
        url = await self._storage.create_presigned_get_url(
            document.s3_key, document.filename
        )
        return document.id, url


def create_retrieval_service(session: AsyncSession) -> RetrievalService:
    settings = get_settings()
    if settings.gemini_api_key is None:
        raise RuntimeError("GEMINI_API_KEY is required for retrieval")
    api_key = settings.gemini_api_key.get_secret_value()
    dense_embeddings = GeminiEmbeddingProvider(
        api_key, settings.embedding_model, settings.embedding_dimension
    )
    sparse_embeddings: SparseEmbeddingProvider = (
        SpladeSparseEmbeddingProvider()
        if settings.sparse_embedding_provider.lower() == "splade"
        else BM25SparseEmbeddingProvider()
    )
    reranker = (
        CohereReranker(
            settings.cohere_api_key.get_secret_value(), settings.cohere_rerank_model
        )
        if settings.cohere_api_key is not None
        else None
    )
    return RetrievalService(
        session=session,
        searcher=QdrantHybridSearcher(
            AsyncQdrantClient(
                url=settings.qdrant_url, api_key=settings.qdrant_api_key
            ),
            settings.qdrant_collection_name,
        ),
        dense_embeddings=dense_embeddings,
        sparse_embeddings=sparse_embeddings,
        query_rewriter=GeminiQueryRewriter(api_key, settings.query_rewrite_model),
        storage=get_storage_service(),
        reranker=reranker,
    )

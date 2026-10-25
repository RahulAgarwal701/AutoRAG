import uuid
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from temporalio import activity

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.services.chunking import chunk_document_data
from app.services.document_parser import parse_document_bytes
from app.services.embeddings import (
    BM25SparseEmbeddingProvider,
    GeminiEmbeddingProvider,
    SpladeSparseEmbeddingProvider,
)
from app.services.ingestion_models import (
    ChunkedDocument,
    ChunkingConfig,
    EmbeddedChunk,
    EmbeddedDocument,
    ParsedDocument,
)
from app.services.storage import get_storage_service
from app.services.vector_store import get_vector_store


@dataclass(frozen=True)
class DownloadInput:
    s3_key: str
    artifact_prefix: str


@dataclass(frozen=True)
class ParseInput:
    source_key: str
    filename: str
    artifact_prefix: str


@dataclass(frozen=True)
class ChunkInput:
    parsed_key: str
    artifact_prefix: str
    strategy: str
    size_tokens: int
    overlap_percent: float


@dataclass(frozen=True)
class EmbedInput:
    chunks_key: str
    artifact_prefix: str


@dataclass(frozen=True)
class UpsertInput:
    embedded_key: str
    tenant_id: str
    agent_id: str
    document_id: str


@dataclass(frozen=True)
class StatusInput:
    document_id: str
    status: str
    chunk_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class CleanupInput:
    tenant_id: str
    agent_id: str
    document_id: str


async def _write_json(key: str, value: str) -> str:
    await get_storage_service().put_bytes(value.encode(), key, "application/json")
    return key


@activity.defn(name="download_from_s3")
async def download_from_s3(input: DownloadInput) -> str:
    storage = get_storage_service()
    data = await storage.get_bytes(input.s3_key)
    output_key = f"{input.artifact_prefix}/source.bin"
    await storage.put_bytes(data, output_key, "application/octet-stream")
    return output_key


@activity.defn(name="parse_document")
async def parse_document(input: ParseInput) -> str:
    data = await get_storage_service().get_bytes(input.source_key)
    parsed = parse_document_bytes(data, input.filename)
    return await _write_json(
        f"{input.artifact_prefix}/parsed.json", parsed.model_dump_json()
    )


@activity.defn(name="chunk_document")
async def chunk_document(input: ChunkInput) -> str:
    raw = await get_storage_service().get_bytes(input.parsed_key)
    parsed = ParsedDocument.model_validate_json(raw)
    chunked = chunk_document_data(
        parsed,
        ChunkingConfig(
            strategy=input.strategy,
            size_tokens=input.size_tokens,
            overlap_percent=input.overlap_percent,
        ),
    )
    return await _write_json(
        f"{input.artifact_prefix}/chunks.json", chunked.model_dump_json()
    )


@activity.defn(name="embed_chunks")
async def embed_chunks(input: EmbedInput) -> str:
    settings = get_settings()
    if settings.gemini_api_key is None:
        raise RuntimeError("GEMINI_API_KEY is required by the ingestion worker")
    raw = await get_storage_service().get_bytes(input.chunks_key)
    chunked = ChunkedDocument.model_validate_json(raw)
    dense_provider = GeminiEmbeddingProvider(
        settings.gemini_api_key.get_secret_value(),
        settings.embedding_model,
        settings.embedding_dimension,
    )
    sparse_provider = (
        SpladeSparseEmbeddingProvider()
        if settings.sparse_embedding_provider.lower() == "splade"
        else BM25SparseEmbeddingProvider()
    )
    embedded: list[EmbeddedChunk] = []
    all_texts = [chunk.text for chunk in chunked.chunks]
    all_sparse = await sparse_provider.embed(all_texts)
    for start in range(0, len(chunked.chunks), settings.embedding_batch_size):
        batch = chunked.chunks[start : start + settings.embedding_batch_size]
        texts = [chunk.text for chunk in batch]
        dense = await dense_provider.embed(texts)
        sparse = all_sparse[start : start + len(batch)]
        for chunk, dense_vector, sparse_vector in zip(batch, dense, sparse, strict=True):
            embedded.append(
                EmbeddedChunk(
                    **chunk.model_dump(), dense=dense_vector, sparse=sparse_vector
                )
            )
        activity.heartbeat(start + len(batch), len(chunked.chunks))
    document = EmbeddedDocument(chunks=embedded)
    return await _write_json(
        f"{input.artifact_prefix}/embedded.json", document.model_dump_json()
    )


@activity.defn(name="upsert_to_qdrant")
async def upsert_to_qdrant(input: UpsertInput) -> int:
    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    collection = settings.qdrant_collection_name
    if not await client.collection_exists(collection):
        try:
            await client.create_collection(
                collection_name=collection,
                vectors_config={
                    "dense": models.VectorParams(
                        size=settings.embedding_dimension, distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={"sparse": models.SparseVectorParams()},
            )
        except UnexpectedResponse as exc:
            if exc.status_code != 409:
                raise
    raw = await get_storage_service().get_bytes(input.embedded_key)
    document = EmbeddedDocument.model_validate_json(raw)
    namespace = uuid.UUID(input.document_id)
    points = [
        models.PointStruct(
            id=str(uuid.uuid5(namespace, str(chunk.chunk_index))),
            vector={
                "dense": chunk.dense,
                "sparse": models.SparseVector(
                    indices=chunk.sparse.indices, values=chunk.sparse.values
                ),
            },
            payload={
                "tenant_id": input.tenant_id,
                "agent_id": input.agent_id,
                "document_id": input.document_id,
                "page": chunk.page,
                "section": chunk.section,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
            },
        )
        for chunk in document.chunks
    ]
    for start in range(0, len(points), 100):
        await client.upsert(
            collection_name=collection, points=points[start : start + 100], wait=True
        )
    return len(points)


@activity.defn(name="update_document_status")
async def update_document_status(input: StatusInput) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, uuid.UUID(input.document_id))
        if document is None:
            raise ValueError("Document no longer exists")
        document.status = DocumentStatus(input.status)
        document.chunk_count = input.chunk_count
        document.error = input.error
        await session.commit()


@activity.defn(name="cleanup_partial_vectors")
async def cleanup_partial_vectors(input: CleanupInput) -> None:
    await get_vector_store().delete_document_vectors(
        uuid.UUID(input.tenant_id),
        uuid.UUID(input.agent_id),
        uuid.UUID(input.document_id),
    )

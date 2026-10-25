import asyncio
import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from google import genai
from google.genai import errors, types

from app.services.ingestion_models import SparseVectorData

_TERM_RE = re.compile(r"[a-z0-9]+")
_SPARSE_BUCKETS = 1_000_003


class DenseEmbeddingProvider(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SparseEmbeddingProvider(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[SparseVectorData]: ...


class GeminiEmbeddingProvider:
    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self._embed([query], task_type="RETRIEVAL_QUERY")
        return embeddings[0]

    async def _embed(
        self, texts: Sequence[str], *, task_type: str
    ) -> list[list[float]]:
        delay = 1.0
        for attempt in range(6):
            try:
                response = await self._client.aio.models.embed_content(
                    model=self._model,
                    contents=list(texts),
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self._dimensions,
                    ),
                )
                if response.embeddings is None:
                    raise RuntimeError("Gemini returned no embeddings")
                return [list(item.values or []) for item in response.embeddings]
            except (errors.ClientError, errors.ServerError) as exc:
                status_code = getattr(exc, "code", None)
                retryable = status_code == 429 or (
                    isinstance(status_code, int) and status_code >= 500
                )
                if attempt == 5 or not retryable:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
        raise RuntimeError("Embedding retries exhausted")


class BM25SparseEmbeddingProvider:
    async def embed(self, texts: Sequence[str]) -> list[SparseVectorData]:
        tokenized = [_TERM_RE.findall(text.lower()) for text in texts]
        document_count = max(len(tokenized), 1)
        average_length = sum(len(terms) for terms in tokenized) / document_count
        document_frequency: Counter[str] = Counter()
        for terms in tokenized:
            document_frequency.update(set(terms))
        result: list[SparseVectorData] = []
        for terms in tokenized:
            counts = Counter(terms)
            values: dict[int, float] = {}
            for term, frequency in counts.items():
                digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
                index = int.from_bytes(digest, "big") % _SPARSE_BUCKETS
                inverse_document_frequency = math.log(
                    1
                    + (document_count - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                score = inverse_document_frequency * (frequency * 2.2) / (
                    frequency
                    + 1.2
                    * (0.25 + 0.75 * len(terms) / max(average_length, 1.0))
                )
                values[index] = values.get(index, 0.0) + score
            indices = sorted(values)
            result.append(
                SparseVectorData(indices=indices, values=[values[index] for index in indices])
            )
        return result


class SpladeSparseEmbeddingProvider:
    def __init__(self) -> None:
        from fastembed import SparseTextEmbedding

        self._model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

    async def embed(self, texts: Sequence[str]) -> list[SparseVectorData]:
        embeddings = await asyncio.to_thread(lambda: list(self._model.embed(list(texts))))
        return [
            SparseVectorData(indices=item.indices.tolist(), values=item.values.tolist())
            for item in embeddings
        ]

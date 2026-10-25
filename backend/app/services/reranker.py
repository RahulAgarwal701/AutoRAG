import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import cohere


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float


class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int
    ) -> list[RerankResult]: ...


class CohereReranker:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = cohere.ClientV2(api_key=api_key)
        self._model = model

    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int
    ) -> list[RerankResult]:
        response = await asyncio.to_thread(
            self._client.rerank,
            model=self._model,
            query=query,
            documents=list(documents),
            top_n=top_n,
        )
        return [
            RerankResult(index=result.index, score=result.relevance_score)
            for result in response.results
        ]

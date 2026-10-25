from types import SimpleNamespace

import pytest
from google.genai.types import EmbedContentConfig

from app.services.embeddings import GeminiEmbeddingProvider


class FakeAsyncModels:
    def __init__(self) -> None:
        self.model: str | None = None
        self.contents: list[str] = []
        self.config: EmbedContentConfig | None = None

    async def embed_content(
        self, *, model: str, contents: list[str], config: EmbedContentConfig
    ) -> SimpleNamespace:
        self.model = model
        self.contents = contents
        self.config = config
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[0.1, 0.2]),
                SimpleNamespace(values=[0.3, 0.4]),
            ]
        )


class FakeGeminiClient:
    def __init__(self) -> None:
        self.models = FakeAsyncModels()
        self.aio = SimpleNamespace(models=self.models)


@pytest.mark.asyncio
async def test_gemini_provider_batches_retrieval_document_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeGeminiClient()
    monkeypatch.setattr(
        "app.services.embeddings.genai.Client", lambda **_: client
    )
    provider = GeminiEmbeddingProvider("test-key", "gemini-embedding-001", 1536)

    vectors = await provider.embed(["first chunk", "second chunk"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert client.models.model == "gemini-embedding-001"
    assert client.models.contents == ["first chunk", "second chunk"]
    assert client.models.config is not None
    assert client.models.config.task_type == "RETRIEVAL_DOCUMENT"
    assert client.models.config.output_dimensionality == 1536


@pytest.mark.asyncio
async def test_gemini_provider_uses_retrieval_query_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeGeminiClient()
    monkeypatch.setattr("app.services.embeddings.genai.Client", lambda **_: client)
    provider = GeminiEmbeddingProvider("test-key", "gemini-embedding-001", 1536)

    vector = await provider.embed_query("What is the warranty?")

    assert vector == [0.1, 0.2]
    assert client.models.config is not None
    assert client.models.config.task_type == "RETRIEVAL_QUERY"

import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest

from app.agents.graph import FALLBACK_ANSWER, AgentState, AutoRAGGraph
from app.agents.llm import LLMMessage
from app.models.agent import Agent
from app.schemas.agent import AgentCreate
from app.services.query_rewriter import ChatTurn
from app.services.retrieval import RetrievedChunk


class FakeRewriter:
    async def rewrite(self, question: str, history: Sequence[ChatTurn]) -> str:
        del history
        return question


class FakeRetrieval:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    async def retrieve_standalone(self, **_: object) -> list[RetrievedChunk]:
        return self.chunks


class FakeLLM:
    def __init__(self, tokens: list[str], *, must_not_run: bool = False) -> None:
        self.tokens = tokens
        self.must_not_run = must_not_run

    async def stream(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
        temperature: float,
    ) -> AsyncIterator[str]:
        del model, system_prompt, messages, temperature
        if self.must_not_run:
            raise AssertionError("LLM must not run without relevant context")
        for token in self.tokens:
            yield token


class FakeTools:
    async def run(self, tools: object, query: str) -> None:
        del tools, query
        return None


def make_agent(tenant_id: uuid.UUID) -> Agent:
    return Agent(
        id=uuid.uuid4(),
        user_id=tenant_id,
        name="Test agent",
        system_prompt="Answer from documents.",
        model="test-model",
        llm_provider="openai",
        temperature=0.2,
        top_k=5,
        use_reranker=False,
        chunk_strategy="recursive",
        chunk_size_tokens=650,
        chunk_overlap_percent=0.12,
        allowed_origins=[],
        tools=[],
    )


def test_new_agents_default_to_free_tier_gemini() -> None:
    payload = AgentCreate(name="Free agent", system_prompt="Stay grounded.")

    assert payload.llm_provider == "gemini"
    assert payload.model == "gemini-3.5-flash-lite"


def test_grok_agent_uses_current_default_model() -> None:
    payload = AgentCreate(
        name="Grok agent",
        system_prompt="Stay grounded.",
        llm_provider="grok",
    )

    assert payload.llm_provider == "grok"
    assert payload.model == "grok-4.7"


async def run_graph(
    runtime: AutoRAGGraph, state: AgentState
) -> tuple[list[dict[str, Any]], AgentState]:
    events: list[dict[str, Any]] = []
    final_state: AgentState | None = None
    async for mode, data in runtime.graph.astream(
        state, stream_mode=["custom", "values"]
    ):
        if mode == "custom":
            events.append(data)
        else:
            final_state = data
    assert final_state is not None
    return events, final_state


@pytest.mark.asyncio
async def test_no_relevant_context_returns_fallback_without_calling_llm() -> None:
    tenant_id = uuid.uuid4()
    agent = make_agent(tenant_id)
    runtime = AutoRAGGraph(
        retrieval=FakeRetrieval([]),  # type: ignore[arg-type]
        query_rewriter=FakeRewriter(),
        llm=FakeLLM([], must_not_run=True),
        tools=FakeTools(),  # type: ignore[arg-type]
        relevance_threshold=0.2,
    )

    events, result = await run_graph(
        runtime,
        {
            "tenant_id": tenant_id,
            "agent": agent,
            "question": "What is the total?",
            "chat_history": [],
        },
    )

    assert result["answer"] == FALLBACK_ANSWER
    assert result["citations"] == []
    assert events == [{"type": "token", "text": FALLBACK_ANSWER}]


@pytest.mark.asyncio
async def test_stream_removes_unretrieved_citations_and_maps_valid_ones() -> None:
    tenant_id = uuid.uuid4()
    agent = make_agent(tenant_id)
    chunk = RetrievedChunk(
        text="The invoice total is $42.",
        score=0.9,
        document_id=uuid.uuid4(),
        document_name="invoice.pdf",
        page=2,
        section="Total",
        chunk_index=0,
        source_url="https://storage.test/invoice.pdf",
    )
    runtime = AutoRAGGraph(
        retrieval=FakeRetrieval([chunk]),  # type: ignore[arg-type]
        query_rewriter=FakeRewriter(),
        llm=FakeLLM(["The total is $42 [", "1], not [99]."]),
        tools=FakeTools(),  # type: ignore[arg-type]
        relevance_threshold=0.2,
    )

    events, result = await run_graph(
        runtime,
        {
            "tenant_id": tenant_id,
            "agent": agent,
            "question": "What is the total?",
            "chat_history": [],
        },
    )

    streamed = "".join(event["text"] for event in events)
    assert streamed == result["answer"]
    assert "[1]" in streamed
    assert "[99]" not in streamed
    assert result["citations"] == [
        {
            "document": "invoice.pdf",
            "page": 2,
            "snippet": "The invoice total is $42.",
            "link": "https://storage.test/invoice.pdf",
        }
    ]


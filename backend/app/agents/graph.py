import re
import uuid
from collections.abc import Callable, Sequence
from typing import Literal, NotRequired, TypedDict

import tiktoken
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.agents.llm import LLMMessage, LLMProvider
from app.agents.tools import ToolError, ToolExecutor, ToolResult
from app.models.agent import Agent
from app.schemas.chat import Citation
from app.services.query_rewriter import ChatTurn, QueryRewriter
from app.services.retrieval import RetrievalService, RetrievedChunk

FALLBACK_ANSWER = "I couldn't find that in your documents"


class AgentState(TypedDict):
    tenant_id: uuid.UUID
    agent: Agent
    question: str
    chat_history: Sequence[ChatTurn]
    standalone_query: NotRequired[str]
    chunks: NotRequired[list[RetrievedChunk]]
    relevant: NotRequired[bool]
    tool_result: NotRequired[ToolResult | None]
    answer: NotRequired[str]
    citations: NotRequired[list[dict[str, object]]]
    token_usage: NotRequired[dict[str, int | bool]]


def _citation_for(chunk: RetrievedChunk) -> Citation:
    snippet = " ".join(chunk.text.split())
    if len(snippet) > 280:
        snippet = f"{snippet[:277]}..."
    return Citation(
        document=chunk.document_name,
        page=chunk.page,
        snippet=snippet,
        link=chunk.source_url,
    )


def _token_count(text: str) -> int:
    return len(tiktoken.get_encoding("o200k_base").encode(text))


class CitationStreamGuard:
    """Streams prose while withholding citation-like text until it is validated."""

    def __init__(self, source_count: int, emit: Callable[[str], None]) -> None:
        self._source_count = source_count
        self._emit = emit
        self._pending = ""
        self.parts: list[str] = []
        self.cited: list[int] = []

    def feed(self, text: str) -> None:
        self._pending += text
        self._drain(final=False)

    def finish(self) -> tuple[str, list[int]]:
        self._drain(final=True)
        current_answer = "".join(self.parts).strip()
        if current_answer == FALLBACK_ANSWER:
            return current_answer, []
        if not self.cited and self._source_count:
            suffix = " [1]"
            self._send(suffix)
            self.cited.append(1)
        return "".join(self.parts).strip(), self.cited

    def _drain(self, *, final: bool) -> None:
        while self._pending:
            opening = self._pending.find("[")
            if opening == -1:
                self._send(self._pending)
                self._pending = ""
                return
            if opening:
                self._send(self._pending[:opening])
                self._pending = self._pending[opening:]
            closing = self._pending.find("]", 1)
            if closing == -1:
                if final:
                    self._send(self._pending)
                    self._pending = ""
                return
            candidate = self._pending[: closing + 1]
            match = re.fullmatch(r"\[(\d+)]", candidate)
            if match is None:
                self._send(candidate)
            else:
                index = int(match.group(1))
                if 1 <= index <= self._source_count:
                    self._send(candidate)
                    if index not in self.cited:
                        self.cited.append(index)
            self._pending = self._pending[closing + 1 :]

    def _send(self, text: str) -> None:
        if text:
            self.parts.append(text)
            self._emit(text)


class AutoRAGGraph:
    def __init__(
        self,
        *,
        retrieval: RetrievalService,
        query_rewriter: QueryRewriter,
        llm: LLMProvider,
        tools: ToolExecutor,
        relevance_threshold: float,
    ) -> None:
        self._retrieval = retrieval
        self._query_rewriter = query_rewriter
        self._llm = llm
        self._tools = tools
        self._relevance_threshold = relevance_threshold
        builder = StateGraph(AgentState)
        builder.add_node("rewrite_query", self._rewrite_query)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("grade_context", self._grade_context)
        builder.add_node("use_tools", self._use_tools)
        builder.add_node("generate_answer", self._generate_answer)
        builder.add_node("fallback", self._fallback)
        builder.add_edge(START, "rewrite_query")
        builder.add_edge("rewrite_query", "retrieve")
        builder.add_edge("retrieve", "grade_context")
        builder.add_conditional_edges(
            "grade_context",
            self._route_context,
            {"relevant": "use_tools", "irrelevant": "fallback"},
        )
        builder.add_edge("use_tools", "generate_answer")
        builder.add_edge("generate_answer", END)
        builder.add_edge("fallback", END)
        self.graph = builder.compile()

    async def _rewrite_query(self, state: AgentState) -> dict[str, object]:
        query = await self._query_rewriter.rewrite(
            state["question"], state["chat_history"]
        )
        return {"standalone_query": query}

    async def _retrieve(self, state: AgentState) -> dict[str, object]:
        chunks = await self._retrieval.retrieve_standalone(
            tenant_id=state["tenant_id"],
            agent=state["agent"],
            standalone_query=state["standalone_query"],
        )
        return {"chunks": chunks}

    async def _grade_context(self, state: AgentState) -> dict[str, object]:
        chunks = state.get("chunks", [])
        relevant_chunks = [chunk for chunk in chunks if chunk.text.strip()]
        relevant = bool(relevant_chunks) and max(
            chunk.score for chunk in relevant_chunks
        ) >= self._relevance_threshold
        return {"relevant": relevant}

    @staticmethod
    def _route_context(state: AgentState) -> Literal["relevant", "irrelevant"]:
        return "relevant" if state.get("relevant", False) else "irrelevant"

    async def _use_tools(self, state: AgentState) -> dict[str, object]:
        try:
            result = await self._tools.run(state["agent"].tools, state["question"])
        except ToolError:
            result = None
        return {"tool_result": result}

    async def _generate_answer(self, state: AgentState) -> dict[str, object]:
        chunks = state["chunks"]
        sources = "\n\n".join(
            f"[{index}] document={chunk.document_name}; page={chunk.page}; "
            f"section={chunk.section}\n{chunk.text}"
            for index, chunk in enumerate(chunks, 1)
        )
        tool_result = state.get("tool_result")
        tool_text = (
            f"\n\nOptional tool result ({tool_result.name}):\n{tool_result.output}"
            if tool_result is not None
            else ""
        )
        system_prompt = (
            f"{state['agent'].system_prompt}\n\n"
            "Answer only claims supported by the numbered document sources below. "
            "Cite every supported claim with its source number such as [1]. Never "
            "invent a source number. Tool output is supplemental and is not a citable "
            "document source. If the sources do not support an answer, reply exactly: "
            f"{FALLBACK_ANSWER}\n\nSources:\n{sources}{tool_text}"
        )
        writer = get_stream_writer()
        guard = CitationStreamGuard(
            len(chunks), lambda text: writer({"type": "token", "text": text})
        )
        messages = [
            *[
                LLMMessage(role=turn.role, content=turn.content)
                for turn in state["chat_history"]
            ],
            LLMMessage(role="user", content=state["question"]),
        ]
        async for token in self._llm.stream(
            model=state["agent"].model,
            system_prompt=system_prompt,
            messages=messages,
            temperature=state["agent"].temperature,
        ):
            guard.feed(token)
        answer, cited_indices = guard.finish()
        citations = [
            _citation_for(chunks[index - 1]).model_dump(mode="json")
            for index in cited_indices
        ]
        input_text = system_prompt + "\n" + "\n".join(
            message.content for message in messages
        )
        input_tokens = _token_count(input_text)
        output_tokens = _token_count(answer)
        return {
            "answer": answer,
            "citations": citations,
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "estimated": True,
            },
        }

    async def _fallback(self, _: AgentState) -> dict[str, object]:
        writer = get_stream_writer()
        writer({"type": "token", "text": FALLBACK_ANSWER})
        output_tokens = _token_count(FALLBACK_ANSWER)
        return {
            "answer": FALLBACK_ANSWER,
            "citations": [],
            "token_usage": {
                "input_tokens": 0,
                "output_tokens": output_tokens,
                "total_tokens": output_tokens,
                "estimated": True,
            },
        }


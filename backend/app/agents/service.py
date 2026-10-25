import json
import uuid
from collections.abc import AsyncIterator
from functools import lru_cache

from langfuse import Langfuse, propagate_attributes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import AgentState, AutoRAGGraph
from app.agents.llm import create_llm_provider
from app.agents.tools import ToolExecutor
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.agent import Agent
from app.models.chat import ChatSession, Message
from app.services.query_rewriter import ChatTurn, GeminiQueryRewriter
from app.services.retrieval import create_retrieval_service

logger = get_logger(__name__)


@lru_cache
def get_langfuse() -> Langfuse:
    settings = get_settings()
    enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_host,
        environment=settings.app_env,
        tracing_enabled=enabled,
    )


def encode_sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


class ChatAgentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def stream(
        self,
        *,
        tenant_id: uuid.UUID,
        agent: Agent,
        question: str,
        session_id: uuid.UUID | None,
    ) -> AsyncIterator[str]:
        async for event, data in self.stream_events(
            tenant_id=tenant_id,
            agent=agent,
            question=question,
            session_id=session_id,
        ):
            yield encode_sse(event, data)

    async def stream_events(
        self,
        *,
        tenant_id: uuid.UUID,
        agent: Agent,
        question: str,
        session_id: uuid.UUID | None,
    ) -> AsyncIterator[tuple[str, object]]:
        chat_session = await self._get_or_create_session(
            tenant_id=tenant_id,
            agent=agent,
            session_id=session_id,
            title=question[:200],
        )
        history = await self._load_history(tenant_id, chat_session.id)
        self._session.add(
            Message(
                user_id=tenant_id,
                chat_session_id=chat_session.id,
                role="user",
                content=question,
                citations=[],
            )
        )
        await self._session.commit()
        yield "session", {"session_id": str(chat_session.id)}

        settings = get_settings()
        if settings.gemini_api_key is None:
            raise RuntimeError("GEMINI_API_KEY is required for query rewriting and retrieval")
        query_rewriter = GeminiQueryRewriter(
            settings.gemini_api_key.get_secret_value(), settings.query_rewrite_model
        )
        runtime = AutoRAGGraph(
            retrieval=create_retrieval_service(self._session),
            query_rewriter=query_rewriter,
            llm=create_llm_provider(agent),
            tools=ToolExecutor(settings),
            relevance_threshold=settings.retrieval_relevance_threshold,
        )
        graph_input: AgentState = {
            "tenant_id": tenant_id,
            "agent": agent,
            "question": question,
            "chat_history": history,
        }
        final_state: AgentState | None = None
        langfuse = get_langfuse()
        with propagate_attributes(
            user_id=str(tenant_id),
            session_id=str(chat_session.id),
            metadata={"agent_id": str(agent.id)},
            tags=["autorag", agent.llm_provider],
            trace_name="autorag-chat",
        ):
            with langfuse.start_as_current_observation(
                name="autorag-agent-run",
                as_type="agent",
                input={"question": question, "agent_id": str(agent.id)},
                model=agent.model,
            ) as observation:
                async for mode, data in runtime.graph.astream(
                    graph_input,
                    stream_mode=["custom", "values"],
                ):
                    if mode == "custom":
                        if data.get("type") == "token":
                            yield "token", {"text": data["text"]}
                    elif mode == "values":
                        final_state = data
                if final_state is None:
                    raise RuntimeError("Agent graph completed without a final state")
                observation.update(
                    output={
                        "answer": final_state["answer"],
                        "citations": final_state["citations"],
                    }
                )

        self._session.add(
            Message(
                user_id=tenant_id,
                chat_session_id=chat_session.id,
                role="assistant",
                content=final_state["answer"],
                citations=final_state["citations"],
            )
        )
        await self._session.commit()
        usage = final_state["token_usage"]
        logger.info(
            "chat_completed",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent.id),
                "session_id": str(chat_session.id),
                "provider": agent.llm_provider,
                "model": agent.model,
                **usage,
            },
        )
        yield "usage", usage
        yield "citations", final_state["citations"]

    async def _get_or_create_session(
        self,
        *,
        tenant_id: uuid.UUID,
        agent: Agent,
        session_id: uuid.UUID | None,
        title: str,
    ) -> ChatSession:
        if session_id is not None:
            chat_session = await self._session.scalar(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == tenant_id,
                    ChatSession.agent_id == agent.id,
                )
            )
            if chat_session is None:
                raise LookupError("Chat session not found")
            return chat_session
        chat_session = ChatSession(
            user_id=tenant_id,
            agent_id=agent.id,
            title=title,
        )
        self._session.add(chat_session)
        await self._session.flush()
        return chat_session

    async def _load_history(
        self, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[ChatTurn]:
        messages = await self._session.scalars(
            select(Message)
            .where(
                Message.user_id == tenant_id,
                Message.chat_session_id == session_id,
            )
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return [ChatTurn(role=message.role, content=message.content) for message in messages]


from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


class QueryRewriter(Protocol):
    async def rewrite(self, question: str, history: Sequence[ChatTurn]) -> str: ...


class GeminiQueryRewriter:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def rewrite(self, question: str, history: Sequence[ChatTurn]) -> str:
        if not history:
            return question.strip()
        recent_history = history[-10:]
        transcript = "\n".join(
            f"{turn.role.upper()}: {turn.content}" for turn in recent_history
        )
        prompt = (
            f"Conversation:\n{transcript}\n\n"
            f"Follow-up question:\n{question}\n\n"
            "Standalone retrieval query:"
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Rewrite the user's latest question as one concise standalone search "
                    "query. Resolve references using the conversation. Preserve names, dates, "
                    "and constraints. Return only the rewritten query. Do not answer it."
                ),
                temperature=0,
            ),
        )
        rewritten = (response.text or "").strip().strip('"')
        return rewritten or question.strip()

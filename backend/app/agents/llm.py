from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from anthropic import AsyncAnthropic
from google import genai
from google.genai import types
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.models.agent import Agent


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


class LLMProvider(Protocol):
    def stream(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
        temperature: float,
    ) -> AsyncIterator[str]: ...


class GeminiProvider:
    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def stream(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
        temperature: float,
    ) -> AsyncIterator[str]:
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part.from_text(text=message.content)],
            )
            for message in messages
        ]
        stream = await self._client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text


class OpenAIProvider:
    def __init__(self, api_key: str, *, base_url: str | None = None) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def stream(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
        temperature: float,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                *[{"role": message.role, "content": message.content} for message in messages],
            ],
            stream=True,
        )
        async for event in stream:
            text = event.choices[0].delta.content
            if text:
                yield text


class GrokProvider(OpenAIProvider):
    """xAI's OpenAI-compatible streaming chat provider."""

    def __init__(self, api_key: str, base_url: str) -> None:
        super().__init__(api_key, base_url=base_url)


class ClaudeProvider:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def stream(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
        temperature: float,
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=model,
            max_tokens=2_048,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": message.role, "content": message.content} for message in messages],
        ) as stream:
            async for text in stream.text_stream:
                yield text


def create_llm_provider(agent: Agent) -> LLMProvider:
    settings = get_settings()
    if agent.llm_provider == "gemini":
        if settings.gemini_api_key is None:
            raise RuntimeError("GEMINI_API_KEY is required for this agent")
        return GeminiProvider(settings.gemini_api_key.get_secret_value())
    if agent.llm_provider == "openai":
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for this agent")
        return OpenAIProvider(settings.openai_api_key.get_secret_value())
    if agent.llm_provider == "grok":
        if settings.xai_api_key is None:
            raise RuntimeError("XAI_API_KEY is required for this agent")
        return GrokProvider(
            settings.xai_api_key.get_secret_value(),
            settings.xai_base_url,
        )
    if agent.llm_provider == "claude":
        if settings.anthropic_api_key is None:
            raise RuntimeError("ANTHROPIC_API_KEY is required for this agent")
        return ClaudeProvider(settings.anthropic_api_key.get_secret_value())
    raise ValueError(f"Unsupported LLM provider: {agent.llm_provider}")

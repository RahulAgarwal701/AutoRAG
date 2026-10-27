import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalculatorToolConfig(BaseModel):
    type: Literal["calculator"]
    enabled: bool = True


class WebSearchToolConfig(BaseModel):
    type: Literal["web_search"]
    enabled: bool = True


class WebhookToolConfig(BaseModel):
    type: Literal["webhook"]
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=500)
    url: str = Field(pattern=r"^https://")
    enabled: bool = True


AgentToolConfig = Annotated[
    CalculatorToolConfig | WebSearchToolConfig | WebhookToolConfig,
    Field(discriminator="type"),
]


def _default_theme() -> dict[str, object]:
    return {"primary_color": "#111827", "position": "bottom-right"}


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    greeting: str = Field(default="Hi! How can I help?", min_length=1, max_length=500)
    theme: dict[str, object] = Field(default_factory=_default_theme)
    system_prompt: str = Field(min_length=1, max_length=20_000)
    model: str = Field(default="gemini-3.5-flash-lite", min_length=1, max_length=120)
    llm_provider: Literal["gemini", "grok", "openai", "claude"] = "gemini"
    temperature: float = Field(default=0.2, ge=0, le=2)
    top_k: int = Field(default=5, ge=1, le=100)
    use_reranker: bool = False
    chunk_strategy: Literal["recursive", "semantic"] = "recursive"
    chunk_size_tokens: int = Field(default=650, ge=500, le=800)
    chunk_overlap_percent: float = Field(default=0.12, ge=0.10, le=0.15)
    allowed_origins: list[str] = Field(default_factory=list)
    tools: list[AgentToolConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def select_provider_default_model(self) -> "AgentCreate":
        if self.llm_provider == "grok" and self.model == "gemini-3.5-flash-lite":
            self.model = "grok-4.7"
        return self


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=20_000)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    llm_provider: Literal["gemini", "grok", "openai", "claude"] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_k: int | None = Field(default=None, ge=1, le=100)
    use_reranker: bool | None = None
    tools: list[AgentToolConfig] | None = None


class AgentLLMUpdate(BaseModel):
    llm_provider: Literal["gemini", "grok", "openai", "claude"]
    model: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def select_provider_default_model(self) -> "AgentLLMUpdate":
        if self.model is None:
            self.model = {
                "gemini": "gemini-3.5-flash-lite",
                "grok": "grok-4.7",
                "openai": "gpt-4o-mini",
                "claude": "claude-3-5-haiku-latest",
            }[self.llm_provider]
        return self


class AgentWidgetUpdate(BaseModel):
    greeting: str = Field(min_length=1, max_length=500)
    theme: dict[str, object]
    allowed_origins: list[str] = Field(min_length=1)


class AgentRead(AgentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime

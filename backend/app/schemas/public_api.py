import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import Citation


class PublicChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "What is the invoice total?",
                    "session_id": None,
                    "stream": True,
                }
            ]
        }
    )

    message: str = Field(min_length=1, max_length=20_000)
    session_id: uuid.UUID | None = None
    stream: bool = True


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated: bool = True


class PublicChatResponse(BaseModel):
    session_id: uuid.UUID
    answer: str
    citations: list[Citation]
    usage: TokenUsage


class PublicAgentConfig(BaseModel):
    name: str
    greeting: str
    theme: dict[str, Any]


class WidgetSessionResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail

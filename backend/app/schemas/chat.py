import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    session_id: uuid.UUID | None = None


class Citation(BaseModel):
    document: str
    page: int | None = None
    snippet: str
    link: str


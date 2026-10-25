import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    filename: str
    status: DocumentStatus
    error: str | None
    chunk_count: int
    created_at: datetime


class PresignedUrlResponse(BaseModel):
    url: str
    expires_in: int


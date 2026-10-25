import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prefix: str
    last_used_at: datetime | None
    revoked: bool
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    key: str


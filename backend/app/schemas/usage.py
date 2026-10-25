from pydantic import BaseModel


class DocumentUsage(BaseModel):
    total: int
    pending: int
    processing: int
    ready: int
    failed: int
    indexed_chunks: int


class UsageSummary(BaseModel):
    agents: int
    documents: DocumentUsage
    chat_sessions: int
    messages: int
    active_api_keys: int

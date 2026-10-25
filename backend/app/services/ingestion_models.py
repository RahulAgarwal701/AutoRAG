from typing import Literal

from pydantic import BaseModel, Field


class ParsedBlock(BaseModel):
    text: str
    page: int | None = None
    section: str | None = None


class ParsedDocument(BaseModel):
    blocks: list[ParsedBlock]


class Chunk(BaseModel):
    text: str
    chunk_index: int
    page: int | None = None
    section: str | None = None


class ChunkedDocument(BaseModel):
    chunks: list[Chunk]


class SparseVectorData(BaseModel):
    indices: list[int]
    values: list[float]


class EmbeddedChunk(Chunk):
    dense: list[float]
    sparse: SparseVectorData


class EmbeddedDocument(BaseModel):
    chunks: list[EmbeddedChunk]


class ChunkingConfig(BaseModel):
    strategy: Literal["recursive", "semantic"] = "recursive"
    size_tokens: int = Field(default=650, ge=500, le=800)
    overlap_percent: float = Field(default=0.12, ge=0.10, le=0.15)

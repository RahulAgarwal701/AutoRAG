import re
from collections.abc import Iterable

import tiktoken

from app.services.ingestion_models import (
    Chunk,
    ChunkedDocument,
    ChunkingConfig,
    ParsedBlock,
    ParsedDocument,
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text))


def _split_tokens(text: str, size: int, overlap: int) -> Iterable[str]:
    encoder = _encoder()
    tokens = encoder.encode(text)
    step = max(1, size - overlap)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + size]
        if not window:
            break
        yield encoder.decode(window).strip()
        if start + size >= len(tokens):
            break


def _lexical_similarity(left: str, right: str) -> float:
    left_terms = set(_WORD_RE.findall(left.lower()))
    right_terms = set(_WORD_RE.findall(right.lower()))
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def _semantic_groups(blocks: list[ParsedBlock], target_tokens: int) -> list[ParsedBlock]:
    groups: list[ParsedBlock] = []
    current: ParsedBlock | None = None
    previous_text = ""
    for block in blocks:
        starts_topic = (
            current is not None
            and count_tokens(current.text) >= target_tokens // 2
            and (
                block.section != current.section
                or _lexical_similarity(previous_text, block.text) < 0.08
            )
        )
        if current is None or starts_topic:
            if current is not None:
                groups.append(current)
            current = block.model_copy()
        else:
            current.text = f"{current.text}\n\n{block.text}"
        previous_text = block.text
    if current is not None:
        groups.append(current)
    return groups


def chunk_document_data(document: ParsedDocument, config: ChunkingConfig) -> ChunkedDocument:
    overlap = round(config.size_tokens * config.overlap_percent)
    source_blocks = document.blocks
    if config.strategy == "semantic":
        source_blocks = _semantic_groups(source_blocks, config.size_tokens)

    chunks: list[Chunk] = []
    for block in source_blocks:
        for text in _split_tokens(block.text, config.size_tokens, overlap):
            if text:
                chunks.append(
                    Chunk(
                        text=text,
                        chunk_index=len(chunks),
                        page=block.page,
                        section=block.section,
                    )
                )
    return ChunkedDocument(chunks=chunks)

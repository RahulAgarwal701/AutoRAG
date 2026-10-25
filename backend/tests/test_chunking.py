from app.services.chunking import chunk_document_data, count_tokens
from app.services.ingestion_models import ChunkingConfig, ParsedBlock, ParsedDocument


def test_recursive_chunking_respects_size_overlap_and_metadata() -> None:
    text = " ".join(f"token-{index}" for index in range(1500))
    result = chunk_document_data(
        ParsedDocument(blocks=[ParsedBlock(text=text, page=7, section="Limits")]),
        ChunkingConfig(strategy="recursive", size_tokens=500, overlap_percent=0.10),
    )

    assert len(result.chunks) > 1
    assert all(count_tokens(chunk.text) <= 500 for chunk in result.chunks)
    assert all(chunk.page == 7 and chunk.section == "Limits" for chunk in result.chunks)
    assert [chunk.chunk_index for chunk in result.chunks] == list(range(len(result.chunks)))


def test_semantic_chunking_keeps_section_boundaries() -> None:
    first = "billing invoice payment " * 130
    second = "security encryption authentication " * 130
    result = chunk_document_data(
        ParsedDocument(
            blocks=[
                ParsedBlock(text=first, page=1, section="Billing"),
                ParsedBlock(text=second, page=2, section="Security"),
            ]
        ),
        ChunkingConfig(strategy="semantic", size_tokens=500, overlap_percent=0.10),
    )

    assert {chunk.section for chunk in result.chunks} == {"Billing", "Security"}
    assert all(chunk.page in {1, 2} for chunk in result.chunks)

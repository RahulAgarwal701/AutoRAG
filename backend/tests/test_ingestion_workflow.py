from datetime import timedelta

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflows.activities import (
    ChunkInput,
    CleanupInput,
    DownloadInput,
    EmbedInput,
    ParseInput,
    StatusInput,
    UpsertInput,
)
from app.workflows.ingestion import IngestDocumentWorkflow, IngestionWorkflowInput


@activity.defn(name="download_from_s3")
async def fake_download(input: DownloadInput) -> str:
    return f"{input.artifact_prefix}/source.bin"


@activity.defn(name="parse_document")
async def fake_parse(input: ParseInput) -> str:
    return f"{input.artifact_prefix}/parsed.json"


@activity.defn(name="chunk_document")
async def fake_chunk(input: ChunkInput) -> str:
    return f"{input.artifact_prefix}/chunks.json"


@activity.defn(name="embed_chunks")
async def fake_embed(input: EmbedInput) -> str:
    return f"{input.artifact_prefix}/embedded.json"


@activity.defn(name="upsert_to_qdrant")
async def fake_upsert(input: UpsertInput) -> int:
    return 3


@activity.defn(name="update_document_status")
async def fake_status(input: StatusInput) -> None:
    del input


@activity.defn(name="cleanup_partial_vectors")
async def fake_cleanup(input: CleanupInput) -> None:
    del input


@pytest.mark.asyncio
async def test_ingestion_workflow_completes_with_test_environment() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as environment:
        task_queue = "test-ingestion"
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[IngestDocumentWorkflow],
            activities=[
                fake_download,
                fake_parse,
                fake_chunk,
                fake_embed,
                fake_upsert,
                fake_status,
                fake_cleanup,
            ],
        ):
            result = await environment.client.execute_workflow(
                IngestDocumentWorkflow.run,
                IngestionWorkflowInput(
                    user_id="11111111-1111-1111-1111-111111111111",
                    agent_id="22222222-2222-2222-2222-222222222222",
                    document_id="33333333-3333-3333-3333-333333333333",
                    s3_key="tenants/source.pdf",
                    filename="source.pdf",
                ),
                id="test-ingestion-success",
                task_queue=task_queue,
                execution_timeout=timedelta(seconds=30),
            )

    assert result == "33333333-3333-3333-3333-333333333333"

from dataclasses import dataclass
from datetime import timedelta

from temporalio import common, workflow

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        ChunkInput,
        CleanupInput,
        DownloadInput,
        EmbedInput,
        ParseInput,
        StatusInput,
        UpsertInput,
        chunk_document,
        cleanup_partial_vectors,
        download_from_s3,
        embed_chunks,
        parse_document,
        update_document_status,
        upsert_to_qdrant,
    )


@dataclass(frozen=True)
class IngestionWorkflowInput:
    user_id: str
    agent_id: str
    document_id: str
    s3_key: str
    filename: str
    chunk_strategy: str = "recursive"
    chunk_size_tokens: int = 650
    chunk_overlap_percent: float = 0.12


@workflow.defn(name="document-ingestion")
class IngestDocumentWorkflow:
    @workflow.run
    async def run(self, workflow_input: IngestionWorkflowInput) -> str:
        normal_retry = common.RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2,
            maximum_interval=timedelta(minutes=1),
            maximum_attempts=5,
        )
        embedding_retry = common.RetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2,
            maximum_interval=timedelta(minutes=2),
            maximum_attempts=8,
        )
        compensation_retry = common.RetryPolicy(
            initial_interval=timedelta(seconds=1), maximum_attempts=10
        )
        artifact_prefix = f"{workflow_input.s3_key}.ingestion"
        try:
            await workflow.execute_activity(
                update_document_status,
                StatusInput(workflow_input.document_id, "processing"),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=normal_retry,
            )
            source_key = await workflow.execute_activity(
                download_from_s3,
                DownloadInput(workflow_input.s3_key, artifact_prefix),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=normal_retry,
            )
            parsed_key = await workflow.execute_activity(
                parse_document,
                ParseInput(source_key, workflow_input.filename, artifact_prefix),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=normal_retry,
            )
            chunks_key = await workflow.execute_activity(
                chunk_document,
                ChunkInput(
                    parsed_key,
                    artifact_prefix,
                    workflow_input.chunk_strategy,
                    workflow_input.chunk_size_tokens,
                    workflow_input.chunk_overlap_percent,
                ),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=normal_retry,
            )
            embedded_key = await workflow.execute_activity(
                embed_chunks,
                EmbedInput(chunks_key, artifact_prefix),
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=embedding_retry,
            )
            chunk_count = await workflow.execute_activity(
                upsert_to_qdrant,
                UpsertInput(
                    embedded_key,
                    workflow_input.user_id,
                    workflow_input.agent_id,
                    workflow_input.document_id,
                ),
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=normal_retry,
            )
            await workflow.execute_activity(
                update_document_status,
                StatusInput(workflow_input.document_id, "ready", chunk_count),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=normal_retry,
            )
            return workflow_input.document_id
        except Exception as exc:
            await workflow.execute_activity(
                cleanup_partial_vectors,
                CleanupInput(
                    workflow_input.user_id,
                    workflow_input.agent_id,
                    workflow_input.document_id,
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=compensation_retry,
            )
            await workflow.execute_activity(
                update_document_status,
                StatusInput(
                    workflow_input.document_id,
                    "failed",
                    error=str(exc)[:2000],
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=compensation_retry,
            )
            raise


DocumentIngestionWorkflow = IngestDocumentWorkflow

import asyncio
import uuid
from functools import lru_cache
from typing import Protocol

from temporalio.client import Client

from app.core.config import get_settings
from app.workflows.ingestion import IngestDocumentWorkflow, IngestionWorkflowInput


class WorkflowStarter(Protocol):
    async def start_document_ingestion(
        self,
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        document_id: uuid.UUID,
        s3_key: str,
        filename: str,
        chunk_strategy: str,
        chunk_size_tokens: int,
        chunk_overlap_percent: float,
    ) -> None: ...


class TemporalWorkflowStarter:
    def __init__(self, address: str, namespace: str, task_queue: str) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue
        self._client: Client | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Client:
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = await Client.connect(
                    self._address,
                    namespace=self._namespace,
                )
        return self._client

    async def start_document_ingestion(
        self,
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        document_id: uuid.UUID,
        s3_key: str,
        filename: str,
        chunk_strategy: str,
        chunk_size_tokens: int,
        chunk_overlap_percent: float,
    ) -> None:
        client = await self._get_client()
        await client.start_workflow(
            IngestDocumentWorkflow.run,
            IngestionWorkflowInput(
                user_id=str(user_id),
                agent_id=str(agent_id),
                document_id=str(document_id),
                s3_key=s3_key,
                filename=filename,
                chunk_strategy=chunk_strategy,
                chunk_size_tokens=chunk_size_tokens,
                chunk_overlap_percent=chunk_overlap_percent,
            ),
            id=f"document-ingestion-{document_id}",
            task_queue=self._task_queue,
        )


@lru_cache
def get_workflow_starter() -> WorkflowStarter:
    settings = get_settings()
    return TemporalWorkflowStarter(
        address=settings.temporal_address,
        namespace=settings.temporal_namespace,
        task_queue=settings.temporal_task_queue,
    )


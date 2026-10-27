import asyncio

from temporalio.worker import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.observability import configure_sentry
from app.workflows.activities import (
    chunk_document,
    cleanup_partial_vectors,
    download_from_s3,
    embed_chunks,
    parse_document,
    update_document_status,
    upsert_to_qdrant,
)
from app.workflows.connection import connect_temporal
from app.workflows.ingestion import IngestDocumentWorkflow


async def create_worker() -> Worker:
    settings = get_settings()
    client = await connect_temporal(settings)
    return Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[IngestDocumentWorkflow],
        activities=[
            download_from_s3,
            parse_document,
            chunk_document,
            embed_chunks,
            upsert_to_qdrant,
            update_document_status,
            cleanup_partial_vectors,
        ],
    )


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_sentry(settings)
    logger = get_logger(__name__)
    worker = await create_worker()
    logger.info("temporal_worker_started", extra={"task_queue": settings.temporal_task_queue})
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())

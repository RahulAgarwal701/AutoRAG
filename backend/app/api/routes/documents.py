import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import (
    CurrentUser,
    DatabaseSession,
    IngestionWorkflowStarter,
    StorageService,
    VectorStoreService,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentRead, PresignedUrlResponse
from app.services.document_uploads import UploadValidationError, validate_document_upload
from app.services.tenancy import get_owned_agent, get_owned_document

router = APIRouter(prefix="/agents/{agent_id}/documents", tags=["documents"])
settings = get_settings()
logger = get_logger(__name__)


def _document_key(
    user_id: uuid.UUID, agent_id: uuid.UUID, document_id: uuid.UUID, filename: str
) -> str:
    return f"tenants/{user_id}/agents/{agent_id}/documents/{document_id}/{filename}"


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    agent_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    storage: StorageService,
    workflow_starter: IngestionWorkflowStarter,
    file: Annotated[UploadFile, File()],
) -> Document:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        validated = await validate_document_upload(
            file,
            max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    document_id = uuid.uuid4()
    s3_key = _document_key(current_user.id, agent.id, document_id, validated.filename)
    try:
        await storage.upload(file.file, s3_key, validated.content_type)
    except Exception as exc:
        logger.exception("document_storage_upload_failed", extra={"document_id": document_id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to store the document",
        ) from exc

    document = Document(
        id=document_id,
        user_id=current_user.id,
        agent_id=agent.id,
        filename=validated.filename,
        s3_key=s3_key,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    try:
        await session.commit()
        await session.refresh(document)
    except SQLAlchemyError as exc:
        await session.rollback()
        try:
            await storage.delete(s3_key)
        except Exception:
            logger.exception("orphaned_document_cleanup_failed", extra={"document_id": document_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the document record",
        ) from exc

    try:
        await workflow_starter.start_document_ingestion(
            user_id=current_user.id,
            agent_id=agent.id,
            document_id=document.id,
            s3_key=document.s3_key,
            filename=document.filename,
            chunk_strategy=agent.chunk_strategy,
            chunk_size_tokens=agent.chunk_size_tokens,
            chunk_overlap_percent=agent.chunk_overlap_percent,
        )
    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error = "Unable to start ingestion workflow"
        await session.commit()
        logger.exception("document_workflow_start_failed", extra={"document_id": document.id})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document stored, but ingestion could not be started",
        ) from exc
    return document


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    agent_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
) -> list[Document]:
    agent = await get_owned_agent(session, current_user.id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    query = select(Document).where(
        Document.agent_id == agent_id,
        Document.user_id == current_user.id,
    )
    if status_filter is not None:
        query = query.where(Document.status == status_filter)
    result = await session.scalars(query.order_by(Document.created_at.desc()))
    return list(result)


@router.get("/{document_id}", response_model=DocumentRead)
async def read_document(
    agent_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Document:
    document = await get_owned_document(session, current_user.id, agent_id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/{document_id}/view-url", response_model=PresignedUrlResponse)
async def create_document_view_url(
    agent_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    storage: StorageService,
) -> PresignedUrlResponse:
    document = await get_owned_document(session, current_user.id, agent_id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        url = await storage.create_presigned_get_url(document.s3_key, document.filename)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to generate a document URL",
        ) from exc
    return PresignedUrlResponse(
        url=url,
        expires_in=settings.s3_presigned_url_expiry_seconds,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    agent_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    storage: StorageService,
    vector_store: VectorStoreService,
) -> Response:
    document = await get_owned_document(session, current_user.id, agent_id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        await vector_store.delete_document_vectors(current_user.id, agent_id, document.id)
        await storage.delete(document.s3_key)
    except Exception as exc:
        logger.exception("document_external_delete_failed", extra={"document_id": document.id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to delete document data",
        ) from exc
    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

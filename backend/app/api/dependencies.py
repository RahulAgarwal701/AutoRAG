from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, decode_token
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import get_user_by_id
from app.services.storage import ObjectStorage, get_storage_service
from app.services.vector_store import VectorStore, get_vector_store
from app.workflows.client import WorkflowStarter, get_workflow_starter

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
StorageService = Annotated[ObjectStorage, Depends(get_storage_service)]
VectorStoreService = Annotated[VectorStore, Depends(get_vector_store)]
IngestionWorkflowStarter = Annotated[WorkflowStarter, Depends(get_workflow_starter)]


async def get_current_user(
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        user_id = decode_token(credentials.credentials, "access")
    except InvalidTokenError as exc:
        raise unauthorized from exc

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


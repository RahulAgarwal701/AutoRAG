from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DatabaseSession
from app.core.security import InvalidTokenError, create_token_pair, decode_token
from app.schemas.auth import AuthResponse, Credentials, RefreshRequest, TokenPair, UserRead
from app.services.auth import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    get_user_by_id,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: Credentials, session: DatabaseSession) -> AuthResponse:
    try:
        user = await register_user(session, payload.email, payload.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    access_token, refresh_token = create_token_pair(user.id)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: Credentials, session: DatabaseSession) -> AuthResponse:
    user = await authenticate_user(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, refresh_token = create_token_pair(user.id)
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(payload: RefreshRequest, session: DatabaseSession) -> TokenPair:
    try:
        user_id = decode_token(payload.refresh_token, "refresh")
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access_token, refresh_token = create_token_pair(user.id)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)

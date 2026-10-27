import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]
password_hasher = PasswordHasher()


class InvalidTokenError(ValueError):
    pass


@dataclass(frozen=True)
class WidgetSessionClaims:
    agent_id: uuid.UUID
    user_id: uuid.UUID
    origin: str
    token_id: uuid.UUID


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_token(subject: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_token_pair(user_id: uuid.UUID) -> tuple[str, str]:
    settings = get_settings()
    access_token = create_token(
        user_id,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_token(
        user_id,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )
    return access_token, refresh_token


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != expected_type or not isinstance(payload.get("sub"), str):
            raise InvalidTokenError("Unexpected token type or subject")
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidTokenError("Invalid or expired token") from exc


def create_widget_session_token(agent_id: uuid.UUID, user_id: uuid.UUID, origin: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(agent_id),
        "tenant_id": str(user_id),
        "origin": origin,
        "type": "widget",
        "iat": now,
        "exp": now + timedelta(minutes=settings.widget_session_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_widget_session_token(token: str) -> WidgetSessionClaims:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "widget":
            raise InvalidTokenError("Unexpected token type")
        origin = payload.get("origin")
        if not isinstance(origin, str) or not origin:
            raise InvalidTokenError("Missing widget origin")
        return WidgetSessionClaims(
            agent_id=uuid.UUID(str(payload["sub"])),
            user_id=uuid.UUID(str(payload["tenant_id"])),
            origin=origin,
            token_id=uuid.UUID(str(payload["jti"])),
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError("Invalid or expired widget session token") from exc


def generate_api_key() -> tuple[str, str, str]:
    full_key = f"ark_live_{secrets.token_urlsafe(32)}"
    prefix = full_key[:17]
    hashed_key = hash_api_key(full_key)
    return full_key, prefix, hashed_key


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

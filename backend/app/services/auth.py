import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


class EmailAlreadyRegisteredError(ValueError):
    pass


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    normalized_email = email.strip().lower()
    existing_user = await session.scalar(select(User.id).where(User.email == normalized_email))
    if existing_user is not None:
        raise EmailAlreadyRegisteredError

    user = User(email=normalized_email, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise EmailAlreadyRegisteredError from exc
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = await session.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user

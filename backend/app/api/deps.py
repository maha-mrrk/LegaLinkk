"""Shared FastAPI dependencies (authentication)."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository


class AuthenticationError(AppError):
    """Raised when the bearer token is missing or invalid."""

    def __init__(self, message: str = "Authentification requise") -> None:
        super().__init__(message, status_code=401)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer`` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError()

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if payload is None:
        raise AuthenticationError("Session expirée ou invalide")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Session invalide")

    try:
        user_id = UUID(str(subject))
    except ValueError:
        raise AuthenticationError("Session invalide")

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Compte introuvable ou désactivé")
    return user

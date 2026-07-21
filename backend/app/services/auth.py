"""Authentication service: registration, login, and token issuance."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository

logger = get_logger(__name__)


class AuthError(AppError):
    """Raised when authentication fails (invalid credentials)."""

    def __init__(self, message: str = "Identifiants invalides") -> None:
        super().__init__(message, status_code=401)


class ConflictError(AppError):
    """Raised when a resource already exists (e.g. email taken)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class AuthService:
    """Handle account creation and credential verification."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = UserRepository(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str | None = None,
    ) -> tuple[User, str]:
        existing = await self._repo.get_by_email(email)
        if existing is not None:
            raise ConflictError("Un compte existe déjà avec cette adresse e-mail")

        user = await self._repo.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=(role or "Juriste"),
        )
        await self._session.commit()
        await self._session.refresh(user)
        logger.info("User registered id=%s email=%s", user.id, user.email)
        return user, self._issue_token(user)

    async def authenticate(self, *, email: str, password: str) -> tuple[User, str]:
        user = await self._repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthError()
        if not user.is_active:
            raise AuthError("Ce compte est désactivé")
        logger.info("User logged in id=%s", user.id)
        return user, self._issue_token(user)

    async def get_user(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Utilisateur introuvable")
        return user

    def _issue_token(self, user: User) -> str:
        return create_access_token(
            str(user.id),
            extra_claims={"email": user.email, "role": user.role},
        )

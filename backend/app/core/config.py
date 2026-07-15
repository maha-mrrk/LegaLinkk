"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Values are loaded from environment variables and an optional ``.env`` file.
    Field names map to uppercase env vars (e.g. ``app_name`` → ``APP_NAME``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "LegalLink"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    postgres_user: str = "legallink"
    postgres_password: str = "legallink"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "legallink"

    # Document storage
    storage_path: str = "storage/documents"
    max_upload_size_mb: int = 25
    allowed_mime_types: str = "application/pdf"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_mime_type_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_mime_types.split(",") if item.strip()}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL (asyncpg)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy connection URL (psycopg2) used by Alembic."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

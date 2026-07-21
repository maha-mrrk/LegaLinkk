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

    # OCR / extraction pipeline (tuned for low-RAM hosts)
    ocr_enabled: bool = True
    ocr_lang: str = "en"  # PaddleOCR: en | french | arabic | ...
    ocr_min_chars_per_page: int = 30
    # Lower scale = less RAM / faster CPU OCR on scanned A4 pages.
    ocr_render_scale: float = 1.0
    # Cap longest pixmap side (px) before OCR to avoid huge bitmaps.
    ocr_max_image_side: int = 1280
    # Angle classifier doubles model memory; disable on low-RAM machines.
    ocr_use_angle_cls: bool = False
    # First OCR run may download Paddle models; keep a generous timeout.
    ocr_timeout_seconds: int = 1800

    # Chunking (RAG preprocessing)
    chunk_size: int = 900
    chunk_overlap: int = 175

    # Semantic indexing (pgvector + embeddings)
    embedding_model: str = "BAAI/bge-m3"
    embedding_fallback_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 2
    embedding_cache_dir: str = "/root/.cache/fastembed"
    auto_index_on_process: bool = True

    # Semantic retrieval (pgvector cosine Top-K)
    retrieval_top_k: int = 5
    # Candidate pool size before CrossEncoder reranking
    retrieval_candidate_k: int = 15

    # CrossEncoder reranking
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_fallback_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_final_k: int = 5
    reranker_cache_dir: str = "/root/.cache/fastembed"

    # LLM / RAG generation (OpenAI-compatible: openai | nvidia_nim | groq)
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 120.0
    rag_max_context_chars: int = 12000
    rag_no_answer_message: str = (
        "I cannot answer this question based on the uploaded documents."
    )

    # Conversation memory (recent turns injected into the prompt)
    conversation_history_limit: int = 10

    # Authentication (JWT)
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

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

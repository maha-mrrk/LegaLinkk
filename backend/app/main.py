"""FastAPI application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.db.session import engine
from app.utils.storage import DocumentStorage

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle hooks."""
    setup_logging(settings.log_level)
    DocumentStorage(settings).ensure_directory()
    logger.info(
        "Starting %s v%s [%s]",
        settings.app_name,
        __version__,
        settings.app_env,
    )
    yield
    await engine.dispose()
    logger.info("Shutdown complete — database engine disposed")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "LegalLink — AI-powered platform for analysing legal contracts "
            "and regulatory documents."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    application.include_router(api_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()

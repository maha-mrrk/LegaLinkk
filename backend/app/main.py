"""FastAPI application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        # Domain errors already carry a professional, user-safe message. Log the
        # technical detail (if any) for diagnostics without exposing it.
        detail = getattr(exc, "detail", None)
        if exc.status_code >= 500:
            logger.error(
                "AppError %s on %s %s: %s",
                exc.status_code,
                request.method,
                request.url.path,
                detail or exc.message,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                "retryable": exc.retryable,
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Return a clean, human-readable message instead of raw pydantic errors.
        first = (exc.errors() or [{}])[0]
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body") or None
        message = "Certaines informations fournies sont invalides."
        if field:
            message = f"Le champ « {field} » est invalide."
        return JSONResponse(
            status_code=422,
            content={"detail": message, "code": "validation", "retryable": False},
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Never leak stack traces or internal details to the client.
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": (
                    "Une erreur inattendue est survenue. "
                    "Veuillez réessayer dans un instant."
                ),
                "code": "internal_error",
                "retryable": True,
            },
        )

    application.include_router(api_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()

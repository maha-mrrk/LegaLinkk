"""Application-specific exceptions mapped to HTTP responses.

Every error carries a user-facing ``message`` (professional, non-technical —
safe to show to lawyers/business users), a machine-readable ``code`` and a
``retryable`` hint so the frontend can guide the user on what to do next.
"""

from __future__ import annotations


class AppError(Exception):
    """Base application error with an HTTP status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code or self._default_code()
        self.retryable = retryable
        super().__init__(message)

    def _default_code(self) -> str:
        # e.g. NotFoundError -> "not_found", ValidationError -> "validation"
        name = type(self).__name__
        if name.endswith("Error"):
            name = name[: -len("Error")]
        # CamelCase -> snake_case
        out = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0:
                out.append("_")
            out.append(ch.lower())
        return "".join(out) or "error"


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404, code="not_found")


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400, code="validation")


class PayloadTooLargeError(AppError):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=413, code="payload_too_large")


class ServiceUnavailableError(AppError):
    """Raised when a downstream dependency (queue, cache, provider) is down."""

    def __init__(
        self,
        message: str = (
            "Le service est momentanément indisponible. "
            "Veuillez réessayer dans un instant."
        ),
    ) -> None:
        super().__init__(
            message, status_code=503, code="service_unavailable", retryable=True
        )

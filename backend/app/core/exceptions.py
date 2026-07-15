"""Application-specific exceptions mapped to HTTP responses."""


class AppError(Exception):
    """Base application error with an HTTP status code."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class PayloadTooLargeError(AppError):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=413)

"""Shared LangGraph retry policy (single source of truth for both graphs).

Only *transient* failures are retried (timeouts, 429 rate limits, 5xx, network
blips). Permanent errors — validation, missing document, auth/config problems —
fail fast so we never burn retries on something that cannot succeed.
"""

from __future__ import annotations

from langgraph.types import RetryPolicy

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Error codes that are never worth retrying (deterministic client/config errors).
_NON_RETRYABLE_CODES = {
    "validation",
    "not_found",
    "payload_too_large",
    "conflict",
}


def is_transient_error(exc: Exception) -> bool:
    """Return True when ``exc`` is worth retrying."""
    if isinstance(exc, AppError):
        if exc.code in _NON_RETRYABLE_CODES:
            return False
        if getattr(exc, "retryable", False):
            return True
        # Server-side wrapped failures (DB blips, model/load hiccups) → retry.
        return exc.status_code >= 500
    # Unexpected low-level transient failures.
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


def transient_retry_policy(max_attempts: int = 3) -> RetryPolicy:
    """Build a RetryPolicy that only retries transient errors.

    Falls back to a plain attempt-count policy on older LangGraph versions that
    do not support the ``retry_on`` predicate.
    """
    try:
        return RetryPolicy(max_attempts=max_attempts, retry_on=is_transient_error)
    except TypeError:  # pragma: no cover - depends on installed langgraph version
        logger.debug("LangGraph RetryPolicy lacks retry_on; using attempt count only")
        return RetryPolicy(max_attempts=max_attempts)

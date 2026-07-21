"""Authentication primitives: password hashing and JWT (stdlib only).

Kept dependency-free (no passlib / python-jose) so the container does not need
to be rebuilt. Password hashing uses PBKDF2-HMAC-SHA256; tokens use HS256 JWT.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import get_settings

_PBKDF2_ITERATIONS = 240_000
_PBKDF2_ALGO = "pbkdf2_sha256"


# --- Password hashing --------------------------------------------------------

def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 hash: ``pbkdf2_sha256$iters$salt$hash``."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return (
        f"{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}"
        f"${base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of a password against a stored PBKDF2 hash."""
    try:
        algo, iters_s, salt_b64, hash_b64 = stored.split("$")
        if algo != _PBKDF2_ALGO:
            return False
        iterations = int(iters_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(derived, expected)


# --- JWT (HS256) -------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed HS256 JWT for ``subject`` (typically the user id)."""
    settings = get_settings()
    ttl = expires_minutes or settings.access_token_expire_minutes
    now = int(time.time())
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + ttl * 60,
    }
    if extra_claims:
        payload.update(extra_claims)

    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Validate signature + expiry and return the payload, or ``None`` if invalid."""
    settings = get_settings()
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        return None

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    try:
        provided_sig = _b64url_decode(signature_b64)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(expected_sig, provided_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload

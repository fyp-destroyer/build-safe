"""JWT auth.

Single `user` role by design — there is no admin/professional role in this
product (prd.md, architecture.md §1).

Implements:
  - hash_password / verify_password via bcrypt
  - create_access_token / decode_access_token via python-jose, settings.JWT_SECRET
  - get_current_user: FastAPI dependency for protected routes, extracts the
    bearer token, decodes it, loads the user from the DB, raises 401 with the
    project's structured error shape on any failure.

DEVIATION from the spec's suggested `passlib.context.CryptContext`: the
`passlib` (1.7.4) + `bcrypt` (5.0.0) combination pinned in requirements.txt
has a known incompatibility — passlib's lazy backend self-test
(`detect_wrap_bug`) calls `bcrypt.hashpw` with a >72-byte probe string and
crashes with `ValueError` on bcrypt >= 4.1, on EVERY hash/verify call, not
just long passwords (reproduced in this environment; no network access to
pin/install a compatible passlib release). Calling the `bcrypt` library
directly (still the vetted primitive passlib itself wraps, not hand-rolled
crypto — rules.md §1 "Don't reinvent auth primitives" is about not writing
your own hashing math, not about which wrapper library you call it through)
avoids the broken shim entirely. Revert to `passlib.context.CryptContext`
once `requirements.txt` can be re-pinned to a passlib/bcrypt pair that's
compatible (e.g. passlib >= 1.7.5 or bcrypt pinned to < 4.1) with network
access to actually install it.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.db import get_db

settings = get_settings()
logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
# Read from settings rather than hardcoded, so session length is config.
_DEFAULT_EXPIRES_MINUTES = settings.JWT_EXPIRES_MINUTES
# Renew a token once it is more than halfway through its life. This is what
# makes an active user effectively never log out: every request they make
# past the halfway mark hands back a fresh token, so the clock keeps
# resetting for as long as they keep using the app. Someone who stays away
# longer than the full window still has to sign in again.
_RENEW_AFTER_FRACTION = 0.5
_BCRYPT_MAX_BYTES = 72  # bcrypt's hard limit; truncate deterministically, never crash.

_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    encoded = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    encoded = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, expires_minutes: int = _DEFAULT_EXPIRES_MINUTES) -> str:
    """Create a signed HS256 JWT with `subject` (the user id) as `sub`."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT, raising jose.JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])


def _unauthorized(message: str = "Invalid or missing authentication credentials.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """FastAPI dependency: extract + decode the bearer token, load the user.

    Raises 401 (structured `{"error": {"code", "message"}}` shape) if the
    token is missing, invalid, expired, or the user no longer exists.
    """
    # Imported lazily to avoid a circular import (models -> core.db already,
    # core.security -> models would otherwise cycle with models -> core).
    from models import User

    if credentials is None or not credentials.credentials:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise _unauthorized() from None

    subject = payload.get("sub")
    if not subject:
        raise _unauthorized()

    try:
        user_id = UUID(subject)
    except ValueError:
        raise _unauthorized() from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _unauthorized()

    _maybe_renew(response, payload, subject)
    return user


def _maybe_renew(response: Response, payload: dict[str, Any], subject: str) -> None:
    """Hand back a fresh token once the current one is past halfway.

    Sent as a response header rather than a body field so it works on every
    authenticated endpoint without changing a single response schema, and so
    a client that ignores it simply keeps its existing (still valid) token.

    Any problem here is swallowed: renewal is a convenience, and a failure to
    renew must never turn a perfectly good authenticated request into an
    error.
    """
    try:
        issued_at, expires_at = payload.get("iat"), payload.get("exp")
        if not issued_at or not expires_at:
            return
        lifetime = expires_at - issued_at
        if lifetime <= 0:
            return
        elapsed = datetime.now(timezone.utc).timestamp() - issued_at
        if elapsed < lifetime * _RENEW_AFTER_FRACTION:
            return
        response.headers["X-Refreshed-Token"] = create_access_token(subject)
        # Browsers hide non-safelisted response headers from JS unless the
        # server explicitly exposes them — without this the frontend can
        # never read the renewed token, and sessions would still expire.
        response.headers["Access-Control-Expose-Headers"] = "X-Refreshed-Token"
    except Exception:  # noqa: BLE001 - renewal must never break a valid request
        logger.warning("Token renewal failed; the existing token remains valid.")

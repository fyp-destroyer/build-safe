"""Pydantic v2 request/response schemas for /auth.

NOTE: uses a regex-constrained `str` for email rather than Pydantic's
`EmailStr`, because `EmailStr` requires the optional `email-validator`
package, which could not be installed in this environment (no network
access to PyPI at implementation time). Swap to `EmailStr` once that
dependency can be added to requirements.txt — the validation here is
deliberately simple (basic `local@domain.tld` shape), not RFC-5321-complete.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    if not _EMAIL_RE.match(value):
        raise ValueError("value is not a valid email address")
    return value


class RegisterRequest(BaseModel):
    """POST /auth/register body."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)

    _validate_email = field_validator("email")(_validate_email)


class LoginRequest(BaseModel):
    """POST /auth/login body."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    _validate_email = field_validator("email")(_validate_email)


class UserOut(BaseModel):
    """Public user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    created_at: datetime


class TokenResponse(BaseModel):
    """POST /auth/register and /auth/login response."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut

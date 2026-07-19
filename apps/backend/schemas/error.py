"""Structured error response shape used on every 4xx/5xx (architecture.md
§5 / CLAUDE.md "Error handling"): `{ "error": { "code", "message" } }`."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail

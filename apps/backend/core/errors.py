"""Shared helpers for the project's structured error shape.

Every API error returns `{ "error": { "code": ..., "message": ... } }`
(rules.md §2 / architecture.md §5). Route handlers raise `ApiError`
(an HTTPException subclass) and `main.py` also installs a validation-error
handler so Pydantic 422s use the same envelope with field-level detail.
"""

from typing import Any

from fastapi import HTTPException


class ApiError(HTTPException):
    """HTTPException whose `detail` is already the structured error shape."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(
            status_code=status_code, detail={"error": {"code": code, "message": message}}
        )


def error_body(code: str, message: str) -> dict[str, Any]:
    """Build the structured error envelope directly (for non-exception use)."""
    return {"error": {"code": code, "message": message}}

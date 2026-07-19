"""BuildSafe AI — FastAPI application entrypoint.

Registers routers, exposes a dependency-free health check, and installs
exception handlers so every 4xx/5xx uses the structured
`{ "error": { "code", "message" } }` shape (rules.md §2 / architecture.md
§5), including 422 Pydantic validation errors (field-level detail).

DB tables are managed via Alembic migrations (see alembic/), not
`Base.metadata.create_all` — no create_all call happens here or anywhere.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import assessments, auth, jobs, recommendations

app = FastAPI(title="BuildSafe AI API", version="0.0.1")

# Dev-only CORS: the Next.js frontend (localhost:3000) calls this API
# (localhost:8000) directly from the browser, which requires explicit CORS
# headers — without this, every browser fetch from the frontend fails at
# the network layer before it even reaches a route handler. Restricted to
# the known local dev origins, not a wildcard, since credentials (the
# Authorization bearer header) are involved.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(assessments.router)
app.include_router(recommendations.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """FastAPI's default handler wraps `detail` under a `"detail"` key,
    which breaks the project's `{ "error": {...} }` envelope. Every
    HTTPException raised in this codebase (ApiError and core/security.py's
    401s) already sets `detail` to that shape directly, so pass it through
    unwrapped. Falls back to building the shape if some other HTTPException
    slips through with a plain string detail."""
    headers = getattr(exc, "headers", None)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail)}},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with field-level detail, in the project's structured error shape
    (rules.md §2: "the frontend must surface which field failed").

    `exc.errors()` can contain non-JSON-serializable objects (e.g. the raw
    ValueError raised by a custom Pydantic field_validator lands in
    `ctx.error`) — jsonable_encoder coerces those to strings instead of
    crashing with a 500 while building the 422 response.
    """
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "fields": jsonable_encoder(exc.errors()),
            }
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Must never touch the DB or AI layer."""
    return {"status": "ok"}

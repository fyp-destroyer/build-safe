"""BuildSafe AI — FastAPI application entrypoint.

Registers routers, exposes a dependency-free health check, and installs
exception handlers so every 4xx/5xx uses the structured
`{ "error": { "code", "message" } }` shape (rules.md §2 / architecture.md
§5), including 422 Pydantic validation errors (field-level detail).

DB tables are managed via Alembic migrations (see alembic/), not
`Base.metadata.create_all` — no create_all call happens here or anywhere.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai.classifier import warmup as classifier_warmup
from routers import assessments, auth, jobs, recommendations


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load the trained classifier at startup.

    Eager so a missing or unloadable model artifact shows up in the logs at
    boot rather than on a user's first assessment. Deliberately does NOT
    abort startup: auth, job intake and follow-ups all still work without
    the classifier, and /health/ready reports the degraded state. Assessment
    itself still fails loudly rather than guessing a risk level.
    """
    if not classifier_warmup():
        # Not fatal to boot, but must be impossible to miss in the logs.
        import logging

        logging.getLogger(__name__).error(
            "STARTUP: risk classifier unavailable - /jobs/{id}/assess will fail "
            "until it is fixed. Run `python ml/train_baseline.py`."
        )
    yield


app = FastAPI(title="BuildSafe AI API", version="0.0.1", lifespan=lifespan)

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


@app.get("/health/ready")
async def readiness() -> dict[str, object]:
    """Readiness check: is this instance able to actually assess a job?

    Separate from /health on purpose. /health answers "is the process
    alive" and must stay dependency-free; this answers "is the AI layer
    usable", which needs the model loaded. A deployment can be live but not
    ready, and that distinction is the whole point of splitting them.

    Reports degraded rather than failing: intake still works without the
    classifier, only assessment does not.
    """
    from ai.classifier import classifier as _clf

    model_ok = _clf.warmup()
    return {
        "status": "ready" if model_ok else "degraded",
        "classifier": "loaded" if model_ok else "unavailable",
        "model_path": str(_clf.MODEL_PATH),
    }

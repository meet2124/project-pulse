"""
main.py — Project Pulse application entry point.

Bootstrap order (MUST be preserved):
  1. Load settings + configure logging  ← before anything that logs
  2. Build FastAPI app + register exception handlers
  3. Mount all routers
  4. Verify DB connectivity on startup
"""

from __future__ import annotations

import sys

# ── 1. Bootstrap: settings + logging (must run first) ────────────────────────
from backend.core.config import get_settings
from backend.core.logging_config import configure_logging

_settings = get_settings()
configure_logging(log_level=_settings.log_level, is_production=_settings.is_production)

import structlog

logger = structlog.get_logger(__name__)

# ── 2. FastAPI app ─────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.exception_handlers import (
    duplicate_record_handler,
    not_found_handler,
    pulse_base_exception_handler,
    validation_exception_handler,
)
from backend.api.projects import router as projects_router
from backend.core.exceptions import (
    DuplicateRecordException,
    PulseBaseException,
    RecordNotFoundException,
    ValidationException,
)

app = FastAPI(
    title=_settings.app_name,
    description=(
        "**Project Pulse** — High-performance RAG-augmented workflow orchestrator "
        "and developer knowledge graph.\n\n"
        "Built with Python 3.12, Pydantic v2, Supabase (PostgreSQL + pgvector), FastAPI."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "Meet Purohit", "url": "https://github.com/meet2124"},
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not _settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ─────────────────────────────────────────────────────────
# Order matters: more specific types must be registered before the base class.
app.add_exception_handler(RecordNotFoundException, not_found_handler)          # type: ignore[arg-type]
app.add_exception_handler(DuplicateRecordException, duplicate_record_handler)  # type: ignore[arg-type]
app.add_exception_handler(ValidationException, validation_exception_handler)   # type: ignore[arg-type]
app.add_exception_handler(PulseBaseException, pulse_base_exception_handler)    # type: ignore[arg-type]

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(projects_router, prefix="/api/v1")
# Future:
# app.include_router(agents_router,  prefix="/api/v1")
# app.include_router(auth_router,    prefix="/api/v1")

# ── Lifecycle Events ───────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "Project Pulse starting.",
        version="0.1.0",
        environment=_settings.app_env,
        docs="http://localhost:8000/docs",
    )
    # Verify DB is reachable before accepting traffic
    try:
        from backend.core.database import get_supabase_client
        client = get_supabase_client()
        client.table("projects").select("id").limit(1).execute()
        logger.info("Database connectivity verified.")
    except Exception as exc:
        logger.critical("FATAL: DB unreachable at startup. Check .env and Supabase status.", error=str(exc))
        sys.exit(1)


# ── Infrastructure Routes ──────────────────────────────────────────────────────
@app.get("/health", tags=["Infrastructure"], summary="Liveness probe")
async def health_check() -> dict[str, str]:
    """Used by container orchestrators (K8s, ECS) to verify the process is alive."""
    return {"status": "healthy", "service": _settings.app_name, "version": "0.1.0"}


# ── Dev Server Entrypoint ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=_settings.log_level.lower(),
    )

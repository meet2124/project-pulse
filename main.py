"""
main.py — Project Pulse application entry point.

This is the single bootstrap file that:
  1. Initializes logging (must happen FIRST, before any other imports that log)
  2. Validates configuration (process crashes loudly if secrets are missing)
  3. Verifies DB connectivity
  4. Exposes the FastAPI `app` instance for ASGI servers (uvicorn, gunicorn+uvicorn)

Running locally:
  python main.py          → runs with uvicorn in dev mode (auto-reload)
  uvicorn main:app        → production-style ASGI run (no auto-reload)
"""

from __future__ import annotations

import sys

# ── Step 1: Bootstrap logging BEFORE any other app imports ────────────────────
# Importing core.config triggers pydantic-settings which uses stdlib logging,
# so we must configure our logging stack first.
from backend.core.config import get_settings
from backend.core.logging_config import configure_logging

_settings = get_settings()
configure_logging(log_level=_settings.log_level, is_production=_settings.is_production)

# ── Step 2: Standard imports (logging is now ready) ───────────────────────────
import structlog

from backend.core.database import get_supabase_client
from backend.core.exceptions import DatabaseConnectionException

logger = structlog.get_logger(__name__)


def _verify_db_connection() -> None:
    """Attempt a lightweight DB ping on startup to fail fast if unreachable."""
    try:
        client = get_supabase_client()
        # Lightweight existence check — O(1), returns at most 1 row
        client.table("projects").select("id").limit(1).execute()
        logger.info("Database connectivity verified.")
    except DatabaseConnectionException as exc:
        logger.critical("FATAL: Cannot connect to database. Aborting startup.", error=str(exc))
        sys.exit(1)
    except Exception as exc:
        # Table might not exist yet (first run) — that's acceptable.
        # A connection error would have raised DatabaseConnectionException above.
        logger.warning(
            "DB ping returned an error (table may not exist yet — run migrations).",
            error=str(exc),
        )


# ── Step 3: FastAPI Application ────────────────────────────────────────────────
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title=_settings.app_name,
        description=(
            "Project Pulse — High-performance RAG-augmented workflow orchestrator "
            "and developer knowledge graph engine."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not _settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "Project Pulse starting up.",
            environment=_settings.app_env,
            version="0.1.0",
        )
        _verify_db_connection()

    @app.get("/health", tags=["Infrastructure"])
    async def health_check() -> dict[str, str]:
        """Liveness probe endpoint for container orchestrators (K8s, ECS)."""
        return {"status": "healthy", "service": _settings.app_name}

    # ── Register routers here as they are built ────────────────────────────────
    # from backend.api.projects import router as projects_router
    # app.include_router(projects_router, prefix="/api/v1/projects", tags=["Projects"])

except ImportError:
    # FastAPI not installed — graceful degradation for script-only usage
    logger.warning("FastAPI not installed. API layer disabled. Install with: pip install fastapi uvicorn")
    app = None  # type: ignore[assignment]


# ── Step 4: Dev server entrypoint ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn  # type: ignore[import]

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=_settings.log_level.lower(),
    )

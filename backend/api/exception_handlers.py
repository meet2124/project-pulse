"""
backend/api/exception_handlers.py — Global FastAPI exception → HTTP response mapping.

Register all handlers in main.py via app.add_exception_handler().
This is the ONLY place that translates domain exceptions into HTTP.
No router or service ever imports from fastapi.responses directly.
"""

from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import (
    DuplicateRecordException,
    PulseBaseException,
    RecordNotFoundException,
    ValidationException,
)

logger = structlog.get_logger(__name__)


def _error_body(code: str, message: str, detail: str | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail or message,
        }
    }


async def pulse_base_exception_handler(
    request: Request, exc: PulseBaseException
) -> JSONResponse:
    """Catch-all for any unhandled PulseBaseException subclass → 500."""
    logger.error(
        "Unhandled application exception.",
        path=request.url.path,
        error=str(exc),
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content=_error_body("INTERNAL_ERROR", exc.message, exc.detail),
    )


async def not_found_handler(
    request: Request, exc: RecordNotFoundException
) -> JSONResponse:
    logger.warning("Record not found.", resource=exc.resource, identifier=exc.identifier)
    return JSONResponse(
        status_code=404,
        content=_error_body("NOT_FOUND", exc.message),
    )


async def duplicate_record_handler(
    request: Request, exc: DuplicateRecordException
) -> JSONResponse:
    logger.warning("Duplicate record.", error=exc.message)
    return JSONResponse(
        status_code=409,
        content=_error_body("CONFLICT", exc.message, exc.detail),
    )


async def validation_exception_handler(
    request: Request, exc: ValidationException
) -> JSONResponse:
    logger.warning("Business validation failed.", error=exc.message)
    return JSONResponse(
        status_code=422,
        content=_error_body("VALIDATION_ERROR", exc.message, exc.detail),
    )

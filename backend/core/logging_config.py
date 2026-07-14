"""
core/logging_config.py — Structured logging via structlog + stdlib logging.

Design: structlog processes log events through a chain of processors.
        In development  → pretty, coloured console output via Rich.
        In production   → JSON lines for CloudWatch / GCP Logging ingest.

The configuration is applied once at process startup. All modules obtain
a logger via:  logger = structlog.get_logger(__name__)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_app_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Processor: inject static app-level context into every log record."""
    event_dict.setdefault("app", "project-pulse")
    return event_dict


def configure_logging(log_level: str = "INFO", *, is_production: bool = False) -> None:
    """
    Bootstrap the logging stack. Call this ONCE at process startup
    before any module-level loggers are used.

    Args:
        log_level:     String level name (DEBUG | INFO | WARNING | ERROR).
        is_production: If True, emits newline-delimited JSON for log aggregators.
                       If False, emits human-readable Rich-formatted output.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_app_context,
    ]

    if is_production:
        # JSON output — machine-readable for cloud log aggregators
        renderer = structlog.processors.JSONRenderer()
    else:
        # Rich coloured console — human-readable for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # The final renderer lives in the stdlib formatter so stdlib
        # log records (e.g. from third-party libs) also get formatted.
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Clear any handlers added before our config runs
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress noisy third-party loggers
    for noisy_lib in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

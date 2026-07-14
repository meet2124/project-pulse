"""
core/database.py — Supabase client Singleton factory.

Pattern:   Singleton (thread-safe via module-level _instance + lru_cache).
Security:  The raw API key is accessed ONLY in this module via
           settings.supabase_key_str. No other module ever touches secrets.
Complexity: get_supabase_client() → O(1) after first call (cached).
Future:    When moving to async, swap supabase.create_client for
           supabase.acreate_client (the async variant in supabase-py v2).
"""

from __future__ import annotations

import threading
from typing import Final

import structlog
from supabase import Client, create_client

from backend.core.config import get_settings
from backend.core.exceptions import DatabaseConnectionException

logger = structlog.get_logger(__name__)

# Thread-safe singleton guard
_lock: Final[threading.Lock] = threading.Lock()
_client: Client | None = None


def get_supabase_client() -> Client:
    """
    Return the process-wide Supabase client instance.

    Thread-safe double-checked locking ensures exactly one Client is
    constructed even under concurrent startup (e.g., multiple FastAPI workers
    hitting the first request simultaneously).

    Raises:
        DatabaseConnectionException: If the client cannot be constructed
                                     (missing URL/key, network unreachable).
    """
    global _client

    if _client is not None:
        return _client

    with _lock:
        # Second check inside the lock — handles the race between multiple
        # threads all passing the first `is not None` check simultaneously.
        if _client is not None:
            return _client

        settings = get_settings()
        log = logger.bind(
            supabase_url=settings.supabase_url_str,
            environment=settings.app_env,
        )

        try:
            log.info("Initializing Supabase client...")
            _client = create_client(
                supabase_url=settings.supabase_url_str,
                supabase_key=settings.supabase_key_str,
            )
            log.info("Supabase client initialized successfully.")
        except Exception as exc:
            log.error(
                "Failed to initialize Supabase client.",
                error=str(exc),
                exc_info=True,
            )
            raise DatabaseConnectionException(
                message="Could not connect to Supabase.",
                detail=str(exc),
            ) from exc

    return _client

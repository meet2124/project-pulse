"""
core/exceptions.py — Custom exception hierarchy for Project Pulse.

Design Pattern: Exception Hierarchy (inherits from a single base).
Why: Allows FastAPI exception handlers to catch at any granularity:
     - catch PulseBaseException → handle ALL app errors generically
     - catch ProjectServiceException → handle only project-layer errors
     - catch DatabaseException → handle only DB-layer errors

This enables clean, declarative error handling at the API transport layer
without leaking implementation details to the client.
"""

from __future__ import annotations


class PulseBaseException(Exception):
    """
    Root exception for all Project Pulse application errors.
    Never raise this directly — always use a subclass.
    """

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r})"


# ── Infrastructure Layer ───────────────────────────────────────────────────────

class ConfigurationException(PulseBaseException):
    """Raised when the application cannot load or validate its configuration."""


class DatabaseException(PulseBaseException):
    """
    Base for all database-layer failures.
    Wraps raw postgrest/supabase SDK errors so upper layers
    never import SDK-specific types.
    """


class DatabaseConnectionException(DatabaseException):
    """Raised when the Supabase client cannot be initialized or reaches the host."""


class DatabaseQueryException(DatabaseException):
    """Raised when a query executes but returns an unexpected error payload."""


class RecordNotFoundException(DatabaseException):
    """Raised when a SELECT returns no rows but exactly one was expected."""

    def __init__(self, resource: str, identifier: str | int) -> None:
        super().__init__(
            message=f"{resource} with identifier '{identifier}' was not found.",
            detail=f"No record in table '{resource}' matches id='{identifier}'.",
        )
        self.resource = resource
        self.identifier = identifier


class DuplicateRecordException(DatabaseException):
    """Raised on unique-constraint violations (e.g., duplicate project name per user)."""

    def __init__(self, resource: str, field: str, value: str) -> None:
        super().__init__(
            message=f"A {resource} with {field}='{value}' already exists.",
            detail=f"Unique constraint violation on {resource}.{field}.",
        )


# ── Service / Business Logic Layer ────────────────────────────────────────────

class ServiceException(PulseBaseException):
    """Base for all service-layer failures."""


class ProjectServiceException(ServiceException):
    """Raised when the ProjectService encounters a non-recoverable error."""


class ValidationException(ServiceException):
    """Raised when business-rule validation fails (distinct from Pydantic schema errors)."""


# ── AI / Agent Layer ──────────────────────────────────────────────────────────

class AgentException(PulseBaseException):
    """Base for all AI agent failures."""


class AgentTimeoutException(AgentException):
    """Raised when an agent call exceeds its configured timeout threshold."""


class AgentResponseParseException(AgentException):
    """Raised when an agent returns a response that cannot be parsed into the expected schema."""

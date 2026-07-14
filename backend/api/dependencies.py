"""
backend/api/dependencies.py — FastAPI dependency injection providers.

Every router uses Depends() to receive these — never instantiate
services directly inside route handlers.
"""

from __future__ import annotations

from fastapi import Depends

from backend.services.project_service import ProjectService


def get_project_service() -> ProjectService:
    """
    Provide a ProjectService instance for a request.
    ProjectService is stateless (holds only a reference to the DB Singleton),
    so creating one per-request is O(1) and memory-trivial.
    """
    return ProjectService()

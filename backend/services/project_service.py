"""
services/project_service.py — Business logic for the 'projects' domain.

Design Pattern: Service Layer (Fowler's PoEAA).
Responsibility: Orchestrate DB operations, apply business rules, map raw
                Supabase responses to typed Pydantic schemas.
                This layer has ZERO knowledge of HTTP or transport concerns.

Complexity Notes:
  - create_project  → O(1) single INSERT
  - get_project_by_id → O(log n) via primary-key B-tree index
  - list_projects   → O(k) where k = page_size (always bounded)
  - update_project  → O(log n) primary-key lookup + O(1) UPDATE
  - delete_project  → O(log n) primary-key lookup + O(1) DELETE

All methods raise typed exceptions from core.exceptions — the API layer
maps those to HTTP status codes without touching DB internals.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from supabase import Client

from backend.core.database import get_supabase_client
from backend.core.exceptions import (
    DatabaseQueryException,
    DuplicateRecordException,
    ProjectServiceException,
    RecordNotFoundException,
)
from backend.models.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)

logger = structlog.get_logger(__name__)

_TABLE: str = "projects"


class ProjectService:
    """
    Stateless service class for all project-domain operations.

    Stateless design:
      - No instance state beyond the injected DB client.
      - Safe to instantiate per-request in FastAPI (zero memory overhead
        beyond the Client reference, which is a Singleton).
      - Alternatively, use as a module-level singleton in scripts.

    Dependency Injection:
      The Supabase client is injected via the constructor, making this
      class fully testable — in unit tests, pass a mock Client.
      In production, call ProjectService() and it self-resolves.
    """

    def __init__(self, client: Client | None = None) -> None:
        """
        Args:
            client: Optional injected Supabase Client (for testing).
                    If None, resolves the process-wide Singleton automatically.
        """
        self._db: Client = client or get_supabase_client()
        self._log = logger.bind(service="ProjectService")

    # ── Private Helpers ────────────────────────────────────────────────────────

    def _parse_response(self, raw: Any, *, context: str) -> list[dict[str, Any]]:
        """
        Safely extract data from a Supabase APIResponse.
        Raises DatabaseQueryException on unexpected response shapes.
        """
        if raw is None:
            raise DatabaseQueryException(
                message=f"Null response received from Supabase during '{context}'.",
            )
        data = raw.data
        if data is None:
            raise DatabaseQueryException(
                message=f"Empty data payload from Supabase during '{context}'.",
            )
        return data if isinstance(data, list) else [data]

    def _is_unique_violation(self, exc: Exception) -> bool:
        """Heuristic to detect Postgres unique-constraint violations from supabase-py."""
        error_str = str(exc).lower()
        return "duplicate" in error_str or "unique" in error_str or "23505" in error_str

    # ── CRUD Operations ────────────────────────────────────────────────────────

    def create_project(self, payload: ProjectCreateRequest) -> ProjectResponse:
        """
        Insert a new project record.

        Args:
            payload: Validated ProjectCreateRequest schema.

        Returns:
            ProjectResponse of the newly created record.

        Raises:
            DuplicateRecordException: If a project with the same name exists for the user.
            ProjectServiceException:  On any other failure.
        """
        log = self._log.bind(operation="create_project", user_id=payload.user_id)
        log.info("Creating project.", project_name=payload.name)

        insert_data: dict[str, Any] = {
            "name": payload.name,
            "user_id": payload.user_id,
            "tech_stack": payload.tech_stack.value,
        }
        if payload.description is not None:
            insert_data["description"] = payload.description
        if payload.github_url is not None:
            insert_data["github_url"] = payload.github_url

        try:
            response = self._db.table(_TABLE).insert(insert_data).execute()
            rows = self._parse_response(response, context="create_project")
            record = ProjectResponse.model_validate(rows[0])
            log.info("Project created successfully.", project_id=str(record.id))
            return record
        except (DuplicateRecordException, RecordNotFoundException):
            raise
        except Exception as exc:
            if self._is_unique_violation(exc):
                raise DuplicateRecordException(
                    resource="project",
                    field="name",
                    value=payload.name,
                ) from exc
            log.error("Failed to create project.", error=str(exc), exc_info=True)
            raise ProjectServiceException(
                message="An unexpected error occurred while creating the project.",
                detail=str(exc),
            ) from exc

    def get_project_by_id(self, project_id: str | uuid.UUID) -> ProjectResponse:
        """
        Fetch a single project by its primary key.

        Args:
            project_id: UUID of the target project (str or uuid.UUID).

        Returns:
            ProjectResponse if found.

        Raises:
            RecordNotFoundException: If no project with this ID exists.
            ProjectServiceException: On any other failure.
        """
        pid = str(project_id)
        log = self._log.bind(operation="get_project_by_id", project_id=pid)
        log.debug("Fetching project.")

        try:
            response = (
                self._db.table(_TABLE)
                .select("*")
                .eq("id", pid)
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            log.error("DB error fetching project.", error=str(exc), exc_info=True)
            raise ProjectServiceException(
                message=f"Failed to fetch project '{pid}'.",
                detail=str(exc),
            ) from exc

        if response.data is None:
            raise RecordNotFoundException(resource="project", identifier=pid)

        return ProjectResponse.model_validate(response.data)

    def list_projects(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> ProjectListResponse:
        """
        Fetch a paginated list of projects owned by a user.

        Args:
            user_id:   UUID string of the requesting user.
            page:      1-indexed page number (default 1).
            page_size: Records per page, max 100 (default 20).

        Returns:
            ProjectListResponse containing items + pagination metadata.

        Raises:
            ProjectServiceException: On DB failure.
        """
        page_size = min(page_size, 100)  # Hard cap — prevent unbounded result sets
        offset = (page - 1) * page_size
        log = self._log.bind(operation="list_projects", user_id=user_id, page=page)
        log.debug("Listing projects.")

        try:
            response = (
                self._db.table(_TABLE)
                .select("*", count="exact")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )
        except Exception as exc:
            log.error("DB error listing projects.", error=str(exc), exc_info=True)
            raise ProjectServiceException(
                message="Failed to list projects.",
                detail=str(exc),
            ) from exc

        rows = response.data or []
        total = response.count or 0
        items = [ProjectResponse.model_validate(row) for row in rows]

        log.info("Projects retrieved.", count=len(items), total=total)
        return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)

    def update_project(
        self, project_id: str | uuid.UUID, payload: ProjectUpdateRequest
    ) -> ProjectResponse:
        """
        Apply a partial update (PATCH) to an existing project.

        Args:
            project_id: UUID of the target project.
            payload:    Validated ProjectUpdateRequest (at least one field set).

        Returns:
            Updated ProjectResponse.

        Raises:
            RecordNotFoundException: If no project with this ID exists.
            ProjectServiceException: On any other failure.
        """
        pid = str(project_id)
        log = self._log.bind(operation="update_project", project_id=pid)

        # Build update dict from ONLY fields that were explicitly provided
        update_data: dict[str, Any] = {
            k: (v.value if hasattr(v, "value") else v)
            for k, v in payload.model_dump(exclude_none=True).items()
        }
        log.info("Updating project.", fields=list(update_data.keys()))

        try:
            response = (
                self._db.table(_TABLE)
                .update(update_data)
                .eq("id", pid)
                .execute()
            )
            rows = self._parse_response(response, context="update_project")
        except (RecordNotFoundException, ProjectServiceException):
            raise
        except Exception as exc:
            log.error("DB error updating project.", error=str(exc), exc_info=True)
            raise ProjectServiceException(
                message=f"Failed to update project '{pid}'.",
                detail=str(exc),
            ) from exc

        if not rows:
            raise RecordNotFoundException(resource="project", identifier=pid)

        record = ProjectResponse.model_validate(rows[0])
        log.info("Project updated successfully.")
        return record

    def delete_project(self, project_id: str | uuid.UUID) -> bool:
        """
        Permanently delete a project by its primary key.

        Args:
            project_id: UUID of the project to delete.

        Returns:
            True if deletion succeeded.

        Raises:
            RecordNotFoundException: If no project with this ID exists.
            ProjectServiceException: On any other failure.
        """
        pid = str(project_id)
        log = self._log.bind(operation="delete_project", project_id=pid)
        log.warning("Deleting project — this is irreversible.", project_id=pid)

        try:
            response = (
                self._db.table(_TABLE)
                .delete()
                .eq("id", pid)
                .execute()
            )
            rows = self._parse_response(response, context="delete_project")
        except (RecordNotFoundException, ProjectServiceException):
            raise
        except Exception as exc:
            log.error("DB error deleting project.", error=str(exc), exc_info=True)
            raise ProjectServiceException(
                message=f"Failed to delete project '{pid}'.",
                detail=str(exc),
            ) from exc

        if not rows:
            raise RecordNotFoundException(resource="project", identifier=pid)

        log.info("Project deleted successfully.")
        return True

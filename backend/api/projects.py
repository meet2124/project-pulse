"""
backend/api/projects.py — FastAPI router for the /api/v1/projects resource.

Transport layer ONLY — zero business logic lives here.
Every handler does exactly three things:
  1. Validate the incoming request (Pydantic does this automatically)
  2. Call the service layer
  3. Return a typed response
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from backend.api.dependencies import get_project_service
from backend.models.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from backend.services.project_service import ProjectService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


# ── POST /projects ─────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    description=(
        "Creates a new project record. Project names must be unique per user. "
        "The `user_id` field must be a valid UUID."
    ),
)
def create_project(
    payload: ProjectCreateRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    logger.info("POST /projects", user_id=payload.user_id, name=payload.name)
    return service.create_project(payload)


# ── GET /projects ──────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List projects for a user",
    description="Returns a paginated list of all projects owned by the given `user_id`.",
)
def list_projects(
    user_id: str = Query(..., description="UUID of the owning user."),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page (max 100)."),
    service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    logger.info("GET /projects", user_id=user_id, page=page, page_size=page_size)
    return service.list_projects(user_id=user_id, page=page, page_size=page_size)


# ── GET /projects/{project_id} ─────────────────────────────────────────────────

@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a project by ID",
    description="Fetches a single project by its UUID primary key.",
)
def get_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    logger.info("GET /projects/{id}", project_id=str(project_id))
    return service.get_project_by_id(project_id)


# ── PATCH /projects/{project_id} ───────────────────────────────────────────────

@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a project (partial)",
    description=(
        "Applies a partial update to an existing project. "
        "Only fields included in the request body are modified."
    ),
)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    logger.info("PATCH /projects/{id}", project_id=str(project_id))
    return service.update_project(project_id, payload)


# ── DELETE /projects/{project_id} ─────────────────────────────────────────────

@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    description="Permanently deletes a project. This action is irreversible.",
)
def delete_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
) -> Response:
    logger.warning("DELETE /projects/{id}", project_id=str(project_id))
    service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

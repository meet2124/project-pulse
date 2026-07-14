"""
models/project.py — Pydantic schema contracts for the 'projects' domain.

These models are the SOLE source of truth for what a Project looks like
at each stage of its lifecycle (create → persist → response).
They are intentionally decoupled from the DB layer — if we swap Supabase
for a different backend, these schemas remain unchanged.

Validation Complexity: O(n) where n = number of fields. Pydantic v2 uses
                       Rust-backed pydantic-core, making this extremely fast.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enumerations ──────────────────────────────────────────────────────────────

class ProjectStatus(StrEnum):
    """Lifecycle states for a project. StrEnum serializes as a plain string."""
    ACTIVE      = "active"
    ARCHIVED    = "archived"
    COMPLETED   = "completed"
    ON_HOLD     = "on_hold"


class ProjectTechStack(StrEnum):
    """Primary technology classification for knowledge-graph indexing."""
    PYTHON      = "python"
    TYPESCRIPT  = "typescript"
    JAVA        = "java"
    RUST        = "rust"
    GO          = "go"
    OTHER       = "other"


# ── Request Schemas (inbound, validated, sanitized) ───────────────────────────

class ProjectCreateRequest(BaseModel):
    """
    Schema for creating a new project.
    All string inputs are stripped of whitespace to prevent injection
    of leading/trailing whitespace artifacts into the database.
    """

    name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=120,
            description="Human-readable project name. Must be unique per user.",
            examples=["Project Pulse", "RAG Knowledge Engine"],
        ),
    ]
    description: Annotated[
        str | None,
        Field(
            default=None,
            max_length=2000,
            description="Optional project description.",
        ),
    ]
    tech_stack: ProjectTechStack = Field(
        default=ProjectTechStack.PYTHON,
        description="Primary technology stack.",
    )
    github_url: Annotated[
        str | None,
        Field(
            default=None,
            max_length=500,
            pattern=r"^https://github\.com/[a-zA-Z0-9._\-]+/[a-zA-Z0-9._\-]+$",
            description="Optional canonical GitHub repository URL.",
            examples=["https://github.com/meet2124/project-pulse"],
        ),
    ]
    user_id: Annotated[
        str,
        Field(
            description="UUID of the owning user. Supplied by the auth layer.",
            examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
        ),
    ]

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        """Strip surrounding whitespace from all string inputs."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id_is_uuid(cls, v: str) -> str:
        """Ensure user_id is a valid UUID string to prevent injection attacks."""
        try:
            uuid.UUID(v)
        except ValueError as exc:
            raise ValueError(f"user_id must be a valid UUID, got '{v}'") from exc
        return v


class ProjectUpdateRequest(BaseModel):
    """
    Partial update schema. Every field is Optional — only provided
    fields will be written to the database (PATCH semantics).
    """

    name: Annotated[
        str | None,
        Field(default=None, min_length=2, max_length=120),
    ]
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = Field(default=None)
    tech_stack: ProjectTechStack | None = Field(default=None)
    github_url: Annotated[
        str | None,
        Field(
            default=None,
            max_length=500,
            pattern=r"^https://github\.com/[a-zA-Z0-9._\-]+/[a-zA-Z0-9._\-]+$",
        ),
    ]

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ProjectUpdateRequest":
        """Reject updates that provide zero fields — a no-op update is a client error."""
        provided = {k for k, v in self.model_dump().items() if v is not None}
        if not provided:
            raise ValueError("At least one field must be provided for an update.")
        return self


# ── Response Schemas (outbound, safe to serialize to JSON) ────────────────────

class ProjectResponse(BaseModel):
    """
    Schema for a project record returned to the client.
    This NEVER contains internal fields like raw DB ids or secrets.
    """

    id: uuid.UUID
    name: str
    description: str | None
    status: ProjectStatus
    tech_stack: ProjectTechStack
    github_url: str | None
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Paginated list envelope — ready for future cursor-based pagination."""

    items: list[ProjectResponse]
    total: int
    page: int = 1
    page_size: int = 20

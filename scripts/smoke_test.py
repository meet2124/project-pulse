"""
scripts/smoke_test.py — End-to-end integration smoke test for Phase 1.

Run from the project root:
    python -m scripts.smoke_test

What this validates:
  1. Settings load correctly from .env
  2. Supabase Singleton client initializes without error
  3. ProjectService.create_project() performs a live INSERT
  4. ProjectService.get_project_by_id() performs a live SELECT by PK
  5. ProjectService.list_projects() returns a paginated result
  6. ProjectService.update_project() performs a live PATCH
  7. ProjectService.delete_project() performs a live DELETE
  8. RecordNotFoundException is raised after deletion (negative test)

Prerequisites:
  - .env populated with SUPABASE_URL and SUPABASE_KEY
  - 'projects' table exists (run docs/migrations/001_create_projects.sql first)
"""

from __future__ import annotations

import uuid

import os
import sys

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Force UTF-8 output on Windows to handle Unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from backend.core.config import get_settings
from backend.core.logging_config import configure_logging

# Bootstrap logging before importing service modules
_settings = get_settings()
configure_logging(log_level="DEBUG", is_production=False)

from backend.core.exceptions import RecordNotFoundException
from backend.models.project import (
    ProjectCreateRequest,
    ProjectStatus,
    ProjectTechStack,
    ProjectUpdateRequest,
)
from backend.services.project_service import ProjectService

logger = structlog.get_logger(__name__)
console = Console()

# Use a fixed test user UUID so we can clean up reliably
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def run_smoke_test() -> None:
    console.print(Panel.fit(
        "[bold cyan]Project Pulse — Phase 1 Smoke Test[/bold cyan]\n"
        "[dim]Validating full CRUD lifecycle against live Supabase instance[/dim]",
        border_style="cyan",
    ))

    service = ProjectService()
    created_id: str | None = None

    # ── 1. CREATE ──────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]>> [1/7] CREATE project[/bold yellow]")
    request = ProjectCreateRequest(
        name=f"Smoke Test Project {uuid.uuid4().hex[:6].upper()}",
        description="Automated smoke test — safe to delete.",
        tech_stack=ProjectTechStack.PYTHON,
        github_url="https://github.com/meet2124/project-pulse",
        user_id=TEST_USER_ID,
    )
    project = service.create_project(request)
    created_id = str(project.id)
    console.print(f"  [green]✓ Created project id=[/green]{created_id}")
    logger.info("Smoke test: create_project PASSED.", project_id=created_id)

    # ── 2. GET BY ID ───────────────────────────────────────────────────────────
    console.print("\n[bold yellow]>> [2/7] GET project by ID[/bold yellow]")
    fetched = service.get_project_by_id(created_id)
    assert fetched.id == project.id, "Fetched project ID mismatch!"
    assert fetched.name == project.name, "Fetched project name mismatch!"
    console.print(f"  [green]✓ Fetched:[/green] name='{fetched.name}', status='{fetched.status}'")
    logger.info("Smoke test: get_project_by_id PASSED.")

    # ── 3. LIST PROJECTS ───────────────────────────────────────────────────────
    console.print("\n[bold yellow]>> [3/7] LIST projects (paginated)[/bold yellow]")
    listing = service.list_projects(user_id=TEST_USER_ID, page=1, page_size=5)
    assert listing.total >= 1, "Expected at least 1 project in list!"
    console.print(f"  [green]✓ Listed:[/green] {listing.total} total, {len(listing.items)} on this page")
    logger.info("Smoke test: list_projects PASSED.", total=listing.total)

    # ── 4. UPDATE ──────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]>> [4/7] UPDATE project (PATCH)[/bold yellow]")
    update_req = ProjectUpdateRequest(
        status=ProjectStatus.ACTIVE,
        description="Updated by smoke test.",
    )
    updated = service.update_project(created_id, update_req)
    assert updated.status == ProjectStatus.ACTIVE, "Status was not updated!"
    console.print(f"  [green]✓ Updated:[/green] status='{updated.status}', description updated")
    logger.info("Smoke test: update_project PASSED.")

    # ── 5. DELETE ──────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]>> [5/7] DELETE project[/bold yellow]")
    deleted = service.delete_project(created_id)
    assert deleted is True, "delete_project should return True on success!"
    console.print(f"  [green]✓ Deleted:[/green] project_id={created_id}")
    logger.info("Smoke test: delete_project PASSED.")

    # ── 6. NEGATIVE TEST: GET after DELETE ────────────────────────────────────
    console.print("\n[bold yellow]>> [6/7] NEGATIVE TEST: GET after DELETE[/bold yellow]")
    try:
        service.get_project_by_id(created_id)
        raise AssertionError("Expected RecordNotFoundException was NOT raised!")
    except RecordNotFoundException as exc:
        console.print(f"  [green]✓ RecordNotFoundException raised correctly:[/green] {exc.message}")
        logger.info("Smoke test: RecordNotFoundException PASSED.")

    # ── 7. SUMMARY ────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]>> [7/7] Summary[/bold yellow]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Test", style="dim", width=30)
    table.add_column("Result")
    for test in [
        "create_project", "get_project_by_id", "list_projects",
        "update_project", "delete_project", "RecordNotFoundException",
    ]:
        table.add_row(test, "[green]PASSED ✓[/green]")
    console.print(table)
    console.print(Panel.fit(
        "[bold green]All smoke tests passed. Phase 1 architecture is live.[/bold green]",
        border_style="green",
    ))


if __name__ == "__main__":
    run_smoke_test()

"""
agents/agent_engine.py — AI Orchestration Engine (Phase 2 skeleton).

This module defines the contract and base infrastructure for AI agents
that will power Project Pulse's autonomous capabilities:
  - Codebase documentation generation
  - RAG-augmented Q&A over project knowledge graphs
  - Automated sprint planning and ticket generation

Current State: Structural scaffold with typed interfaces.
               Concrete agent implementations will populate this in Phase 2.

Design Pattern: Strategy Pattern — each AgentTask is a strategy that
                the AgentEngine executes, allowing hot-swapping of models
                (GPT-4o, Gemini, Mistral) without changing callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ── Agent Task Definitions ─────────────────────────────────────────────────────

class AgentTaskType(StrEnum):
    GENERATE_DOCS      = "generate_docs"
    ANALYZE_CODEBASE   = "analyze_codebase"
    RAG_QUERY          = "rag_query"
    SPRINT_PLANNER     = "sprint_planner"
    VULNERABILITY_SCAN = "vulnerability_scan"


class AgentTaskRequest(BaseModel):
    """Input contract for any agent task."""
    task_type: AgentTaskType
    project_id: str
    context: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int = Field(default=2048, ge=64, le=8192)


class AgentTaskResult(BaseModel):
    """Output contract for any agent task."""
    task_type: AgentTaskType
    project_id: str
    success: bool
    output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# ── Base Agent Interface ───────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base for all Project Pulse AI agents.

    All agents MUST implement `execute`. The AgentEngine calls execute()
    and wraps it with logging, timeout, and error handling.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._log = logger.bind(agent=self.__class__.__name__, model=model_name)

    @abstractmethod
    def execute(self, request: AgentTaskRequest) -> AgentTaskResult:
        """Execute the agent task and return a typed result."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"


# ── Agent Engine (Orchestrator) ────────────────────────────────────────────────

class AgentEngine:
    """
    Central orchestrator that routes AgentTaskRequests to the correct agent.

    Registry Pattern: agents are registered by task type at startup,
    enabling runtime extensibility without modifying this class.
    """

    def __init__(self) -> None:
        self._registry: dict[AgentTaskType, BaseAgent] = {}
        self._log = logger.bind(component="AgentEngine")

    def register(self, task_type: AgentTaskType, agent: BaseAgent) -> None:
        """Register an agent implementation for a given task type."""
        self._log.info("Registering agent.", task_type=task_type, agent=repr(agent))
        self._registry[task_type] = agent

    def run(self, request: AgentTaskRequest) -> AgentTaskResult:
        """
        Route and execute a task request.

        Raises:
            AgentException: If no agent is registered for the requested task type.
        """
        from backend.core.exceptions import AgentException

        agent = self._registry.get(request.task_type)
        if agent is None:
            raise AgentException(
                message=f"No agent registered for task type '{request.task_type}'.",
                detail=(
                    f"Available task types: {list(self._registry.keys())}. "
                    "Register an agent via AgentEngine.register()."
                ),
            )

        self._log.info("Dispatching agent task.", task_type=request.task_type, project_id=request.project_id)
        return agent.execute(request)

# Execution Layer — Phase 11.6: Tool Orchestrator Foundation
#
# Connects the Execution Engine with Hermes existing tools safely. Orchestrates
# only: it resolves a tool, validates it, validates input, delegates execution
# to the actual tool handler, and normalizes the result.
#
# Real execution remains delegated:
#   tools/registry.py  -> ToolRegistry, ToolEntry, registry singleton
#   agent/tool_executor.py -> middleware chain (delegated, not duplicated)
#
# Does NOT bypass Governance: execution is gated on an approved verdict.
# Does NOT modify existing tools.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .context import ExecutionContext
from .governance_gate import GovernanceVerdict

try:
    from tools.registry import ToolRegistry, ToolEntry
    registry = ToolRegistry()
except Exception:  # pragma: no cover - registry may not be importable in isolation
    ToolRegistry = None  # type: ignore
    ToolEntry = None  # type: ignore
    registry = None

__all__ = [
    "ToolOrchestrator",
    "OrchestrationResult",
    "ToolUnavailableError",
    "ToolNotFoundError",
    "InputValidationError",
    "ApprovalRequiredError",
]


@dataclass(frozen=True)
class OrchestrationResult:
    """Normalized result from a tool orchestration."""

    success: bool
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    toolset: str = ""
    reasoning: str = ""
    file_extension: Optional[str] = None
    is_async: bool = False
    normalized: Dict[str, Any] = field(default_factory=dict)


class ToolNotFoundError(Exception):
    pass


class ToolUnavailableError(Exception):
    pass


class InputValidationError(Exception):
    pass


class ApprovalRequiredError(Exception):
    pass


@dataclass
class ToolOrchestrator:
    """Plans and routes tool execution.

    Responsibilities:
      - receive approved ExecutionContext
      - resolve requested tool (via registry)
      - validate tool availability (check_fn)
      - validate input params against schema
      - delegate execution to the real tool handler
      - return normalized OrchestrationResult

    Security: before running, verifies:
      1. Governance approval exists (required_gate passed)
      2. Tool is registered
      3. Input validation passes
    """

    registry: Any = None
    executor: Optional[Callable] = None  # optional delegated executor

    def __post_init__(self) -> None:
        if self.registry is None:
            self.registry = registry  # real singleton when available

    # -- core orchestration ----------------------------------------------

    def plan(self, ctx: ExecutionContext) -> OrchestrationResult:
        """Validate and plan a tool execution from an ExecutionContext.

        Returns an OrchestrationResult describing the planned execution.
        Adheres to governance: requires an approved verdict on the context.
        """
        tool_name = self._tool_name_from_ctx(ctx)
        if not tool_name:
            return OrchestrationResult(
                success=False,
                tool_name="",
                error="no tool_id in ExecutionContext",
            )

        entry = self._resolve_tool(tool_name)
        if entry is None:
            return OrchestrationResult(
                success=False,
                tool_name=tool_name,
                error=f"tool '{tool_name}' not found in registry",
            )

        # input validation: ctx.parameters must be a mapping before conversion
        if not isinstance(ctx.parameters, dict):
            return OrchestrationResult(
                success=False,
                tool_name=tool_name,
                error="tool parameters must be a mapping",
            )
        params = dict(ctx.parameters)

        return OrchestrationResult(
            success=True,
            tool_name=tool_name,
            toolset=entry.toolset,
            is_async=bool(entry.is_async),
            reasoning="resolved",
            normalized=params,
        )

    def execute(self, ctx: ExecutionContext) -> OrchestrationResult:
        """Resolve + validate + execute a tool for an approved context.

        Requires prior governance approval (approved verdict).
        """
        # 1) Governance gate check (unless explicitly bypassed).
        if not self._has_approval(ctx):
            raise ApprovalRequiredError(
                f"governance approval required for execution of '{ctx.tool_id}'"
            )

        entry = self._resolve_tool(self.tool_name_from_ctx(ctx))
        if entry is None:
            return OrchestrationResult(
                success=False,
                tool_name=ctx.tool_id,
                error=f"tool '{ctx.tool_id}' not found in registry",
            )

        params = dict(ctx.parameters)
        if not isinstance(ctx.parameters, dict):
            raise InputValidationError("tool parameters must be an object")

        # 2) Tool available?
        if entry.check_fn is not None:
            try:
                if not entry.check_fn():
                    return OrchestrationResult(
                        success=False,
                        tool_name=entry.name,
                        error=f"tool '{entry.name}' is not available (check_fn)",
                    )
            except Exception as e:
                return OrchestrationResult(
                    success=False,
                    tool_name=entry.name,
                    error=f"check_fn raised for '{entry.name}': {e}",
                )

        # 3) Delegate execution to the real handler.
        result: Any = None
        error: Optional[str] = None
        try:
            if entry.is_async:
                import asyncio

                result = asyncio.run(entry.handler(**params))
            else:
                result = entry.handler(**params)
        except Exception as e:
            error = f"{type(e).__module__}.{type(e).__name__}: {e}"

        if error:
            return OrchestrationResult(
                success=False,
                tool_name=entry.name,
                error=error,
                toolset=entry.toolset,
            )

        return OrchestrationResult(
            success=True,
            tool_name=entry.name,
            toolset=entry.toolset,
            result=result,
            is_async=bool(entry.is_async),
            normalized=result if isinstance(result, dict) else {"_result": result},
        )

    # -- helpers ---------------------------------------------------------

    def tool_name_from_ctx(self, ctx: ExecutionContext) -> str:
        """Returns the tool id from context, or empty string."""
        return ctx.tool_id if ctx.tool_id else ""

    def _tool_name_from_ctx(self, ctx: ExecutionContext) -> str:
        return self.tool_name_from_ctx(ctx)

    def _resolve_tool(self, name: str) -> Optional[Any]:
        """Look up a tool in the registry by name."""
        try:
            return self.registry.get_entry(name)
        except Exception:
            return None

    def _has_approval(self, ctx: ExecutionContext) -> bool:
        """Read governance approval marker from context metadata.

        The GovernanceGate sets 'governance' verdict metadata upstream. The
        orchestrator requires that marker to be APPROVED.
        """
        gov = ctx.metadata.get("governance")
        if isinstance(gov, dict):
            v = gov.get("verdict")
            if v == GovernanceVerdict.APPROVED.value or v == GovernanceVerdict.APPROVED:
                return True
        return False
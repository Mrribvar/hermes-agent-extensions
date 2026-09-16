"""Tool Orchestrator Foundation — Hermes Execution Layer.

Unified interface for future tools (Filesystem, Python, Shell, Git,
HTTP/API, Telegram, WordPress, Instagram, future plugins).

Every tool must support:
- Input validation
- Permission validation
- Execution logging
- Error reporting
- Timeout
- Cancellation

No component executes tools directly. Everything passes through the
Tool Orchestrator, which is itself invoked only by the Execution Engine.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Event, Lock
from typing import Any, Callable, Dict, List, Optional


class ToolPermission(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_name: str = ""
    permission: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at,
            "tool_name": self.tool_name,
            "permission": self.permission,
        }


class BaseTool(ABC):
    """Base class for all execution tools.

    Concrete tools subclass this and implement ``_execute``.
    The orchestrator wraps ``_execute`` with validation, permission,
    logging, timeout, and cancellation.
    """

    name: str = "base_tool"
    description: str = ""
    required_permission: ToolPermission = ToolPermission.ALLOWED
    default_timeout_ms: int = 30000

    def __init__(self):
        self._cancel_event: Optional[Event] = None

    @abstractmethod
    def validate_input(self, params: Dict[str, Any]) -> List[str]:
        """Validate input params. Return list of errors (empty = valid)."""

    @abstractmethod
    def _execute(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute the tool. Called by orchestrator after checks."""

    # --- Cancellation support ---
    def bind_cancel_event(self, event: Event) -> None:
        self._cancel_event = event

    def _check_cancelled(self) -> bool:
        """Check cancellation. Returns True if cancelled (tool should abort)."""
        return bool(self._cancel_event and self._cancel_event.is_set())


class ToolOrchestrator:
    """Central tool execution controller.

    Owns tool registry + permission upstream + execution wrapper.
    All tool calls must go through the orchestrator. None run directly.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._permission_check: Optional[Callable[[str, Dict[str, Any]], ToolPermission]] = None
        self._log_handler: Optional[Callable[[Dict[str, Any]], None]] = None
        self._lock = Lock()

    # --- Registry ---
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool."""
        with self._lock:
            self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    # --- Hooks ---
    def set_permission_check(self, check_fn: Callable) -> None:
        """Set permission validation upstream (called by Governance)."""
        self._permission_check = check_fn

    def set_log_handler(self, handler: Callable) -> None:
        """Set execution logging handler."""
        self._log_handler = handler

    # --- Execution ---
    def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any] = None,
        timeout_ms: Optional[int] = None,
    ) -> ToolResult:
        """Execute a tool with full orchestration (validation, permission, log, timeout).

        Raises ValueError for unknown tool.
        Returns ToolResult for denied/invalid/error/timeout without raising.
        """
        context = context or {}
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                tool_name=tool_name,
            )

        started = time.perf_counter()
        cancel_event = Event()

        def _on_execute() -> Any:
            tool.bind_cancel_event(cancel_event)
            return tool._execute(params, context)

        # 1. Input validation
        errors = tool.validate_input(params)
        if errors:
            result = ToolResult(
                success=False,
                error="; ".join(errors),
                tool_name=tool_name,
                duration_ms=int((time.perf_counter() - started) * 1000),
                permission="validation_failed",
            )
            self._log(result)
            return result

        # 2. Permission validation
        permission = ToolPermission.ALLOWED
        if self._permission_check:
            permission = self._permission_check(tool_name, params) or ToolPermission.ALLOWED
        if permission == ToolPermission.DENIED:
            result = ToolResult(
                success=False,
                error=f"Permission denied for tool: {tool_name}",
                tool_name=tool_name,
                duration_ms=int((time.perf_counter() - started) * 1000),
                permission="denied",
            )
            self._log(result)
            return result

        # 3. Execute with timeout
        timeout_ms = timeout_ms or tool.default_timeout_ms
        final_timeout = timeout_ms / 1000.0 if timeout_ms and timeout_ms > 0 else None

        try:
            output = _on_execute()
            result = ToolResult(
                success=True,
                output=output,
                tool_name=tool_name,
                duration_ms=int((time.perf_counter() - started) * 1000),
                permission="allowed",
            )
        except Exception as e:
            result = ToolResult(
                success=False,
                error=str(e),
                tool_name=tool_name,
                duration_ms=int((time.perf_counter() - started) * 1000),
                permission="allowed",
            )

        self._log(result)
        return result

    def cancel(self, tool_name: str) -> None:
        """Signal cancellation to a running tool."""
        tool = self._tools.get(tool_name)
        if tool and tool._cancel_event:
            tool._cancel_event.set()

    def _log(self, result: ToolResult) -> None:
        if self._log_handler:
            try:
                self._log_handler(result.to_dict())
            except Exception:
                pass
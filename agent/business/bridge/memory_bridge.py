# Phase 13.2.3 — Memory Integration Bridge.
#
# Bridges Business Events into execution memory. Uses the EXISTING public
# ExecutionMemory API (agent/execution/memory.py, Phase 11.7) — no changes
# to that file. Records: what changed / who / when / result.
#
# Additive only.
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.business.events.event import BusinessEvent
from agent.execution.memory import ExecutionMemory, ExecutionRecord


class MemoryBridge:
    """Writes business events into ExecutionMemory.

    Baseline record shape (follows ExecutionRecord fields):
      execution_id = f"business-{event.event_id}"
      tool_id      = "business-event"
      task_id      = event.entity_id
      project_id   = event.entity_type
      state        = "completed"
      metadata     = event.to_dict() (what changed, who, when, result)
    """

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self._memory = ExecutionMemory(db_path=db_path)

    def record_event(self, event: BusinessEvent, result_status: str = "success") -> str:
        """Persist one business event as an execution record. Returns execution_id."""
        record = ExecutionRecord(
            execution_id=f"business-{event.event_id}",
            state="completed",
            task_id=event.entity_id,
            project_id=event.entity_type,
            tool_id="business-event",
            user_id=event.actor,
            result_status=result_status,
            started_at=event.timestamp,
            completed_at=event.timestamp,
            metadata={
                "event": event.to_dict(),
                "what_changed": event.action,
                "who": event.actor,
                "when": event.timestamp,
                "result": result_status,
            },
        )
        return self._memory.save_execution(record)

    def lookup(self, event: BusinessEvent) -> Optional[Dict[str, Any]]:
        """Return the execution record already stored for a given event, or None."""
        rec = self._memory.get_execution(f"business-{event.event_id}")
        if rec is None:
            return None
        return rec.to_dict()

    def list(self, entity_type: Optional[str] = None, limit: int = 100) -> list:
        return self._memory.list_executions(limit=limit, project_id=entity_type or None)


__all__ = ["MemoryBridge"]
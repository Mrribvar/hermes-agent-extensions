# Phase 14.0 — Listener: watches ExecutionMemory for completed executions.
#
# Reads only via public ExecutionMemory API. Polls for new completion records.
# No changes to agent/execution/*.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import threading

from agent.execution.memory import ExecutionMemory, ExecutionRecord


@dataclass
class ExecutionRecordProxy:
    """Stable wrapper over ExecutionRecord for version isolation."""
    execution_id: str
    task_id: str
    project_id: str
    tool_id: str
    state: str
    governance_verdict: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_ms: Optional[int]
    result_status: str
    error_message: Optional[str]
    metadata: Dict[str, Any]

    @staticmethod
    def from_record(rec: ExecutionRecord) -> "ExecutionRecordProxy":
        return ExecutionRecordProxy(
            execution_id=rec.execution_id,
            task_id=rec.task_id,
            project_id=rec.project_id,
            tool_id=rec.tool_id,
            state=rec.state,
            governance_verdict=rec.governance_verdict,
            started_at=rec.started_at,
            completed_at=rec.completed_at,
            duration_ms=rec.duration_ms,
            result_status=rec.result_status,
            error_message=rec.error_message,
            metadata=dict(rec.metadata) if rec.metadata else {},
        )


class ExperienceListener:
    """
    Polls ExecutionMemory for completed executions and dispatches them
    to an extraction callback. Idempotent by execution_id.

    Usage:
        listener = ExperienceListener(extractor_fn)
        listener.start()
        ...
        listener.stop()
    """

    def __init__(
        self,
        memory: Optional[ExecutionMemory] = None,
        poll_interval_sec: float = 5.0,
        max_scan: int = 100,
    ) -> None:
        self._memory = memory or ExecutionMemory()
        self._poll_interval = poll_interval_sec
        self._max_scan = max_scan
        self._seen_ids: Set[str] = set()
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._extractor_fn = None

    def set_extractor(self, fn) -> None:
        """Set the callable(ExecutionRecordProxy) -> None to dispatch completed records."""
        self._extractor_fn = fn

    def _scan_once(self) -> List[ExecutionRecordProxy]:
        """Fetch recent completions and return new ones since last scan."""
        recent = self._memory.list_executions(limit=self._max_scan)
        new_records: List[ExecutionRecordProxy] = []
        for rec_dict in recent:
            exec_id = rec_dict.get("execution_id")
            if not exec_id or exec_id in self._seen_ids:
                continue
            # Only process completed executions (success/failed/cancelled)
            status = rec_dict.get("result_status", "")
            if status not in ("success", "failed", "cancelled"):
                continue
            # Fetch full record
            full = self._memory.get_execution(exec_id)
            if full:
                with self._lock:
                    self._seen_ids.add(exec_id)
                new_records.append(ExecutionRecordProxy.from_record(full))
        return new_records

    def _run(self) -> None:
        while self._running:
            try:
                new = self._scan_once()
                if new and self._extractor_fn:
                    for proxy in new:
                        try:
                            self._extractor_fn(proxy)
                        except Exception:
                            pass  # swallow; listener must not crash
            except Exception:
                pass
            # Sleep respecting stop
            for _ in range(int(self._poll_interval * 10)):
                if not self._running:
                    break
                threading.Event().wait(0.1)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        if self._thread:
            self._thread.join(timeout=timeout)

    def force_scan(self) -> List[ExecutionRecordProxy]:
        """Manual scan (e.g., at shutdown). Returns newly found records."""
        return self._scan_once()

    def reset_seen(self) -> None:
        with self._lock:
            self._seen_ids.clear()


__all__ = ["ExperienceListener", "ExecutionRecordProxy"]
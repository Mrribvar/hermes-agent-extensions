"""Execution Memory — Hermes Execution Layer.

Persists execution history: actions, inputs, outputs, errors,
decision context, status, timing. Basis for future Continuous Learning.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionRecord:
    """A single execution record in memory."""
    execution_id: str
    task_id: str
    status: str                     # pending | running | completed | failed | cancelled
    started_at: str = ""
    ended_at: str = ""
    duration_ms: int = 0

    # Inputs / outputs
    action: str = ""
    tool: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Any = None
    errors: List[str] = field(default_factory=list)

    # Decision context
    decision_context: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    governance_approval: bool = False

    # Recovery
    retry_count: int = 0
    max_retries: int = 3
    last_retry_at: str = ""
    recovery_info: str = ""

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExecutionMemory:
    """Persistent execution history.

    Thread-safe: mutations hold a lock.  Atomic writes: data written to a
    temp file then renamed into place.
    """

    DEFAULT_PATH = os.path.expanduser("~/.hermes/governance/execution_history.json")

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or self.DEFAULT_PATH
        self.records: Dict[str, ExecutionRecord] = {}
        self._lock = threading.Lock()
        self._ensure_dir()
        self._load()

    # --- persistence ---

    def _ensure_dir(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def _load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    rec = ExecutionRecord(**{
                        k: v for k, v in item.items()
                        if k in ExecutionRecord.__dataclass_fields__
                    })
                    self.records[rec.execution_id] = rec
        except (json.JSONDecodeError, IOError):
            pass  # graceful on corrupt file

    def _save(self) -> None:
        """Atomic write."""
        self._ensure_dir()
        data = [r.to_dict() for r in self.records.values()]
        dir_name = os.path.dirname(self.storage_path)
        fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.storage_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # --- mutations ---

    def create(
        self,
        execution_id: str,
        task_id: str,
        action: str = "",
        tool: str = "",
        inputs: Dict[str, Any] = None,
        risk_level: str = "low",
        governance_approval: bool = False,
    ) -> ExecutionRecord:
        """Create a new execution record."""
        rec = ExecutionRecord(
            execution_id=execution_id,
            task_id=task_id,
            status="pending",
            action=action,
            tool=tool,
            inputs=inputs or {},
            risk_level=risk_level,
            governance_approval=governance_approval,
        )
        with self._lock:
            self.records[execution_id] = rec
            self._save()
        return rec

    def start(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Mark execution as started."""
        with self._lock:
            rec = self.records.get(execution_id)
            if not rec:
                return None
            rec.status = "running"
            rec.started_at = datetime.now().isoformat()
            rec.updated_at = rec.started_at
            self._save()
        return rec

    def complete(
        self,
        execution_id: str,
        outputs: Any = None,
        duration_ms: int = 0,
    ) -> Optional[ExecutionRecord]:
        """Mark execution as completed."""
        with self._lock:
            rec = self.records.get(execution_id)
            if not rec:
                return None
            rec.status = "completed"
            rec.ended_at = datetime.now().isoformat()
            rec.duration_ms = duration_ms
            rec.outputs = outputs
            rec.updated_at = rec.ended_at
            self._save()
        return rec

    def fail(
        self,
        execution_id: str,
        error: str = "",
    ) -> Optional[ExecutionRecord]:
        """Mark execution as failed."""
        with self._lock:
            rec = self.records.get(execution_id)
            if not rec:
                return None
            rec.status = "failed"
            rec.ended_at = datetime.now().isoformat()
            rec.updated_at = rec.ended_at
            if error:
                rec.errors.append(error)
            self._save()
        return rec

    def cancel(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Mark execution as cancelled."""
        with self._lock:
            rec = self.records.get(execution_id)
            if not rec:
                return None
            rec.status = "cancelled"
            rec.ended_at = datetime.now().isoformat()
            rec.updated_at = rec.ended_at
            self._save()
        return rec

    # --- queries ---

    def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        return self.records.get(execution_id)

    def get_by_task(self, task_id: str) -> List[ExecutionRecord]:
        return [r for r in self.records.values() if r.task_id == task_id]

    def get_by_status(self, status: str) -> List[ExecutionRecord]:
        return [r for r in self.records.values() if r.status == status]

    def get_all(self) -> List[ExecutionRecord]:
        return list(self.records.values())

    def get_stats(self) -> Dict[str, Any]:
        """Statistics about execution history."""
        total = len(self.records)
        by_status: Dict[str, int] = {}
        for r in self.records.values():
            by_status[r.status] = by_status.get(r.status, 0) + 1
        return {
            "total": total,
            "by_status": by_status,
        }

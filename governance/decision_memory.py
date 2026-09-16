"""
Decision Memory System - Hermes Phase 7

Stores important decisions with schema:
{
  date,
  decision,
  reason,
  impact,
  rollback,
  result
}
"""

import json
import os
import tempfile
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class DecisionRecord:
    """A single decision record in memory"""
    id: str
    date: str
    decision: str
    reason: str
    impact: str
    rollback: str
    result: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "decision": self.decision,
            "reason": self.reason,
            "impact": self.impact,
            "rollback": self.rollback,
            "result": self.result,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRecord":
        return cls(
            id=data.get("id", ""),
            date=data.get("date", ""),
            decision=data.get("decision", ""),
            reason=data.get("reason", ""),
            impact=data.get("impact", ""),
            rollback=data.get("rollback", ""),
            result=data.get("result", "pending"),
            metadata=data.get("metadata", {})
        )


class DecisionMemory:
    """
    Persistent decision memory for Hermes governance layer.

    Thread-safe: all mutations hold a lock to prevent concurrent-write clobbering.
    Atomic writes: data is serialized to a temp file then renamed into place so
    a crash mid-write can never leave a half-written JSON on disk.
    """

    DEFAULT_PATH = os.path.expanduser("~/.hermes/governance/decisions.json")

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or self.DEFAULT_PATH
        self.decisions: Dict[str, DecisionRecord] = {}
        self._lock = threading.Lock()
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist"""
        dir_path = os.path.dirname(self.storage_path)
        os.makedirs(dir_path, exist_ok=True)

    def _load(self) -> None:
        """Load decisions from storage file (caller must hold _lock)"""
        if not os.path.exists(self.storage_path):
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    record = DecisionRecord.from_dict(item)
                    self.decisions[record.id] = record
            elif isinstance(data, dict):
                for key, item in data.items():
                    record = DecisionRecord.from_dict(item)
                    self.decisions[record.id] = record
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load decision memory: {e}")

    def _save(self) -> None:
        """Atomic save: write to temp file then rename.

        Caller must hold _lock.  The two-step write (temp → rename) ensures a
        crash or power loss mid-write never leaves a half-written file on disk.
        """
        self._ensure_storage_dir()
        data = [record.to_dict() for record in self.decisions.values()]

        dir_name = os.path.dirname(self.storage_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # os.replace is atomic on POSIX (and on NTFS when src/dst on same vol)
            os.replace(tmp_path, self.storage_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def record(self, decision: str, reason: str, impact: str,
               rollback: str, result: str = "pending",
               metadata: Dict[str, Any] = None) -> DecisionRecord:
        """
        Record a new decision.
        """
        import uuid

        record_id = f"decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        record = DecisionRecord(
            id=record_id,
            date=datetime.now().isoformat(),
            decision=decision,
            reason=reason,
            impact=impact,
            rollback=rollback,
            result=result,
            metadata=metadata or {}
        )

        with self._lock:
            self.decisions[record_id] = record
            self._save()

        return record

    def update_result(self, record_id: str, result: str) -> bool:
        """Update the result of a decision"""
        with self._lock:
            if record_id not in self.decisions:
                return False
            self.decisions[record_id].result = result
            self._save()
            return True

    def get(self, record_id: str) -> Optional[DecisionRecord]:
        """Get a specific decision by ID"""
        return self.decisions.get(record_id)

    def get_all(self) -> List[DecisionRecord]:
        """Get all decisions"""
        return list(self.decisions.values())

    def get_recent(self, limit: int = 10) -> List[DecisionRecord]:
        """Get most recent decisions"""
        sorted_decisions = sorted(
            self.decisions.values(),
            key=lambda d: d.date,
            reverse=True
        )
        return sorted_decisions[:limit]

    def get_by_decision(self, decision_text: str) -> List[DecisionRecord]:
        """Search decisions by decision text"""
        return [
            d for d in self.decisions.values()
            if decision_text.lower() in d.decision.lower()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored decisions"""
        total = len(self.decisions)
        results = {}
        for d in self.decisions.values():
            r = d.result
            results[r] = results.get(r, 0) + 1

        return {
            "total_decisions": total,
            "by_result": results,
            "oldest": min(d.date for d in self.decisions.values()) if self.decisions else None,
            "newest": max(d.date for d in self.decisions.values()) if self.decisions else None
        }

    def export_json(self) -> str:
        """Export all decisions as JSON string"""
        data = [d.to_dict() for d in self.decisions.values()]
        return json.dumps(data, indent=2, ensure_ascii=False)

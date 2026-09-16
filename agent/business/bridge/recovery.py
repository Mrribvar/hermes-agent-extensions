# Phase 13.2.5 — Recovery Compatibility.
#
# Scans business events against execution memory to detect "interrupted"
# flows (event was created but execution never completed). Reports status
# and suggests recovery actions. NO automatic execution/rollback happens here.
#
# Additive only.
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.business.events.event import BusinessEvent
from agent.business.bridge.memory_bridge import MemoryBridge


@dataclass
class RecoveryFinding:
    event_id: str
    entity_id: str
    entity_type: str
    action: str
    status: str  # COMPLETE / INCOMPLETE / MISSING
    suggested_recovery: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "action": self.action,
            "status": self.status,
            "suggested_recovery": self.suggested_recovery,
        }


@dataclass
class RecoveryReport:
    findings: List[RecoveryFinding] = field(default_factory=list)

    @property
    def incomplete_count(self) -> int:
        return len([
            f for f in self.findings
            if getattr(f, "status", "") in ("INCOMPLETE", "MISSING")
        ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_findings": len(self.findings),
            "incomplete_count": self.incomplete_count,
            "findings": [f.to_dict() for f in self.findings],
        }


class RecoveryProbe:
    """Finds interrupted business operations. Read-only + report."""

    def __init__(
        self,
        memory_bridge: Optional[MemoryBridge] = None,
        events: Optional[List[BusinessEvent]] = None,
        db_path: Optional[Path | str] = None,
    ) -> None:
        self._bridge = memory_bridge or MemoryBridge(db_path=db_path)
        self._provided_events = list(events or [])

    def scan(self, events: Optional[List[BusinessEvent]] = None) -> RecoveryReport:
        """Check each event against execution memory for completion."""
        event_list = events if events is not None else self._provided_events
        findings: List[RecoveryFinding] = []

        for event in event_list:
            record = self._bridge.lookup(event)
            if record is None:
                findings.append(
                    RecoveryFinding(
                        event_id=event.event_id,
                        entity_id=event.entity_id,
                        entity_type=event.entity_type,
                        action=event.action,
                        status="MISSING",
                        suggested_recovery=(
                            "No execution record found. Replay event into MemoryBridge "
                            f"(record_event) to mark {event.action} as completed."
                        ),
                    )
                )
                continue
            status = record.get("result_status", "")
            if status in ("failed", "cancelled"):
                findings.append(
                    RecoveryFinding(
                        event_id=event.event_id,
                        entity_id=event.entity_id,
                        entity_type=event.entity_type,
                        action=event.action,
                        status="INCOMPLETE",
                        suggested_recovery=(
                            f"Execution ended with status '{status}'. Review error and "
                            "re-run the operation; no auto-recovery performed."
                        ),
                    )
                )
            else:
                findings.append(
                    RecoveryFinding(
                        event_id=event.event_id,
                        entity_id=event.entity_id,
                        entity_type=event.entity_type,
                        action=event.action,
                        status="COMPLETE",
                        suggested_recovery="None required.",
                    )
                )

        return RecoveryReport(findings=findings)


def build_incomplete_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "system",
    action: Optional[str] = None,
) -> BusinessEvent:
    """Build an event that mimics an interrupted execution (no memory record)."""
    import uuid
    from agent.business.events.event import BusinessEvent as BE
    from datetime import datetime, timezone

    return BE(
        event_id=f"interrupted-{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action or event_type,
        actor=actor,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


__all__ = [
    "RecoveryProbe",
    "RecoveryReport",
    "RecoveryFinding",
    "build_incomplete_event",
]
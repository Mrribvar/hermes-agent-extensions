# Phase 13.2.1 — Business Event Layer.
#
# Immutable event log: captures *what changed* on business entities before/
# after persistence. Decoupled from storage — events live here as pure
# dataclasses. Persistence + execution-memory wiring happens in bridge/.
#
# Additive only. No changes to agent/execution/* or governance/*.
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import uuid


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BusinessEventType(str, Enum):
    PRODUCT_CREATED = "PRODUCT_CREATED"
    PRODUCT_UPDATED = "PRODUCT_UPDATED"
    PRODUCT_PRICE_CHANGED = "PRODUCT_PRICE_CHANGED"
    PRODUCT_DELETED = "PRODUCT_DELETED"
    CATEGORY_CREATED = "CATEGORY_CREATED"
    CUSTOMER_CREATED = "CUSTOMER_CREATED"


@dataclass
class BusinessEvent:
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actor: str = "system"
    timestamp: str = field(default_factory=_utc_now)
    risk_level: str = RiskLevel.LOW.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_id.strip():
            self.event_id = str(uuid.uuid4())
        if not self.event_type or not self.event_type.strip():
            raise ValueError("event_type is required")
        if not self.entity_type or not self.entity_type.strip():
            raise ValueError("entity_type is required")
        if not self.entity_id or not self.entity_id.strip():
            raise ValueError("entity_id is required")
        if not self.action or not self.action.strip():
            raise ValueError("action is required")
        if not self.actor or not self.actor.strip():
            self.actor = "system"
        if not self.timestamp:
            self.timestamp = _utc_now()
        if self.risk_level not in {r.value for r in RiskLevel}:
            self.risk_level = RiskLevel.LOW.value
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BusinessEvent":
        if not isinstance(data, dict):
            raise ValueError("BusinessEvent data must be a dict")
        required = ["event_id", "event_type", "entity_type", "entity_id",
                    "action", "actor", "timestamp"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"missing required fields: {missing}")
        # Copy metadata shallowly, drop non-expected keys to avoid injection
        md = data.get("metadata") or {}
        if not isinstance(md, dict):
            raise ValueError("metadata must be a dict")
        return BusinessEvent(
            event_id=str(data["event_id"]),
            event_type=str(data["event_type"]),
            entity_type=str(data["entity_type"]),
            entity_id=str(data["entity_id"]),
            action=str(data["action"]),
            actor=str(data.get("actor", "system")),
            timestamp=str(data["timestamp"]),
            risk_level=str(data.get("risk_level", RiskLevel.LOW.value)),
            metadata=dict(md),
        )


__all__ = [
    "BusinessEvent",
    "BusinessEventType",
    "RiskLevel",
]
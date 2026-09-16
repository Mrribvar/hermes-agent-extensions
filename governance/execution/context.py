"""Execution Context — Hermes Execution Layer.

Immutable record of a single execution's parameters and metadata.
Created once at submission time, passed through the entire lifecycle.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionContext:
    """Context for a single execution — immutable after creation."""
    # Identity
    task_id: str
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Ownership
    user: str = "system"
    project: str = "hermes"
    skill: str = ""

    # Tooling
    provider: str = ""
    required_tools: List[str] = field(default_factory=list)

    # Governance
    risk_level: str = "low"           # safe | low | medium | high
    governance_approval: bool = False  # must be True before execution starts
    approval_id: str = ""

    # Execution parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict for storage."""
        return {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp,
            "user": self.user,
            "project": self.project,
            "skill": self.skill,
            "provider": self.provider,
            "required_tools": list(self.required_tools),
            "risk_level": self.risk_level,
            "governance_approval": self.governance_approval,
            "approval_id": self.approval_id,
            "parameters": dict(self.parameters),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionContext:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

"""Recovery Hooks — Hermes Execution Layer.

Prepares interfaces for Recovery, Retry, Rollback, Checkpoint.
Do NOT implement self-healing yet. Interface-only for future use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RecoveryAction:
    """A single recovery action (interface definition)."""
    kind: str                    # "retry" | "rollback" | "checkpoint" | "resume"
    execution_id: str
    parameters: dict = field(default_factory=dict)
    note: str = ""


class RecoveryState(ABC):
    """Interface for storing/retrieving recovery state.

    Implementations (e.g. disk-based checkpoint store) come in a future phase.
    """

    @abstractmethod
    def save_checkpoint(self, execution_id: str, state: dict) -> None:
        """Persist a checkpoint for an execution."""

    @abstractmethod
    def load_checkpoint(self, execution_id: str) -> dict | None:
        """Load the latest checkpoint for an execution."""

    @abstractmethod
    def clear_checkpoint(self, execution_id: str) -> None:
        """Remove all checkpoints for an execution."""


class RetryPolicy:
    """Backoff policy for retries (interface definition)."""

    def __init__(self, max_retries: int = 3, backoff_base_seconds: float = 1.0):
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds

    def get_delay(self, retry_count: int) -> float:
        """Exponential backoff: base * 2^retry_count."""
        if retry_count <= 0:
            return 0.0
        return self.backoff_base_seconds * (2 ** (retry_count - 1))

    def can_retry(self, retry_count: int) -> bool:
        """Check if more retries are allowed."""
        return retry_count < self.max_retries


class RecoveryExecutor(ABC):
    """Interface that a future Recovery System will implement.

    This phase only defines the contract — no self-healing logic.
    The Execution Engine calls these hooks where possible but never
    auto-executes self-healing.
    """

    @abstractmethod
    def plan_recovery(self, execution_id: str) -> list[RecoveryAction]:
        """Return a list of recovery actions for a failed execution.

        Interface-only. Actual planning in future phase.
        """

    @abstractmethod
    def can_recover(self, execution_id: str) -> bool:
        """Check whether execution has a recovery path."""

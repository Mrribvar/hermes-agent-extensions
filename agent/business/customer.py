# Phase 13.1 — Customer entity.
#
# Standard Business Customer Entity. Storage lives in EntityStore.
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CustomerSegment:
    """Persistent classification of a customer."""

    name: str
    description: str = ""


@dataclass
class CustomerCreate:
    """Minimal typed input for creating a Customer."""

    name: str
    email: str = ""
    segment: str = ""


@dataclass
class Customer:
    """Standard Business Customer Entity."""

    name: str
    email: str = ""
    segment: str = ""
    tags: List[str] = field(default_factory=list)
    lifetime_value: float = 0.0

    @staticmethod
    def from_raw(raw: Dict[str, Any]) -> "Customer":
        if not isinstance(raw, dict):
            raise ValueError("customer raw data must be a dict")
        return Customer(
            name=str(raw.get("name", "")).strip(),
            email=str(raw.get("email", "")).strip(),
            segment=str(raw.get("segment", "")).strip(),
            tags=Customer._to_str_list(raw.get("tags")),
            lifetime_value=Customer._to_float(raw.get("lifetime_value", 0.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _to_str_list(v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @staticmethod
    def _to_float(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
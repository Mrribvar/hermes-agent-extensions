# Phase 13.1 — Base Business Entity + Entity Store.
#
# Generic in-memory store that holds Product / Category / Customer entities.
# Kept independent from ExecutionMemory (Phase 11.7); Phase 13.2 bridges them.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


class EntityNotFoundError(Exception):
    pass


@dataclass
class BusinessEntity:
    """Common base for business-wide attributes used in auditing."""

    name: str
    entity_type: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


EntityT = TypeVar("EntityT")


class EntityStore(Generic[EntityT]):
    """Generic in-memory store for business entities.

    Thread-safe for reads; no write-locks yet — phase scope limited.
    Replace with SQLite in later business phases if needed.
    """

    def __init__(self, name: str = "") -> None:
        self._name = name
        self._items: Dict[str, EntityT] = {}
        self._tags: Dict[str, List[str]] = {}

    def put(self, key: str, entity: EntityT, tags: Optional[List[str]] = None) -> None:
        if not key or not key.strip():
            raise ValueError("entity key must be non-empty")
        self._items[key.strip()] = entity
        if tags:
            self._tags[key.strip()] = [str(t).strip() for t in tags if t]

    def get(self, key: str) -> Optional[EntityT]:
        return self._items.get(key.strip())

    def require(self, key: str) -> EntityT:
        k = key.strip()
        e = self._items.get(k)
        if e is None:
            raise EntityNotFoundError(f"entity {k!r} not found in store {self._name!r}")
        return e

    def delete(self, key: str) -> bool:
        k = key.strip()
        existed = k in self._items
        self._items.pop(k, None)
        self._tags.pop(k, None)
        return existed

    def list_all(self) -> Dict[str, EntityT]:
        return dict(self._items)

    def search_by_tag(self, tag: str) -> Dict[str, EntityT]:
        return {k: v for k, v in self._items.items() if tag in self._tags.get(k, [])}

    def size(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._tags.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "count": self.size(),
            "keys": sorted(self._items.keys()),
        }
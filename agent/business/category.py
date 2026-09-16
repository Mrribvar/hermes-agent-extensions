# Phase 13.1 — Category Entity.
#
# Standard product category + optional in-memory tree hierarchy.
# Pure data; storage lives in EntityStore.
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class CategoryNotFoundError(Exception):
    pass


@dataclass
class Category:
    """Business category for products."""

    name: str
    parent: Optional[str] = None
    description: str = ""
    children: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CategoryTree:
    """Tiny in-memory hierarchy over Category objects."""

    def __init__(self, categories: Optional[List[Category]] = None) -> None:
        self._by_name: Dict[str, Category] = {}
        if categories:
            for c in categories:
                self.add(c)

    def add(self, category: Category) -> None:
        name = (category.name or "").strip()
        if not name:
            raise ValueError("category name must be non-empty")
        self._by_name[name] = category

    def get(self, name: str) -> Optional[Category]:
        return self._by_name.get(name)

    def require(self, name: str) -> Category:
        c = self.get(name)
        if c is None:
            raise CategoryNotFoundError(f"category {name!r} not found")
        return c

    def children_of(self, name: str) -> List[Category]:
        parent = self.get(name)
        if parent is None:
            return []
        return [self._by_name[c] for c in parent.children if c in self._by_name]

    def root_names(self) -> List[str]:
        roots = []
        for name, c in self._by_name.items():
            if not c.parent or c.parent not in self._by_name:
                roots.append(name)
        return sorted(roots)

    def size(self) -> int:
        return len(self._by_name)
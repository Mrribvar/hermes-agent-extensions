# Phase 13.1 — Product Entity.
#
# Converts raw product data into a standard Product Business Entity.
# Pure dataclasses + factory methods; no storage here (see EntityStore).
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PRODUCT_STATUS_ACTIVE = "active"
PRODUCT_STATUS_DRAFT = "draft"
PRODUCT_STATUS_ARCHIVED = "archived"
VALID_PRODUCT_STATUS = {
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_DRAFT,
    PRODUCT_STATUS_ARCHIVED,
}

# Type alias for status string.
ProductStatus = str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProductCreate:
    """Minimal typed input for creating a Product Entity."""

    name: str
    category: str = ""
    price: float = 0.0
    status: str = ""
    keywords: Optional[List[str]] = None
    content_links: Optional[List[str]] = None


@dataclass
class ProductPerformance:
    """Rolling performance numbers for a product (0 when unknown)."""

    views: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Product:
    """Standard Business Product Entity."""

    name: str
    category: str = "draft"
    price: float = 0.0
    status: str = PRODUCT_STATUS_DRAFT
    keywords: List[str] = field(default_factory=list)
    content_links: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    performance: Optional[ProductPerformance] = None
    created_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        st = self.status or PRODUCT_STATUS_DRAFT
        if st not in VALID_PRODUCT_STATUS:
            raise ValueError(
                f"invalid status {st!r}; expected one of {sorted(VALID_PRODUCT_STATUS)}"
            )
        self.status = st
        if self.price is None:
            self.price = 0.0
        if self.keywords is None:
            self.keywords = []
        if self.content_links is None:
            self.content_links = []
        if self.tasks is None:
            self.tasks = []
        if self.performance is None:
            self.performance = ProductPerformance()

    @staticmethod
    def from_raw(raw: Dict[str, Any]) -> "Product":
        """Build a Product from arbitrary raw data (partial allowed)."""
        return Product(
            name=str(raw.get("name", "")).strip(),
            category=str(raw.get("category", "")).strip(),
            price=Product._to_float(raw.get("price", 0.0)),
            status=Product._normalize_status(raw.get("status")),
            keywords=Product._to_str_list(raw.get("keywords")),
            content_links=Product._to_str_list(raw.get("content_links")),
            tasks=Product._to_str_list(raw.get("tasks")),
            performance=Product._to_performance(raw.get("performance")),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category
        return d

    @staticmethod
    def _normalize_status(v: Any) -> str:
        s = str(v or "").strip().lower() if v is not None else ""
        if s not in VALID_PRODUCT_STATUS:
            return PRODUCT_STATUS_DRAFT
        return s

    @staticmethod
    def _to_float(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_str_list(v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [s for s in (x.strip() for x in v.split(",")) if s]
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @staticmethod
    def _to_performance(v: Any) -> Optional[ProductPerformance]:
        if isinstance(v, ProductPerformance):
            return v
        if not isinstance(v, dict):
            return None
        if not v:
            return None
        return ProductPerformance(
            views=int(v.get("views", 0) or 0),
            clicks=int(v.get("clicks", 0) or 0),
            conversions=int(v.get("conversions", 0) or 0),
            revenue=Product._to_float(v.get("revenue", 0.0)),
        )
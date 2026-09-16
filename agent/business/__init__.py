# Business Intelligence Layer — Phase 13 (13.1 + 13.2).
#
# Additive only. No changes to agent/execution/* or governance/*.
from __future__ import annotations

# ---- Phase 13.1: entities ---------------------------------------------
from .product import (
    Product,
    ProductCreate,
    ProductPerformance,
    ProductStatus,
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_DRAFT,
    PRODUCT_STATUS_ARCHIVED,
)
from .category import Category, CategoryTree, CategoryNotFoundError
from .customer import Customer, CustomerCreate, CustomerSegment
from .business_entity import BusinessEntity, EntityStore, EntityNotFoundError

# ---- Phase 13.2: events + bridge --------------------------------------
from .events import BusinessEvent, BusinessEventType, RiskLevel
from .bridge import (
    PersistentEntityStore,
    MemoryBridge,
    GovernanceAdapter,
    GovernanceDecision,
    GovernanceVerdict,
    RecoveryProbe,
    RecoveryReport,
    RecoveryFinding,
    build_incomplete_event,
)

__all__ = [
    # entities (13.1)
    "Product",
    "ProductCreate",
    "ProductPerformance",
    "ProductStatus",
    "PRODUCT_STATUS_ACTIVE",
    "PRODUCT_STATUS_DRAFT",
    "PRODUCT_STATUS_ARCHIVED",
    "Category",
    "CategoryTree",
    "CategoryNotFoundError",
    "Customer",
    "CustomerCreate",
    "CustomerSegment",
    "BusinessEntity",
    "EntityStore",
    "EntityNotFoundError",
    # events (13.2.1)
    "BusinessEvent",
    "BusinessEventType",
    "RiskLevel",
    # bridge (13.2.x)
    "PersistentEntityStore",
    "MemoryBridge",
    "GovernanceAdapter",
    "GovernanceDecision",
    "GovernanceVerdict",
    "RecoveryProbe",
    "RecoveryReport",
    "RecoveryFinding",
    "build_incomplete_event",
]
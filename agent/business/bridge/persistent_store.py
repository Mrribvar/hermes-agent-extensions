# Phase 13.2.2 — Persistent Entity Bridge.
#
# Bridges in-memory EntityStore to SQLite persistence.
# Storage lives in a dedicated DB under HERMES_HOME — no changes to
# agent/execution/memory.py (Phase 11.7). Entity API (Product/Category/Customer)
# stays unchanged; only storage backend is added.
#
# Additive only.
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

from agent.business.business_entity import EntityStore, EntityNotFoundError
from agent.business.product import Product
from agent.business.category import Category
from agent.business.customer import Customer

EntityT = TypeVar("EntityT")


class PersistentEntityStore(EntityStore[EntityT]):
    """SQLite-backed entity store.

    Keeps the in-memory EntityStore API intact. On top of put/get/delete,
    adds persistence so entities survive process restarts.

    Thread-safe: module-connection pattern (WAL) + local RLock, same
    style as ExecutionMemory (Phase 11.7).
    """

    def __init__(self, name: str = "", db_path: Optional[Path | str] = None) -> None:
        super().__init__(name=name)
        self._lock = threading.RLock()
        if db_path is None:
            try:
                from hermes_constants import get_hermes_home
                base = get_hermes_home()
            except Exception:  # pragma: no cover
                base = Path.home() / ".hermes"
            db_path = base / "business_entities.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # -- connection -------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    # -- schema -----------------------------------------------------------

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    store_name   TEXT NOT NULL,
                    key          TEXT NOT NULL,
                    entity_type  TEXT NOT NULL,
                    payload      TEXT NOT NULL DEFAULT '{}',
                    tags         TEXT NOT NULL DEFAULT '[]',
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    PRIMARY KEY (store_name, key)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_store ON entities(store_name)"
            )
            conn.commit()
        finally:
            conn.close()

    # -- core operations --------------------------------------------------

    def put(self, key: str, entity: EntityT, tags: Optional[List[str]] = None) -> None:
        with self._lock:
            super().put(key, entity, tags=tags)
            if hasattr(entity, "to_dict"):
                raw = entity.to_dict()
            elif hasattr(entity, "__dataclass_fields__"):
                raw = asdict(entity)
            else:
                raw = entity if isinstance(entity, dict) else {"_raw": repr(entity)}
            raw["__entity_type__"] = type(entity).__name__
            payload = json.dumps(raw, default=str, sort_keys=True)
            tags_json = json.dumps(tags or [])
            now = _utc_now()
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO entities (store_name, key, entity_type, payload, tags, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(store_name, key) DO UPDATE SET
                        payload=excluded.payload,
                        tags=excluded.tags,
                        updated_at=excluded.updated_at
                    """,
                    (self._name, key.strip(), type(entity).__name__, payload, tags_json, now, now),
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, key: str) -> Optional[EntityT]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM entities WHERE store_name=? AND key=?",
                    (self._name, key.strip()),
                ).fetchone()
            finally:
                conn.close()
            if row is None:
                return None
            try:
                payload = json.loads(row["payload"])
            except (json.JSONDecodeError, TypeError):
                return None  # corrupted payload — cannot reconstruct
            return self._reconstruct(payload)

    def require(self, key: str) -> EntityT:
        e = self.get(key)
        if e is None:
            raise EntityNotFoundError(f"entity {key!r} not found in persistent store {self._name!r}")
        return e

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = super().delete(key)
            conn = self._connect()
            try:
                conn.execute(
                    "DELETE FROM entities WHERE store_name=? AND key=?",
                    (self._name, key.strip()),
                )
                conn.commit()
            finally:
                conn.close()
            return existed

    def list_all(self) -> Dict[str, EntityT]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT key, payload FROM entities WHERE store_name=?",
                    (self._name,),
                ).fetchall()
            finally:
                conn.close()
            result: Dict[str, EntityT] = {}
            for row in rows:
                payload = json.loads(row["payload"])
                result[row["key"]] = self._reconstruct(payload)
            return result

    def search_by_tag(self, tag: str) -> Dict[str, EntityT]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT key, payload, tags FROM entities WHERE store_name=?",
                    (self._name,),
                ).fetchall()
            finally:
                conn.close()
            result: Dict[str, EntityT] = {}
            for row in rows:
                tags = json.loads(row["tags"])
                if tag in tags:
                    payload = json.loads(row["payload"])
                    result[row["key"]] = self._reconstruct(payload)
            return result

    def size(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM entities WHERE store_name=?",
                    (self._name,),
                ).fetchone()
            finally:
                conn.close()
            return int(row["cnt"]) if row else 0

    def clear(self) -> None:
        with self._lock:
            super().clear()
            conn = self._connect()
            try:
                conn.execute("DELETE FROM entities WHERE store_name=?", (self._name,))
                conn.commit()
            finally:
                conn.close()

    # -- helpers ----------------------------------------------------------

    def _reconstruct(self, payload: Dict[str, Any]) -> EntityT:
        entity_type = payload.pop("__entity_type__", "")
        if Product.__name__ == entity_type:
            return Product.from_raw(payload)  # type: ignore[return-value]
        if Category.__name__ == entity_type:
            return Category(**payload)  # type: ignore[return-value]
        if Customer.__name__ == entity_type:
            return Customer.from_raw(payload)  # type: ignore[return-value]
        # Corrupted or unknown type: return raw dict fallback
        return payload  # type: ignore[return-value]


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
"""Intelligence Persistence Layer — Phase HERALD-INTELLIGENCE-013.

Append-only, versioned, fail-safe persistence for decision intelligence data.

Design goals:
- Additive only: never blocks execution, never mutates existing data.
- Persistent: data survives process restarts (same path reloads prior state).
- Append-only: records are only ever appended; never edited or deleted via
  the public API (tests may rebuild a fresh store at a temp path).
- Migration-safe: on-disk records carry a format version and are migrated
  forwards when older than the supported version.

Fail-safe contract:
- Every mutation degrades to False / None on error; reads degrade to [] / {}.
- No call ever raises during normal execution.

Sections stored:
    decisions          : normalized decision payloads (strategy, outcome...)
    evaluations        : outcome evaluations (is_success, accuracy...)
    feedback           : DecisionFeedback signals (improvement_signal...)
    strategy_metrics   : per-strategy performance metric snapshots
    confidence_history : confidence values recorded over time

Phase HERALD-INTELLIGENCE-013
"""

from __future__ import annotations

import copy
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Current on-disk format version.
FORMAT_VERSION = 1

# Canonical append-only section names.
SECTIONS: Tuple[str, ...] = (
    "decisions",
    "evaluations",
    "feedback",
    "strategy_metrics",
    "confidence_history",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Migration registry. Keys are FROM versions; values are callables that move a
# raw-doc dict one version forward, additively. There is no migration out of
# the current version; that's intentionally the end of the chain.
############################################################################
_MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], None]] = {}


def register_migration(from_version: int):
    """Decorator to register a forward-migration function."""

    def wrapper(func: Callable[[Dict[str, Any]], None]) -> Callable[[Dict[str, Any]], None]:
        _MIGRATIONS[from_version] = func
        return func

    return wrapper


@register_migration(0)
def _migrate_v0(data: Dict[str, Any]) -> None:
    """v0 -> v1: ensure a 'sections' dict and a 'format_version' key exist."""
    if not isinstance(data.get("sections"), dict):
        # Pre-version dump: a bare list of records without a container.
        records = data.get("sections", [])
        data["sections"] = {"decisions": records if isinstance(records, list) else []}
    data.setdefault("format_version", 0)


############################################################################


def _rebuild_sections(
    sections_raw: Any,
) -> Dict[str, List[Dict[str, Any]]]:
    """Coerce an arbitrary parsed 'sections' value into the canonical shape."""
    fresh: Dict[str, List[Dict[str, Any]]] = {s: [] for s in SECTIONS}
    if not isinstance(sections_raw, dict):
        return fresh
    for name in SECTIONS:
        values = sections_raw.get(name, [])
        if isinstance(values, list):
            fresh[name] = [v for v in values if isinstance(v, dict)]
    return fresh


class IntelligenceStore:
    """Append-only, versioned persistence for intelligence data.

    Persistence format (JSON, atomic write via temp-file + replace):
        {
          "format_version": 1,
          "created_at": "...",
          "updated_at": "...",
          "sections": {
            "decisions": [...], "evaluations": [...], "feedback": [...],
            "strategy_metrics": [...], "confidence_history": [...]
          }
        }

    Thread-safe and fail-safe; never raises during normal operation.
    """

    def __init__(self, storage_path: Union[str, Path, None] = None) -> None:
        if storage_path is None:
            self._path: Path = Path.home() / ".hermes" / "governance" / "intelligence.json"
        else:
            self._path = Path(storage_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._sections: Dict[str, List[Dict[str, Any]]] = {s: [] for s in SECTIONS}
        self._format_version: int = FORMAT_VERSION
        self._created_at: str = _utc_now()
        self._updated_at: str = _utc_now()
        self._format_errors: List[str] = []

        self._load()

    # ------------------------------------------------------------------ #
    # Introspection (never raises).

    @property
    def format_version(self) -> int:
        return self._format_version

    @property
    def storage_path(self) -> Path:
        return self._path

    @property
    def format_errors(self) -> List[str]:
        with self._lock:
            return list(self._format_errors)

    def exists(self) -> bool:
        return self._path.exists()

    def is_valid(self) -> bool:
        """A loaded file is round-trip valid if it produced no format warnings."""
        return not self._format_errors

    # ------------------------------------------------------------------ #
    # Append operations (additive, fail-safe -> bool).

    def append_decision(self, payload: Dict[str, Any]) -> bool:
        return self._append("decisions", payload)

    def append_evaluation(self, payload: Dict[str, Any]) -> bool:
        return self._append("evaluations", payload)

    def append_feedback(self, payload: Dict[str, Any]) -> bool:
        return self._append("feedback", payload)

    def append_strategy_metrics(self, payload: Dict[str, Any]) -> bool:
        return self._append("strategy_metrics", payload)

    def append_confidence(self, payload: Dict[str, Any]) -> bool:
        return self._append("confidence_history", payload)

    # ------------------------------------------------------------------ #
    # Read operations (never raise; copy-on-read).

    def read_decisions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read("decisions", limit)

    def read_evaluations(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read("evaluations", limit)

    def read_feedback(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read("feedback", limit)

    def read_strategy_metrics(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read("strategy_metrics", limit)

    def read_confidence_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._read("confidence_history", limit)

    # ------------------------------------------------------------------ #

    def counts(self) -> Dict[str, int]:
        with self._lock:
            return {name: len(self._sections[name]) for name in SECTIONS}

    def read_all(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            return {
                name: [copy.deepcopy(item) for item in self._sections[name]]
                for name in SECTIONS
            }

    # ------------------------------------------------------------------ #
    # Internal helpers.

    def _append(self, section: str, payload: Dict[str, Any]) -> bool:
        if section not in SECTIONS:
            return False
        with self._lock:
            try:
                entry = dict(payload)
                entry.setdefault("ts", _utc_now())
                self._sections.setdefault(section, []).append(entry)
                self._updated_at = _utc_now()
                self._persist()
                return True
            except Exception as exc:  # noqa: BLE001 - fail-safe
                logger.error("IntelligenceStore append(%s) failed: %s", section, exc)
                return False

    def _read(self, section: str, limit: Optional[int]) -> List[Dict[str, Any]]:
        with self._lock:
            items = self._sections.get(section, [])
            selected = items if limit is None else items[-limit:]
            return [copy.deepcopy(item) for item in selected]

    def _persist(self) -> None:
        doc = {
            "format_version": self._format_version,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "sections": self._sections,
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
        tmp.replace(self._path)

    def _load(self) -> None:
        if not self._path.exists():
            self._persist()
            return

        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Intelligence store unreadable at %s; starting fresh: %s",
                           self._path, exc)
            self._format_errors.append(f"unreadable: {exc}")
            self._persist()
            return

        if not isinstance(data, dict):
            self._format_errors.append("root not a dict")
            self._persist()
            return

        raw_version = int(data.get("format_version", 0))
        if raw_version > FORMAT_VERSION:
            self._format_errors.append(
                f"on-disk version {raw_version} newer than supported {FORMAT_VERSION}"
            )

        migrated = self._apply_migrations(data, raw_version)
        if migrated:
            self._format_version = FORMAT_VERSION
            self._updated_at = _utc_now()

        self._sections = _rebuild_sections(data.get("sections"))
        self._created_at = data.get("created_at", self._created_at)
        self._updated_at = data.get("updated_at", self._updated_at)

        if migrated:
            self._persist()

    def _apply_migrations(self, data: Dict[str, Any], raw_version: int) -> bool:
        """Apply forward migrations from raw_version up to FORMAT_VERSION.

        Returns True if the version advanced.
        """
        version = raw_version
        changed = False
        while version < FORMAT_VERSION:
            step = _MIGRATIONS.get(version)
            if step is None:
                logger.warning(
                    "No migration path from format_version=%s; preserving as-is.", version
                )
                break
            try:
                step(data)
            except Exception as exc:  # noqa: BLE001 - never break the caller
                logger.error("Migration %s->%s failed: %s", version, version + 1, exc)
                break
            version += 1
            changed = True
        if changed:
            data["format_version"] = FORMAT_VERSION
        return changed
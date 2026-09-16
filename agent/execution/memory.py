# Execution Layer — Phase 11.7: Execution Memory Foundation
#
# Persistent memory for execution lifecycle and outcomes only.
#
# Separation of concerns (kept distinct):
#   DecisionMemory   - WHY a decision was made (governance)
#   ExecutionMemory  - WHAT happened during execution (this module)
#   ExperienceMemory - WHAT Hermes learned from it
#
# This module stores ONLY execution lifecycle data: state transitions,
# governance verdict, tool used, result, error, timing. It does NOT replace
# or duplicate DecisionMemory / ExperienceMemory.
#
# Storage: SQLite, following the established VerificationEvidence pattern
# (WAL journal, busy_timeout, sqlite3.Row factory, schema_version meta).

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import sqlite3
import threading

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover

    def get_hermes_home():  # type: ignore
        import os

        return Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))


__all__ = [
    "ExecutionMemory",
    "ExecutionRecord",
    "InvalidRecordError",
]

_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExecutionRecord:
    """A persisted execution lifecycle record."""

    execution_id: str
    state: str
    task_id: str = ""
    session_id: str = ""
    user_id: str = ""
    project_id: str = ""
    tool_id: str = ""
    governance_verdict: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    result_status: str = ""  # success / failed / cancelled
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["metadata"] = dict(self.metadata)
        return d


class InvalidRecordError(Exception):
    """Raised when an invalid execution record is written."""


class ExecutionMemory:
    """SQLite-backed store for execution lifecycle records.

    Prints to no existing memory; uses its own table in a dedicated
    ``execution_memory.db`` under HERMES_HOME. Injected ``db_path`` allows
    isolated storage in tests (persistence-after-restart is testable).

    Thread-safety: a module-connection pattern with a local lock; WAL allows
    concurrent readers and serializes writers.
    """

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self._lock = threading.RLock()
        self._db_path: Path
        if db_path is None:
            self._db_path = get_hermes_home() / "execution_memory.db"
        else:
            self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # -- connection + schema ---------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_records (
                    execution_id  TEXT PRIMARY KEY,
                    task_id       TEXT NOT NULL DEFAULT '',
                    session_id    TEXT NOT NULL DEFAULT '',
                    user_id       TEXT NOT NULL DEFAULT '',
                    project_id    TEXT NOT NULL DEFAULT '',
                    tool_id       TEXT NOT NULL DEFAULT '',
                    state         TEXT NOT NULL,
                    governance_verdict TEXT NOT NULL DEFAULT '',
                    started_at    TEXT,
                    completed_at  TEXT,
                    duration_ms   INTEGER,
                    result_status TEXT NOT NULL DEFAULT '',
                    error_message TEXT,
                    metadata      TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_project ON execution_records(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_tool ON execution_records(tool_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_state ON execution_records(state)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO memory_meta(key,value) VALUES('schema_version', ?)",
                (str(_SCHEMA_VERSION),),
            )
            conn.commit()
        finally:
            conn.close()

    # -- core operations --------------------------------------------------

    def _validate_id(self, execution_id: Any) -> str:
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise InvalidRecordError("execution_id must be a non-empty string")
        return execution_id.strip()

    def save_execution(self, record: ExecutionRecord) -> str:
        """Insert or update an execution record. Returns execution_id.

        Raises InvalidRecordError for a missing/invalid execution_id.
        """
        with self._lock:
            id_ = self._validate_id(record.execution_id)
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO execution_records (
                        execution_id, task_id, session_id, user_id, project_id,
                        tool_id, state, governance_verdict, started_at,
                        completed_at, duration_ms, result_status,
                        error_message, metadata
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(execution_id) DO UPDATE SET
                        task_id=excluded.task_id,
                        session_id=excluded.session_id,
                        user_id=excluded.user_id,
                        project_id=excluded.project_id,
                        tool_id=excluded.tool_id,
                        state=excluded.state,
                        governance_verdict=excluded.governance_verdict,
                        started_at=excluded.started_at,
                        completed_at=excluded.completed_at,
                        duration_ms=excluded.duration_ms,
                        result_status=excluded.result_status,
                        error_message=excluded.error_message,
                        metadata=excluded.metadata
                    """,
                    (
                        id_,
                        record.task_id,
                        record.session_id,
                        record.user_id,
                        record.project_id,
                        record.tool_id,
                        record.state,
                        record.governance_verdict,
                        record.started_at,
                        record.completed_at,
                        record.duration_ms,
                        record.result_status,
                        record.error_message,
                        json.dumps(record.metadata, sort_keys=True),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            return id_

    def get_execution(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Retrieve one execution record, or None if absent."""
        with self._lock:
            id_ = self._validate_id(execution_id)
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM execution_records WHERE execution_id=?",
                    (id_,),
                ).fetchone()
            finally:
                conn.close()
            if row is None:
                return None
            return self._row_to_record(row)

    def list_executions(
        self, *, limit: int = 100, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List executions, newest first. Optionally filter by project."""
        with self._lock:
            conn = self._connect()
            try:
                if project_id is None:
                    rows = conn.execute(
                        "SELECT * FROM execution_records "
                        "ORDER BY rowid DESC LIMIT ?",
                        (max(1, int(limit)),),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM execution_records "
                        "WHERE project_id=? "
                        "ORDER BY rowid DESC LIMIT ?",
                        (project_id, max(1, int(limit))),
                    ).fetchall()
            finally:
                conn.close()
            return [self._row_to_record(r).to_dict() for r in rows]

    def search_by_project(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return executions for a project (handles None/empty as all)."""
        if not project_id:
            raise InvalidRecordError("project_id must be non-empty")
        return self.list_executions(limit=limit, project_id=project_id)

    def search_by_tool(self, tool_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return executions that used a given tool, newest first."""
        with self._lock:
            if not tool_id:
                raise InvalidRecordError("tool_id must be non-empty")
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM execution_records "
                    "WHERE tool_id=? ORDER BY rowid DESC LIMIT ?",
                    (tool_id, max(1, int(limit))),
                ).fetchall()
            finally:
                conn.close()
            return [self._row_to_record(r).to_dict() for r in rows]

    def recent_failures(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return most recent FAILED/CANCELLED executions."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM execution_records "
                    "WHERE result_status IN ('failed','cancelled') "
                    "ORDER BY rowid DESC LIMIT ?",
                    (max(1, int(limit)),),
                ).fetchall()
            finally:
                conn.close()
            return [self._row_to_record(r).to_dict() for r in rows]

    def update_state(
        self,
        execution_id: str,
        *,
        state: str,
        result_status: Optional[str] = None,
        completed_at: Optional[str] = None,
        error_message: Optional[str] = None,
        governance_verdict: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Patch a record's state fields. Returns updated record or None."""
        with self._lock:
            id_ = self._validate_id(execution_id)
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT * FROM execution_records WHERE execution_id=?",
                    (id_,),
                ).fetchone()
                if existing is None:
                    return None
                sets = ["state=?"]
                vals = [state]
                if result_status is not None:
                    sets.append("result_status=?")
                    vals.append(result_status)
                if completed_at is not None:
                    sets.append("completed_at=?")
                    vals.append(completed_at)
                if error_message is not None:
                    sets.append("error_message=?")
                    vals.append(error_message)
                if governance_verdict is not None:
                    sets.append("governance_verdict=?")
                    vals.append(governance_verdict)
                if duration_ms is not None:
                    sets.append("duration_ms=?")
                    vals.append(duration_ms)
                vals.append(id_)
                conn.execute(
                    f"UPDATE execution_records SET {', '.join(sets)} "
                    "WHERE execution_id=?",
                    vals,
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM execution_records WHERE execution_id=?",
                    (id_,),
                ).fetchone()
            finally:
                conn.close()
            if row is None:
                return None
            return self._row_to_record(row).to_dict()

    # -- helpers ----------------------------------------------------------

    def _row_to_record(self, row: sqlite3.Row) -> ExecutionRecord:
        try:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        except ValueError:
            metadata = {}
        d = dict(row)
        d["metadata"] = metadata
        return ExecutionRecord(
            execution_id=d["execution_id"],
            state=d["state"],
            task_id=d.get("task_id", ""),
            session_id=d.get("session_id", ""),
            user_id=d.get("user_id", ""),
            project_id=d.get("project_id", ""),
            tool_id=d.get("tool_id", ""),
            governance_verdict=d.get("governance_verdict", ""),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            duration_ms=d.get("duration_ms"),
            result_status=d.get("result_status", ""),
            error_message=d.get("error_message"),
            metadata=metadata,
        )
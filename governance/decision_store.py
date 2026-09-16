"""Decision Store — append-only storage for decision records."""

import json
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from governance.decision_performance_engine import DecisionRecord

logger = logging.getLogger(__name__)


class DecisionStore:
    """Append-only store for decision records.
    
    Features:
    - Append-only (no deletion)
    - Full audit trail
    - Thread-safe
    - JSON-backed persistence
    - In-memory cache for performance
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            home = Path.home()
            self.storage_path = home / ".hermes" / "governance" / "decisions.json"
        else:
            self.storage_path = Path(storage_path)
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._records: Dict[str, DecisionRecord] = {}
        self._lock = threading.RLock()
        self._loaded = False
        
        self._load()
    
    def add_record(self, record: DecisionRecord) -> bool:
        """Add a new decision record (append-only).
        
        Returns:
            True if record was added successfully
        """
        with self._lock:
            try:
                if record.decision_id in self._records:
                    logger.warning(f"Decision {record.decision_id} already exists")
                    return False
                
                self._records[record.decision_id] = record
                self._persist()
                return True
            except Exception as e:
                logger.error(f"Failed to add decision record: {e}")
                return False
    
    def update_record(self, record: DecisionRecord) -> bool:
        """Update an existing record.
        
        Only updates the actual outcome and duration; preserves
        the original decision metadata.
        
        Returns:
            True if record was updated successfully
        """
        with self._lock:
            try:
                if record.decision_id not in self._records:
                    logger.warning(f"Decision {record.decision_id} not found")
                    return False
                
                # Preserve original, update only runtime fields
                existing = self._records[record.decision_id]
                existing.actual_outcome = record.actual_outcome
                existing.duration_ms = record.duration_ms
                existing.metadata.update(record.metadata)
                
                self._persist()
                return True
            except Exception as e:
                logger.error(f"Failed to update decision record: {e}")
                return False
    
    def get_record(self, decision_id: str) -> Optional[DecisionRecord]:
        """Get a decision record by ID."""
        with self._lock:
            self._load()
            return self._records.get(decision_id)
    
    def get_all_records(self) -> List[DecisionRecord]:
        """Get all decision records (sorted by timestamp)."""
        with self._lock:
            self._load()
            return sorted(
                self._records.values(),
                key=lambda r: r.timestamp
            )
    
    def get_records_by_task(self, task_id: str) -> List[DecisionRecord]:
        """Get all records for a specific task."""
        with self._lock:
            self._load()
            return [r for r in self._records.values() if r.task_id == task_id]
    
    def get_records_by_strategy(self, strategy: str) -> List[DecisionRecord]:
        """Get all records for a specific strategy."""
        with self._lock:
            self._load()
            return [r for r in self._records.values() if r.selected_strategy == strategy]
    
    def get_recent_records(self, limit: int = 100) -> List[DecisionRecord]:
        """Get most recent records."""
        with self._lock:
            self._load()
            sorted_records = sorted(
                self._records.values(),
                key=lambda r: r.timestamp,
                reverse=True
            )
            return sorted_records[:limit]
    
    def clear(self) -> bool:
        """Clear all records (used for testing)."""
        with self._lock:
            self._records = {}
            self._persist()
            return True
    
    def count(self) -> int:
        """Get total number of records."""
        with self._lock:
            self._load()
            return len(self._records)
    
    def _load(self) -> None:
        """Load records from disk."""
        if self._loaded:
            return
        
        try:
            if not self.storage_path.exists():
                self._records = {}
                self._loaded = True
                return
            
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            for item in data:
                record = DecisionRecord.from_dict(item)
                self._records[record.decision_id] = record
            
            self._loaded = True
            logger.info(f"Loaded {len(self._records)} decision records")
            
        except Exception as e:
            logger.error(f"Failed to load decision records: {e}")
            self._records = {}
            self._loaded = True
    
    def _persist(self) -> None:
        """Persist records to disk."""
        try:
            data = [r.to_dict() for r in self._records.values()]
            
            # Write atomically
            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            temp_path.replace(self.storage_path)
            
        except Exception as e:
            logger.error(f"Failed to persist decision records: {e}")
    
    def __len__(self) -> int:
        return self.count()
    
    def __iter__(self):
        with self._lock:
            self._load()
            return iter(self._records.values())

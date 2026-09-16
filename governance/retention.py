"""Experience Retention Policy Engine for Hermes Experience Learning.

This module provides configurable retention policies for ExperienceMemory,
including classification (GOLD/SILVER/BRONZE), archiving, and deletion rules.

Phase 14.6.1 - ADDITIVE FILE - No modifications to existing frozen files.
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import os
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class RetentionConfig:
    """Configuration for Experience retention policies."""
    
    # Limits
    max_experiences: int = 10000
    max_file_size_mb: int = 50
    max_age_days: int = 90
    archive_threshold: int = 7500  # Archive when active > 75% of max
    compression_days: int = 30      # Compress experiences older than 30 days
    
    # Preservation rules
    gold_confidence_threshold: float = 0.8
    keep_failed: bool = True
    keep_with_lessons: bool = True
    min_occurrences_for_pattern: int = 3
    
    # Background job settings
    background_enabled: bool = True
    interval_seconds: int = 3600  # Run retention check every hour
    batch_size: int = 100
    
    # Archive settings
    archive_dir: str = "archives"
    compress_archives: bool = True
    archive_format: str = "json.gz"
    
    def __post_init__(self):
        """Validate configuration values."""
        if self.max_experiences < 100:
            raise ValueError("max_experiences must be at least 100")
        if self.max_file_size_mb < 1:
            raise ValueError("max_file_size_mb must be at least 1")
        if self.max_age_days < 1:
            raise ValueError("max_age_days must be at least 1")
        if self.archive_threshold > self.max_experiences:
            self.archive_threshold = int(self.max_experiences * 0.75)
        if self.gold_confidence_threshold < 0 or self.gold_confidence_threshold > 1:
            raise ValueError("gold_confidence_threshold must be between 0 and 1")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetentionConfig":
        """Create config from dictionary (e.g., from YAML config)."""
        # Extract retention section
        retention_data = data.get("experience_learning", {}).get("retention", {})
        
        # Merge with defaults
        config = cls()
        
        # Map fields
        for field_name in cls.__dataclass_fields__:
            if field_name in retention_data:
                setattr(config, field_name, retention_data[field_name])
        
        return config
    
    @classmethod
    def from_env(cls) -> "RetentionConfig":
        """Create config from environment variables."""
        config = cls()
        
        env_map = {
            "EXPERIENCE_MAX_EXPERIENCES": "max_experiences",
            "EXPERIENCE_MAX_FILE_SIZE_MB": "max_file_size_mb",
            "EXPERIENCE_MAX_AGE_DAYS": "max_age_days",
            "EXPERIENCE_ARCHIVE_THRESHOLD": "archive_threshold",
            "EXPERIENCE_COMPRESSION_DAYS": "compression_days",
            "EXPERIENCE_GOLD_CONFIDENCE": "gold_confidence_threshold",
        }
        
        for env_var, field_name in env_map.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Parse numeric values
                    if field_name in ["max_experiences", "max_file_size_mb", 
                                     "max_age_days", "archive_threshold", 
                                     "compression_days", "min_occurrences_for_pattern"]:
                        setattr(config, field_name, int(value))
                    elif field_name in ["gold_confidence_threshold"]:
                        setattr(config, field_name, float(value))
                    elif field_name in ["keep_failed", "keep_with_lessons", 
                                       "background_enabled", "compress_archives"]:
                        setattr(config, field_name, value.lower() in ("true", "1", "yes"))
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse {env_var}={value}, using default")
        
        return config


class RetentionPolicy:
    """Policy engine for experience retention classification and decisions."""
    
    # Classification labels
    GOLD = "GOLD"      # Never delete
    SILVER = "SILVER"  # Archive if needed, but keep accessible
    BRONZE = "BRONZE"  # Delete first when cleanup needed
    
    def __init__(self, config: RetentionConfig):
        """Initialize retention policy with configuration."""
        self.config = config
        self._pattern_cache: Dict[str, int] = {}  # For detecting repeated patterns
        
    @staticmethod
    def _is_runtime_learning_experience(
        experience: Dict[str, Any],
    ) -> bool:
        metadata = experience.get("metadata") or {}

        return (
            metadata.get("learning_source") == "turn_finalizer"
            or "runtime_learning" in {
                str(tag).lower()
                for tag in (experience.get("tags") or [])
            }
        )

    @staticmethod
    def _runtime_verification_outcome(
        experience: Dict[str, Any],
    ) -> str:
        metadata = experience.get("metadata") or {}

        return str(
            metadata.get("verification_outcome") or ""
        ).upper()

    @staticmethod
    def _is_synthetic_runtime_fixture(
        experience: Dict[str, Any],
    ) -> bool:
        metadata = experience.get("metadata") or {}

        problem = str(
            experience.get("problem") or ""
        ).strip().lower()

        turn_id = str(
            metadata.get("turn_id") or ""
        ).lower()

        return (
            problem in {
                "test",
                "edit",
                "edit and verify",
                "edit changed.py",
            }
            or turn_id.startswith("turn-pm")
            or turn_id.startswith("verify-budget-test:")
        )

    def _classify_runtime_learning(
        self,
        experience: Dict[str, Any],
    ) -> str:
        """Classify runtime learning using authoritative verification truth."""
        verification = self._runtime_verification_outcome(
            experience
        )

        result = str(
            experience.get("result") or ""
        ).lower()

        confidence = float(
            experience.get("confidence") or 0.0
        )

        if self._is_synthetic_runtime_fixture(experience):
            return self.BRONZE

        if verification == "UNVERIFIED" or result == "partial":
            return self.BRONZE

        if (
            verification == "FAILED"
            or result in {"failed", "failure"}
        ):
            return self.SILVER

        if (
            verification == "VERIFIED"
            and result in {"success", "successful"}
        ):
            if confidence >= self.config.gold_confidence_threshold:
                return self.GOLD

            return self.SILVER

        return self.BRONZE

    def classify(self, experience: Dict[str, Any]) -> str:
        """Classify an experience as GOLD, SILVER, or BRONZE."""

        if self._is_runtime_learning_experience(experience):
            return self._classify_runtime_learning(experience)

        confidence = experience.get("confidence", 0.0)
        tags = experience.get("tags", [])

        if self.is_gold(experience):
            return self.GOLD

        if (
            confidence >= 0.5
            and confidence < self.config.gold_confidence_threshold
        ):
            return self.SILVER

        age_days = self._get_age_days(experience)

        if age_days is not None and age_days < 30:
            return self.SILVER

        useful_tags = {
            "important",
            "learning",
            "pattern",
            "repeated",
        }

        if any(
            useful_tag in str(tag).lower()
            for tag in tags
            for useful_tag in useful_tags
        ):
            return self.SILVER

        return self.BRONZE

    def is_gold(self, experience: Dict[str, Any]) -> bool:
        """Check if an experience is GOLD (never delete)."""

        if self._is_runtime_learning_experience(experience):
            return (
                self._classify_runtime_learning(experience)
                == self.GOLD
            )
        confidence = experience.get("confidence", 0.0)
        result = experience.get("result", "unknown")
        lessons = experience.get("lessons_learned", [])
        
        # Gold conditions
        if confidence >= self.config.gold_confidence_threshold:
            return True
        
        if self.config.keep_failed and result == "failed":
            return True
        
        if self.config.keep_with_lessons and lessons and len(lessons) > 0:
            return True
        
        # Repeated patterns (detected via pattern cache)
        pattern_key = self._get_pattern_key(experience)
        if pattern_key and self._get_pattern_count(pattern_key) >= self.config.min_occurrences_for_pattern:
            return True
        
        return False
    
    def classify_with_feedback(
        self,
        experience: Dict[str, Any],
        feedback_records: List[Dict[str, Any]],
    ) -> str:
        """Classify with repeated verified reuse evidence.

        Runtime experiences may become GOLD only after repeated successful
        feedback for the exact experience ID. Synthetic fixtures never promote.

        This method is intentionally pure: callers provide feedback rows rather
        than the retention layer reading runtime storage itself.
        """
        base = self.classify(experience)

        if not self._is_runtime_learning_experience(experience):
            return base

        if self._is_synthetic_runtime_fixture(experience):
            return self.BRONZE

        verification = self._runtime_verification_outcome(
            experience
        )

        result = str(
            experience.get("result") or ""
        ).lower()

        confidence = float(
            experience.get("confidence") or 0.0
        )

        # Only authoritative verified successes are promotable.
        if (
            verification != "VERIFIED"
            or result not in {"success", "successful"}
        ):
            return base

        experience_id = str(
            experience.get("id") or ""
        )

        if not experience_id:
            return self.SILVER

        successful_reuses = 0
        failed_reuses = 0

        for row in feedback_records or []:
            if not isinstance(row, dict):
                continue

            if str(row.get("experience_id") or "") != experience_id:
                continue

            if not bool(row.get("recommendation_used")):
                continue

            after_result = str(
                row.get("after_result") or ""
            ).lower()

            success = bool(row.get("success"))

            if success and after_result == "success":
                successful_reuses += 1
            elif after_result in {"failure", "failed"} or not success:
                failed_reuses += 1

        # Any observed failed reuse blocks automatic GOLD promotion.
        if failed_reuses:
            return self.SILVER

        required_successes = max(
            1,
            int(self.config.min_occurrences_for_pattern),
        )

        if (
            confidence >= self.config.gold_confidence_threshold
            and successful_reuses >= required_successes
        ):
            return self.GOLD

        # A verified runtime success is valuable, but not durable GOLD until
        # repeated reuse evidence exists.
        return self.SILVER

    def classify_with_feedback_history(
        self,
        experience: Dict[str, Any],
        feedback_records: List[Dict[str, Any]],
    ) -> str:
        """Classify using recent reuse history with recovery support.

        Older failures do not permanently poison a verified experience.
        Recent failures demote it, while a sufficiently long fresh run of
        successful reuse can promote it again.
        """
        base = self.classify(experience)

        if not self._is_runtime_learning_experience(experience):
            return base

        if self._is_synthetic_runtime_fixture(experience):
            return self.BRONZE

        verification = self._runtime_verification_outcome(
            experience
        )

        result = str(
            experience.get("result") or ""
        ).lower()

        confidence = float(
            experience.get("confidence") or 0.0
        )

        # Only verified successful runtime experiences participate in
        # promotion/recovery.
        if (
            verification != "VERIFIED"
            or result not in {"success", "successful"}
        ):
            return base

        experience_id = str(
            experience.get("id") or ""
        )

        if not experience_id:
            return self.SILVER

        relevant = [
            row
            for row in (feedback_records or [])
            if isinstance(row, dict)
            and str(row.get("experience_id") or "") == experience_id
            and bool(row.get("recommendation_used"))
        ]

        if not relevant:
            return self.SILVER

        latest = relevant[-1]

        latest_after = str(
            latest.get("after_result") or ""
        ).lower()

        latest_success = bool(
            latest.get("success")
        )

        # Immediate demotion on the newest observed failure.
        if (
            not latest_success
            or latest_after in {"failure", "failed"}
        ):
            return self.SILVER

        recent = relevant[-5:]

        recent_failures = sum(
            1
            for row in recent
            if (
                not bool(row.get("success"))
                or str(
                    row.get("after_result") or ""
                ).lower() in {"failure", "failed"}
            )
        )

        # Repeated instability in the recent window blocks GOLD.
        if recent_failures >= 2:
            return self.SILVER

        required_successes = max(
            1,
            int(self.config.min_occurrences_for_pattern),
        )

        # Count consecutive successful reuses from newest backwards.
        consecutive_successes = 0

        for row in reversed(relevant):
            after = str(
                row.get("after_result") or ""
            ).lower()

            if (
                bool(row.get("success"))
                and after == "success"
            ):
                consecutive_successes += 1
            else:
                break

        if (
            confidence >= self.config.gold_confidence_threshold
            and consecutive_successes >= required_successes
        ):
            return self.GOLD

        return self.SILVER


    def should_archive(self, experience: Dict[str, Any]) -> bool:
        """Determine if an experience should be archived."""
        # GOLD experiences are never archived
        if self.is_gold(experience):
            return False
        
        # Archive SILVER experiences that are old
        if self.classify(experience) == self.SILVER:
            age_days = self._get_age_days(experience)
            if age_days is not None and age_days > self.config.compression_days:
                return True
        
        # Archive BRONZE experiences (always archive before deletion)
        if self.classify(experience) == self.BRONZE:
            return True
        
        return False
    
    def should_delete(self, experience: Dict[str, Any], current_count: int) -> bool:
        """
        Determine if an experience should be deleted to enforce limits.
        
        Args:
            experience: Experience record
            current_count: Total number of experiences currently stored
        
        Returns:
            True if experience should be deleted, False otherwise
        """
        # GOLD experiences are never deleted
        if self.is_gold(experience):
            return False
        
        # Only delete if we're over limits
        if current_count <= self.config.max_experiences:
            return False
        
        # BRONZE experiences are deleted first
        classification = self.classify(experience)
        if classification == self.BRONZE:
            # Delete the oldest BRONZE experiences first
            age_days = self._get_age_days(experience)
            if age_days is not None and age_days > self.config.max_age_days:
                return True
            # If we're significantly over limit, delete BRONZE regardless of age
            if current_count > self.config.max_experiences * 1.2:
                return True
        
        # SILVER experiences only if we're extremely over limit
        if classification == self.SILVER:
            if current_count > self.config.max_experiences * 2:
                return True
        
        return False
    
    def _get_age_days(self, experience: Dict[str, Any]) -> Optional[int]:
        """Calculate age of experience in days."""
        timestamp = experience.get("timestamp")
        if not timestamp:
            return None
        
        try:
            # Parse ISO timestamp
            if isinstance(timestamp, str):
                # Handle ISO format with optional microseconds
                if "." in timestamp:
                    dt = datetime.fromisoformat(timestamp)
                else:
                    dt = datetime.fromisoformat(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                return None
            
            age = (datetime.now() - dt).days
            return max(0, age)
        except (ValueError, TypeError):
            return None
    
    def _get_pattern_key(self, experience: Dict[str, Any]) -> Optional[str]:
        """Generate a pattern key for detecting repeated experiences."""
        # Use tags + problem + tool_id as pattern signature
        tags = sorted(experience.get("tags", []))
        problem = experience.get("problem", "")[:50]  # Truncate for pattern matching
        metadata = experience.get("metadata", {})
        tool_id = metadata.get("tool_id", "")
        
        if not tags and not problem:
            return None
        
        # Create a normalized signature
        key_parts = []
        if tags:
            key_parts.append("|".join(tags))
        if problem:
            key_parts.append(problem.lower().strip())
        if tool_id:
            key_parts.append(tool_id)
        
        return "::".join(key_parts) if key_parts else None
    
    def _get_pattern_count(self, pattern_key: str) -> int:
        """Get count of pattern occurrences from cache."""
        return self._pattern_cache.get(pattern_key, 0)
    
    def register_pattern(self, experience: Dict[str, Any]):
        """Register an experience pattern for future classification."""
        pattern_key = self._get_pattern_key(experience)
        if pattern_key:
            self._pattern_cache[pattern_key] = self._pattern_cache.get(pattern_key, 0) + 1
    
    def get_archivable_experiences(self, experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get all experiences that should be archived."""
        return [
            exp for exp in experiences
            if self.should_archive(exp)
        ]
    
    def get_deletable_experiences(self, experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get experiences that should be deleted to enforce limits."""
        current_count = len(experiences)
        
        # If we're under limits, nothing to delete
        if current_count <= self.config.max_experiences:
            return []
        
        # Sort by priority: BRONZE first (oldest first), then SILVER
        deletable = []
        for exp in experiences:
            if self.should_delete(exp, current_count):
                # Add metadata for sorting
                exp_with_meta = dict(exp)
                exp_with_meta["_classification"] = self.classify(exp)
                exp_with_meta["_age_days"] = self._get_age_days(exp) or 0
                deletable.append(exp_with_meta)
        
        # Sort: BRONZE before SILVER, older before newer
        deletable.sort(
            key=lambda e: (
                0 if e["_classification"] == self.BRONZE else 1,
                -e["_age_days"]  # Older first
            )
        )
        
        # Remove metadata fields
        for exp in deletable:
            exp.pop("_classification", None)
            exp.pop("_age_days", None)
        
        return deletable
    
    def compute_retention_summary(self, experiences: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute a summary of retention status for the current collection."""
        total = len(experiences)
        
        classification_counts = {
            self.GOLD: 0,
            self.SILVER: 0,
            self.BRONZE: 0,
        }
        
        deletable_count = 0
        archive_count = 0
        
        for exp in experiences:
            cls = self.classify(exp)
            classification_counts[cls] = classification_counts.get(cls, 0) + 1
            
            if self.should_delete(exp, total):
                deletable_count += 1
            if self.should_archive(exp):
                archive_count += 1
        
        return {
            "total_experiences": total,
            "max_experiences": self.config.max_experiences,
            "classifications": classification_counts,
            "deletable_count": deletable_count,
            "archive_count": archive_count,
            "over_limit": total > self.config.max_experiences,
            "over_limit_percent": (total / self.config.max_experiences * 100) if self.config.max_experiences > 0 else 0,
        }

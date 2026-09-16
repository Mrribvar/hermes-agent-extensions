"""Experience Feedback Loop for validating Experience Recall.

This module tracks whether the use of Experience Recall leads to improved outcomes
and provides evaluation metrics for the experience learning system.

Schema (additive, no Phase 14 modifications):
    feedback.json stores:
    - task_id: str
    - experience_id: str
    - recommendation_used: bool
    - before_result: str (success/failure)
    - after_result: str (success/failure)
    - success: bool
    - impact_score: float (0.0-1.0)
    - lessons: list
    - timestamp: datetime
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from hermes_constants import get_hermes_home
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class FeedbackRecord:
    """Record of feedback for an experience recommendation."""
    task_id: str
    experience_id: str
    recommendation_used: bool
    before_result: str  # "success" or "failure" or "unknown"
    after_result: str   # "success" or "failure"
    success: bool
    impact_score: float  # 0.0-1.0, positive = improvement
    lessons: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    recommendation: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class ExperienceFeedbackStore:
    """Storage for experience feedback records.

    Uses ~/.hermes/governance/feedback.json (additive, non-schema changing).
    """

    def __init__(self, data_dir: Optional[str] = None):
        """Initialize feedback store."""
        if data_dir is None:
            data_dir = str(
                get_hermes_home()
                / "governance"
            )

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.data_dir / "feedback.json"

        self._records: List[FeedbackRecord] = []
        self._load()

    def _load(self) -> None:
        """Load feedback from disk."""
        if not self.feedback_file.exists():
            self._records = []
            return

        try:
            with open(self.feedback_file, "r") as f:
                data = json.load(f)

            if isinstance(data, list):
                self._records = [
                    FeedbackRecord(**item) if isinstance(item, dict) else item
                    for item in data
                    if isinstance(item, (dict, FeedbackRecord))
                ]
            else:
                self._records = []
        except (json.JSONDecodeError, FileNotFoundError):
            self._records = []

    def _save(self) -> None:
        """Save feedback to disk."""
        data = [record.to_dict() for record in self._records]

        with open(self.feedback_file, "w") as f:
            json.dump(data, f, indent=2)

    def record(self, feedback: FeedbackRecord) -> None:
        """Record a feedback entry."""
        self._records.append(feedback)
        self._save()
        logger.info(f"Feedback recorded for task {feedback.task_id}")

    def get_all(self) -> List[FeedbackRecord]:
        """Get all feedback records."""
        return self._records

    def get_by_experience(self, experience_id: str) -> List[FeedbackRecord]:
        """Get feedback records for a specific experience."""
        return [r for r in self._records if r.experience_id == experience_id]

    def get_by_task(self, task_id: str) -> Optional[FeedbackRecord]:
        """Get feedback for a specific task."""
        matches = [r for r in self._records if r.task_id == task_id]
        return matches[-1] if matches else None

    def has_task_experience(
        self,
        task_id: str,
        experience_id: str,
    ) -> bool:
        """Return whether this exact turn/experience feedback already exists."""
        return any(
            r.task_id == task_id
            and r.experience_id == experience_id
            for r in self._records
        )

    def get_recent(self, limit: int = 10) -> List[FeedbackRecord]:
        """Get most recent feedback records."""
        sorted_records = sorted(
            self._records,
            key=lambda x: x.timestamp,
            reverse=True
        )
        return sorted_records[:limit]

    def get_successful_feedback(self) -> List[FeedbackRecord]:
        """Get feedback where recommendation led to success."""
        return [r for r in self._records if r.success and r.recommendation_used]

    def get_improved_outcomes(self) -> List[FeedbackRecord]:
        """Get feedback where outcome improved."""
        return [
            r for r in self._records
            if r.impact_score > 0 and r.recommendation_used
        ]

    def count(self) -> int:
        """Get total number of feedback records."""
        return len(self._records)

    def get_stats(self) -> dict:
        """Get statistics about feedback."""
        if not self._records:
            return {
                "total": 0,
                "recommendation_used": 0,
                "success_rate": 0.0,
                "avg_impact_score": 0.0,
                "improved": 0
            }

        used = sum(1 for r in self._records if r.recommendation_used)
        successful = sum(1 for r in self._records if r.success)
        improved = sum(1 for r in self._records if r.impact_score > 0)

        return {
            "total": len(self._records),
            "recommendation_used": used,
            "success_rate": successful / len(self._records),
            "avg_impact_score": sum(r.impact_score for r in self._records) / len(self._records),
            "improved": improved
        }


class ExperienceFeedbackEvaluator:
    """Evaluates the effectiveness of Experience Recall recommendations."""

    def __init__(self):
        self.store = ExperienceFeedbackStore()

    def record_feedback(
        self,
        task_id: str,
        experience_id: str,
        recommendation_used: bool,
        before_result: str,
        after_result: str,
        recommendation: Optional[str] = None,
        lessons: Optional[List[str]] = None
    ) -> FeedbackRecord:
        """Record feedback for a task execution.

        Calculates impact_score based on before/after comparison.
        """
        # Calculate impact score
        impact_score = self.calculate_improvement(before_result, after_result)

        success = after_result == "success"

        record = FeedbackRecord(
            task_id=task_id,
            experience_id=experience_id,
            recommendation_used=recommendation_used,
            before_result=before_result,
            after_result=after_result,
            success=success,
            impact_score=impact_score,
            lessons=lessons or [],
            recommendation=recommendation
        )

        self.store.record(record)
        return record

    def calculate_improvement(self, before: str, after: str) -> float:
        """Calculate improvement score from before to after result.

        Returns:
            float: 0.0-1.0 where positive means improvement
            - 1.0: failure → success
            - 0.5: success → success (maintained)
            - 0.0: failure → failure (no improvement)
            - -0.5: success → failure (worse)
            - -1.0: failure → failure (same)
        """
        # Normalize inputs
        before = before.lower() if before else "unknown"
        after = after.lower() if after else "unknown"

        # Define states
        SUCCESS = "success"
        FAILURE = "failure"
        UNKNOWN = "unknown"

        # Score matrix: before -> after -> impact
        if before == SUCCESS and after == SUCCESS:
            return 0.5
        elif before == SUCCESS and after == FAILURE:
            return -0.5
        elif before == FAILURE and after == SUCCESS:
            return 1.0
        elif before == FAILURE and after == FAILURE:
            return 0.0
        elif before == UNKNOWN and after == SUCCESS:
            return 0.5
        elif before == UNKNOWN and after == FAILURE:
            return -0.3
        else:
            return 0.0

    @staticmethod
    def evolve_confidence(
        current_confidence: float,
        *,
        recommendation_used: bool,
        success: bool,
        impact_score: float,
    ) -> float:
        """Return a conservative bounded confidence update.

        Feedback only affects confidence when the recommendation was actually
        used. Successful outcomes strengthen confidence gradually; unsuccessful
        outcomes weaken it more quickly.
        """
        current = max(0.0, min(1.0, float(current_confidence)))

        if not recommendation_used:
            return current

        impact = max(-1.0, min(1.0, float(impact_score)))

        if success:
            delta = 0.05 + (max(0.0, impact) * 0.05)
        else:
            delta = -(0.10 + (abs(min(0.0, impact)) * 0.10))

        return round(
            max(0.0, min(1.0, current + delta)),
            4,
        )

    def get_best_performing_experiences(self, min_feedback: int = 3) -> List[Dict[str, Any]]:
        """Get experiences with highest success rate from feedback."""
        # Group by experience_id
        exp_feedback: Dict[str, List[FeedbackRecord]] = {}
        for record in self.store.get_all():
            if record.experience_id not in exp_feedback:
                exp_feedback[record.experience_id] = []
            exp_feedback[record.experience_id].append(record)

        # Filter by min feedback count
        results = []
        for exp_id, records in exp_feedback.items():
            if len(records) < min_feedback:
                continue

            total = len(records)
            successful = sum(1 for r in records if r.success and r.recommendation_used)
            success_rate = successful / total
            avg_impact = sum(r.impact_score for r in records) / total

            results.append({
                "experience_id": exp_id,
                "success_rate": success_rate,
                "total_feedback": total,
                "avg_impact_score": avg_impact,
                "successful_count": successful
            })

        # Sort by success rate descending
        results.sort(key=lambda x: x["success_rate"], reverse=True)
        return results

    def compare_with_previous(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Compare current execution with previous for the same task."""
        previous = self.store.get_by_task(task_id)
        if not previous:
            return None

        return {
            "task_id": task_id,
            "previous_result": previous.after_result,
            "previous_impact": previous.impact_score,
            "previous_success": previous.success,
            "recommendation_used": previous.recommendation_used
        }

    def get_improvement_summary(self) -> dict:
        """Get summary of improvement metrics."""
        stats = self.store.get_stats()

        improved_records = [
            r for r in self.store.get_all()
            if r.impact_score > 0 and r.recommendation_used
        ]

        return {
            "total_feedback": stats["total"],
            "recommendation_used": stats["recommendation_used"],
            "success_rate": stats["success_rate"],
            "avg_impact_score": stats["avg_impact_score"],
            "improved_count": len(improved_records),
            "improvement_rate": len(improved_records) / max(1, stats["total"])
        }

from pathlib import Path
from hermes_constants import get_hermes_home
"""
Experience Memory - Hermes Phase 8

Enhanced experience storage with:
- Problem
- Analysis
- Solution
- Result
- Lessons Learned
- Confidence
- Future Recommendation
"""

import json
import os
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExperienceRecord:
    """A single experience record from a completed task"""
    id: str
    timestamp: str
    problem: str
    analysis: str
    solution: str
    result: str  # successful, partial, failed
    lessons_learned: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 - 1.0
    future_recommendation: str = ""
    related_decision_id: str = ""
    related_project: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "problem": self.problem,
            "analysis": self.analysis,
            "solution": self.solution,
            "result": self.result,
            "lessons_learned": self.lessons_learned,
            "confidence": self.confidence,
            "future_recommendation": self.future_recommendation,
            "related_decision_id": self.related_decision_id,
            "related_project": self.related_project,
            "tags": self.tags,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperienceRecord":
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            problem=data.get("problem", ""),
            analysis=data.get("analysis", ""),
            solution=data.get("solution", ""),
            result=data.get("result", "pending"),
            lessons_learned=data.get("lessons_learned", []),
            confidence=data.get("confidence", 0.0),
            future_recommendation=data.get("future_recommendation", ""),
            related_decision_id=data.get("related_decision_id", ""),
            related_project=data.get("related_project", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )


class ExperienceMemory:
    """
    Persistent experience memory for Hermes.

    Stores completed tasks as experiences with full context:
    - What was the problem
    - How was it analyzed
    - What solution was applied
    - What was the result
    - What lessons were learned
    - How confident are we in this experience
    - What should we do differently next time

    Storage: ~/.hermes/governance/experiences.json
    """

    DEFAULT_PATH = os.path.expanduser("~/.hermes/governance/experiences.json")

    def __init__(self, storage_path: str = None):
        self.storage_path = (
            storage_path
            or str(
                get_hermes_home()
                / "governance"
                / "experiences.json"
            )
        )
        self.experiences: Dict[str, ExperienceRecord] = {}
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def _load(self) -> None:
        """Load experiences from storage file"""
        if not os.path.exists(self.storage_path):
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    record = ExperienceRecord.from_dict(item)
                    self.experiences[record.id] = record
            elif isinstance(data, dict):
                for key, item in data.items():
                    record = ExperienceRecord.from_dict(item)
                    self.experiences[record.id] = record
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load experience memory: {e}")

    def _save(self) -> None:
        """Atomically save experiences to the storage file."""
        import os
        import tempfile

        self._ensure_storage_dir()

        data = [
            rec.to_dict()
            for rec in self.experiences.values()
        ]

        storage_path = Path(self.storage_path)
        storage_dir = storage_path.parent

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{storage_path.name}.",
            suffix=".tmp",
            dir=str(storage_dir),
        )

        tmp_path = Path(tmp_name)

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    data,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )

                handle.flush()
                os.fsync(handle.fileno())

            # Validate serialized content before publication.
            loaded = json.loads(
                tmp_path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(loaded, list):
                raise ValueError(
                    "experience save validation failed"
                )

            tmp_path.replace(
                storage_path
            )

        finally:
            if tmp_path.exists():
                tmp_path.unlink(
                    missing_ok=True
                )

    def record(self,
               problem: str,
               analysis: str,
               solution: str,
               result: str = "successful",
               lessons_learned: List[str] = None,
               confidence: float = 0.0,
               future_recommendation: str = "",
               related_decision_id: str = "",
               related_project: str = "",
               tags: List[str] = None,
               metadata: Dict[str, Any] = None,
               record_id: str = None) -> ExperienceRecord:
        """
        Record a completed task as an experience.

        Args:
            problem: What was the problem
            analysis: How was it analyzed
            solution: What solution was applied
            result: successful, partial, or failed
            lessons_learned: List of lessons learned
            confidence: Confidence level 0.0-1.0
            future_recommendation: What to do differently next time
            related_decision_id: Link to a governance decision
            related_project: Which project this relates to
            tags: Tags for categorization
            metadata: Additional context

        Returns:
            The created ExperienceRecord
        """
        if record_id:
            existing = self.experiences.get(record_id)
            if existing is not None:
                return existing
        else:
            record_id = (
                f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                f"{uuid.uuid4().hex[:6]}"
            )

        record = ExperienceRecord(
            id=record_id,
            timestamp=datetime.now().isoformat(),
            problem=problem,
            analysis=analysis,
            solution=solution,
            result=result,
            lessons_learned=lessons_learned or [],
            confidence=confidence,
            future_recommendation=future_recommendation,
            related_decision_id=related_decision_id,
            related_project=related_project,
            tags=tags or [],
            metadata=metadata or {}
        )

        self.experiences[record_id] = record
        self._save()
        return record

    def get(self, record_id: str) -> Optional[ExperienceRecord]:
        """Get an experience by ID"""
        return self.experiences.get(record_id)

    def update_confidence(
        self,
        record_id: str,
        confidence: float,
    ) -> Optional[ExperienceRecord]:
        """Persist a bounded confidence update for an existing experience."""
        record = self.experiences.get(record_id)

        if record is None:
            return None

        value = max(0.0, min(1.0, float(confidence)))

        record.confidence = value
        self._save()

        return record

    def remove(
        self,
        record_id: str,
    ) -> Optional[ExperienceRecord]:
        """Atomically remove one explicitly identified experience.

        The in-memory record is restored if persistence fails.
        """
        record_id = str(record_id)

        record = self.experiences.get(
            record_id
        )

        if record is None:
            return None

        self.experiences.pop(
            record_id,
            None,
        )

        try:
            self._save()
        except Exception:
            self.experiences[
                record_id
            ] = record
            raise

        return record

    def get_all(self) -> List[ExperienceRecord]:
        """Get all experiences"""
        return list(self.experiences.values())

    def get_by_result(self, result: str) -> List[ExperienceRecord]:
        """Filter experiences by result"""
        return [e for e in self.experiences.values() if e.result == result]

    def get_by_project(self, project: str) -> List[ExperienceRecord]:
        """Filter experiences by project"""
        return [e for e in self.experiences.values() if e.related_project == project]

    def get_by_tag(self, tag: str) -> List[ExperienceRecord]:
        """Filter experiences by tag"""
        tag_lower = tag.lower()
        return [e for e in self.experiences.values() if tag_lower in [t.lower() for t in e.tags]]

    def get_recent(self, limit: int = 10) -> List[ExperienceRecord]:
        """Get most recent experiences"""
        sorted_exps = sorted(
            self.experiences.values(),
            key=lambda e: e.timestamp,
            reverse=True
        )
        return sorted_exps[:limit]

    def get_lessons(self) -> List[str]:
        """Get all unique lessons learned across all experiences"""
        lessons = []
        for exp in self.experiences.values():
            for lesson in exp.lessons_learned:
                if lesson not in lessons:
                    lessons.append(lesson)
        return lessons

    def get_recommendations(self) -> List[str]:
        """Get all future recommendations from experiences"""
        recs = []
        for exp in self.experiences.values():
            if exp.future_recommendation and exp.future_recommendation not in recs:
                recs.append(exp.future_recommendation)
        return recs

    def get_stats(self) -> Dict[str, Any]:
        """Get experience statistics"""
        total = len(self.experiences)
        by_result = {}
        by_project = {}
        avg_confidence = 0.0

        if total > 0:
            conf_sum = sum(e.confidence for e in self.experiences.values())
            avg_confidence = round(conf_sum / total, 2)

        for exp in self.experiences.values():
            r = exp.result
            by_result[r] = by_result.get(r, 0) + 1

            p = exp.related_project or "general"
            by_project[p] = by_project.get(p, 0) + 1

        return {
            "total_experiences": total,
            "by_result": by_result,
            "by_project": by_project,
            "average_confidence": avg_confidence,
            "total_lessons": len(self.get_lessons()),
            "total_recommendations": len(self.get_recommendations())
        }

    def find_similar(self, problem_text: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Find similar past experiences based on keyword overlap.

        Uses simple word overlap for matching.
        """
        problem_words = set(problem_text.lower().split())
        results = []

        for exp in self.experiences.values():
            exp_words = set((exp.problem + " " + exp.analysis + " " + exp.solution).lower().split())
            overlap = len(problem_words & exp_words)
            total = len(problem_words | exp_words)
            similarity = overlap / total if total > 0 else 0

            if similarity >= threshold:
                results.append({
                    "experience_id": exp.id,
                    "problem": exp.problem,
                    "solution": exp.solution,
                    "result": exp.result,
                    "confidence": exp.confidence,
                    "similarity": round(similarity, 2)
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

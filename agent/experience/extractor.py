# Phase 14.0 — Extractor: builds ExperienceRecord from execution data.
#
# Uses existing governance.experience_memory.ExperienceRecord and governance.experience_memory.ExperienceMemory.
# Idempotent: each execution_id yields at most one ExperienceRecord.
from __future__ import annotations

import uuid
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.experience.listener import ExecutionRecordProxy
from agent.experience.evaluator import EvaluationResult

# Import existing governance memory; we will NOT modify it, just read/write via its public API.
try:
    from governance.experience_memory import ExperienceMemory, ExperienceRecord
except Exception:
    # fallback; the module must exist.
    raise


class ExperienceExtractor:
    """Builds ExperienceRecord from execution result."""

    def __init__(self, memory: Optional[ExperienceMemory] = None):
        self._memory = memory or ExperienceMemory()
        self._lock = threading.RLock()

    def extract_and_store(
        self,
        eval_result: EvaluationResult,
        proxy: ExecutionRecordProxy,
        problem_text: str,
        analysis: str = "",
        solution: str = "",
        related_decision_id: str = "",
        related_project: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExperienceRecord:
        """
        Create ExperienceRecord from the evaluation result and execution details.
        Store via existing ExperienceMemory.record().
        Idempotent by execution_id -> use execution_id as experience id.
        """
        # Ensure each execution creates only one experience (idempotent).
        # Use execution_id from proxy as experience id (consistent with Requirement 5).
        experience_id = f"exp_{proxy.execution_id}"
        existing = self._memory.get(experience_id)
        if existing:
            return existing

        # Determine final result string (same as in ExperienceMemory's record). We need to map eval_result.outcome to record.result.
        # record.result expects: "successful", "partial", "failed". Use EvaluationResult.outcome (same).
        # Build problem from proxy and problem_text (we could combine proxy.tool_id etc.)
        # For simplicity, we set problem = problem_text if provided, else proxy.tool_id or "execution".
        # But spec says "problem_text" is the goal or what the execution attempted.
        final_problem = problem_text or proxy.tool_id or "execution"
        # If analysis is not provided, derive from cause_hint and error_message.
        analysis_text = analysis or eval_result.cause_hint
        # Solution: derive from evaluation if not provided.
        solution_text = solution or ("tool: " + proxy.tool_id) if proxy.tool_id else ""
        # Lessons: combine lesson_candidates from evaluation.
        final_lessons = eval_result.lesson_candidates
        # Confidence: default to 0.5; can be updated later via updater.
        confidence = 0.5
        # Future recommendation: derived from eval_result.cause_hint or empty.
        future_rec = f"Avoid {eval_result.cause_hint}." if eval_result.cause_hint else ""
        # Use execution_id as record.id (ExperienceRecord expects id, we set).
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        # Compose metadata: add execution_id for linking.
        meta = metadata or {}
        meta["execution_id"] = proxy.execution_id
        meta["tool_id"] = proxy.tool_id
        meta["project_id"] = proxy.project_id
        meta["original_status"] = proxy.result_status

        record = ExperienceRecord(
            id=experience_id,
            timestamp=timestamp,
            problem=final_problem,
            analysis=analysis_text,
            solution=solution_text,
            result=eval_result.outcome,  # maps "success"/"partial"/"failed"
            lessons_learned=final_lessons,
            confidence=confidence,
            future_recommendation=future_rec,
            related_decision_id=related_decision_id,
            related_project=related_project,
            tags=tags or [],
            metadata=meta,
        )
        # Store via the existing memory (record method returns ExperienceRecord).
        self._memory.record(
            problem=record.problem,
            analysis=record.analysis,
            solution=record.solution,
            result=record.result,
            lessons_learned=record.lessons_learned,
            confidence=record.confidence,
            future_recommendation=record.future_recommendation,
            related_decision_id=record.related_decision_id,
            related_project=record.related_project,
            tags=record.tags,
            metadata=record.metadata,
            record_id=experience_id,
        )

        # Return the canonical persisted record.  This preserves the
        # execution_id -> experience_id identity contract and makes repeated
        # extraction of the same execution genuinely idempotent.
        persisted = self._memory.get(experience_id)
        return persisted or record

    # Optional: idempotent check by execution_id using experience_id.
    def get_by_execution(self, execution_id: str) -> Optional[ExperienceRecord]:
        experience_id = f"exp_{execution_id}"
        return self._memory.get(experience_id)


__all__ = ["ExperienceExtractor"]
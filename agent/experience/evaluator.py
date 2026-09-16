# Phase 14.0 — Evaluator: classifies ExecutionRecord into learning signal.
#
# Pure functions. No persistence, no I/O.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agent.experience.listener import ExecutionRecordProxy


@dataclass(frozen=True)
class EvaluationResult:
    """Normalized outcome classification."""
    outcome: str  # "success" | "partial" | "failed"
    cause_hint: str
    lesson_candidates: List[str]


class ExperienceEvaluator:
    """
    Classifies an execution result and extracts cause/lesson hints.
    Stateless, no I/O.
    """

    # Heuristic rules for cause hints (extendable)
    TOOL_ERROR_KEYWORDS = {
        "timeout": "tool_timeout",
        "permission": "permission_denied",
        "not found": "resource_missing",
        "connection": "network_error",
        "auth": "auth_failure",
        "validation": "input_validation_error",
    }

    def evaluate(self, record: ExecutionRecordProxy) -> EvaluationResult:
        """Map execution record to normalized outcome + hints."""
        status = record.result_status
        error = (record.error_message or "").lower()
        metadata = record.metadata or {}

        # Determine outcome
        if status == "success":
            outcome = "success"
            cause_hint = "none"
            lessons = ["successful_pattern_retain"]
        elif status == "cancelled":
            outcome = "partial"
            cause_hint = "cancelled_externally"
            lessons = ["avoid_cancellation_triggers"]
        else:  # failed
            outcome = "failed"
            cause_hint = self._classify_error(error)
            lessons = self._derive_lessons(cause_hint, error, metadata)

        # Always add context-specific lesson
        if record.tool_id:
            lessons.append(f"tool_{record.tool_id}_outcome_{outcome}")

        return EvaluationResult(
            outcome=outcome,
            cause_hint=cause_hint,
            lesson_candidates=lessons,
        )

    def _classify_error(self, error_text: str) -> str:
        for kw, hint in self.TOOL_ERROR_KEYWORDS.items():
            if kw in error_text:
                return hint
        return "unknown_error"

    def _derive_lessons(
        self, cause_hint: str, error: str, metadata: Dict[str, Any]
    ) -> List[str]:
        lessons = [f"cause:{cause_hint}"]
        if "timeout" in cause_hint:
            lessons.append("increase_timeout_or_async")
        if "permission" in cause_hint:
            lessons.append("check_permissions_before")
        if "resource_missing" in cause_hint:
            lessons.append("verify_resources_exist")
        if "network" in cause_hint:
            lessons.append("add_retry_with_backoff")
        if "validation" in cause_hint:
            lessons.append("validate_input_before_exec")
        if "auth" in cause_hint:
            lessons.append("refresh_credentials")
        # Deduplicate while preserving order
        seen = set()
        dedup = []
        for l in lessons:
            if l not in seen:
                seen.add(l)
                dedup.append(l)
        return dedup


__all__ = ["ExperienceEvaluator", "EvaluationResult"]
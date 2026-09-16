"""Experience recall over the existing ExperienceMemory/ExperienceIndex."""

from __future__ import annotations

from typing import Any, Dict

from governance.experience_memory import ExperienceMemory
from governance.experience_index import ExperienceIndex


def classify_experience_provenance(
    row: dict,
) -> str:
    """Classify an experience by provenance.

    Returns one of:
      - runtime_learning
      - synthetic_test
      - legacy
      - unknown

    This function is read-only and deterministic.
    """
    if not isinstance(row, dict):
        return "unknown"

    metadata = row.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    session_id = str(
        metadata.get("session_id") or ""
    ).lower()

    turn_id = str(
        metadata.get("turn_id") or ""
    ).lower()

    learning_source = str(
        metadata.get("learning_source") or ""
    ).lower()

    identity = " ".join(
        (
            session_id,
            turn_id,
        )
    )

    synthetic_markers = (
        "verify-budget-test",
        "pm2f-verification-test",
        "turn-pm",
        "fixture",
        "pytest-fixture",
        "probe",
    )

    if any(
        marker in identity
        for marker in synthetic_markers
    ):
        return "synthetic_test"

    if learning_source == "turn_finalizer":
        return "runtime_learning"

    if not metadata:
        return "legacy"

    return "unknown"


class ExperienceRecall:
    def __init__(self, memory: ExperienceMemory | None = None):
        self.memory = memory or ExperienceMemory()
        self.index = ExperienceIndex(self.memory)
        self.index.rebuild()

    @staticmethod
    def _normalize(exp: dict) -> dict:
        row = dict(exp)
        result = str(row.get("result") or "").lower()

        # Runtime memory historically stores "successful", while the
        # recall integration contract expects "success".
        if result == "successful":
            row["result"] = "success"
        elif result in {"failure", "failed"}:
            row["result"] = "failed"
        elif result == "partial":
            row["result"] = "partial"

        return row

    def ask(self, task: str, limit: int = 5) -> Dict[str, Any]:
        if not isinstance(task, str) or not task.strip():
            return {
                "has_experience": False,
                "experiences": [],
                "best_confidence": 0.0,
            }

        scored_rows = self.index.search_keywords_scored(
            task,
            limit=max(limit * 5, 20),
        )

        rows = []

        for row, relevance in scored_rows:
            normalized = self._normalize(
                row
            )

            provenance = (
                classify_experience_provenance(
                    normalized
                )
            )

            # Synthetic regression/test records must never become
            # production recommendations.
            if provenance == "synthetic_test":
                continue

            rows.append(
                (
                    normalized,
                    relevance,
                )
            )

        def rank(item):
            row, relevance = item
            metadata = row.get("metadata") or {}

            verification = str(
                metadata.get("verification_outcome") or ""
            ).upper()

            result = str(row.get("result") or "").lower()
            confidence = float(row.get("confidence") or 0.0)

            # Authoritative verification truth dominates model prose and
            # generic confidence.
            if verification == "VERIFIED" and result == "success":
                verification_rank = 4
            elif result == "success":
                verification_rank = 3
            elif verification == "UNVERIFIED" or result == "partial":
                verification_rank = 2
            elif verification == "FAILED" or result == "failed":
                verification_rank = 1
            else:
                verification_rank = 0

            provenance = classify_experience_provenance(
                row
            )

            runtime_rank = (
                0
                if provenance == "synthetic_test"
                else 1
            )

            # Relevance must participate explicitly in ranking.
            #
            # A VERIFIED experience is trustworthy, but an unrelated VERIFIED
            # fixture must not beat a strongly matching runtime experience.
            #
            # Order:
            #   1. keyword relevance
            #   2. authoritative verification/result quality
            #   3. genuine runtime over synthetic fixtures
            #   4. confidence
            #   5. recency
            # Truth bounds relevance:
            # an UNVERIFIED/PARTIAL experience must never outrank a
            # VERIFIED/SUCCESS experience merely because it shares one more
            # keyword. Relevance ranks candidates inside the same truth tier.
            return (
                verification_rank,
                int(relevance),
                runtime_rank,
                confidence,
                str(row.get("timestamp") or ""),
            )

        rows.sort(key=rank, reverse=True)
        rows = rows[:limit]

        selected = [row for row, _relevance in rows]

        return {
            "has_experience": bool(selected),
            "experiences": selected,
            "best_confidence": (
                float(selected[0].get("confidence") or 0.0)
                if selected else 0.0
            ),
        }

    def get_stats(self) -> dict:
        rows = self.memory.get_all()
        return {
            "total_experiences": len(rows),
        }


__all__ = [
    "ExperienceRecall",
    "classify_experience_provenance",
]

"""First-party runtime learning + verification observer.

Verification truth comes from runtime evidence, never model prose.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_HANDLED = {
    "post_tool_call",
    "on_session_end",
}


def handles_hook(hook_name: str) -> bool:
    return hook_name in _HANDLED


def _stable_experience_id(
    *,
    session_id: Any,
    turn_id: Any,
) -> str:
    """Return one deterministic experience id per Hermes turn."""
    raw = f"{session_id or ''}:{turn_id or ''}"

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]

    return f"exp_turn_{digest}"


def _learning_classification(
    verification_outcome: str,
) -> tuple[str, float, list[str]] | None:
    """Map authoritative verification truth into learning semantics."""

    outcome = str(
        verification_outcome
        or "NOT_APPLICABLE"
    ).upper()

    if outcome == "VERIFIED":
        return (
            "successful",
            0.90,
            [
                "verification_passed",
                "verified_success_pattern",
            ],
        )

    if outcome == "FAILED":
        return (
            "failed",
            0.90,
            [
                "verification_failed",
                "avoid_failed_pattern",
            ],
        )

    if outcome == "UNVERIFIED":
        return (
            "partial",
            0.25,
            [
                "verification_missing",
                "do_not_promote_without_verification",
            ],
        )

    # Ordinary conversational turns have no state-change learning value.
    return None


def _persist_turn_experience(
    *,
    verification_outcome: str,
    kwargs: dict[str, Any],
) -> None:
    """Persist one truth-bounded ExperienceRecord for this turn.

    This is the Experience producer side of lifecycle learning.
    Feedback evolution for recalled experiences is handled separately.
    """
    classification = _learning_classification(
        verification_outcome
    )

    if classification is None:
        logger.debug(
            "learning producer skipped: verification=%s",
            verification_outcome,
        )
        return

    result, confidence, lessons = classification

    session_id = kwargs.get("session_id") or ""
    turn_id = kwargs.get("turn_id") or ""

    if not turn_id:
        logger.warning(
            "learning producer skipped: missing turn identity "
            "session=%s verification=%s",
            session_id,
            verification_outcome,
        )
        return

    try:
        from governance.experience_memory import (
            ExperienceMemory,
        )

        memory = ExperienceMemory()

        record_id = _stable_experience_id(
            session_id=session_id,
            turn_id=turn_id,
        )

        record = memory.record(
            problem=str(
                kwargs.get("user_message")
                or "Hermes state-changing turn"
            ),
            analysis=(
                "Authoritative Hermes verification outcome: "
                f"{verification_outcome}"
            ),
            solution=str(
                kwargs.get("assistant_response")
                or ""
            ),
            result=result,
            lessons_learned=lessons,
            confidence=confidence,
            future_recommendation=(
                "Reuse only when verification evidence supports "
                "the same outcome."
            ),
            tags=[
                "runtime_learning",
                "verification",
                verification_outcome.lower(),
            ],
            metadata={
                "learning_source": "turn_finalizer",
                "verification_outcome":
                    verification_outcome,
                "verification_status":
                    kwargs.get("verification_status"),
                "session_id":
                    session_id,
                "turn_id":
                    turn_id,
                "task_id":
                    kwargs.get("task_id"),
                "completed":
                    bool(kwargs.get("completed")),
                "failed":
                    bool(kwargs.get("failed")),
                "interrupted":
                    bool(kwargs.get("interrupted")),
                "turn_exit_reason":
                    kwargs.get("turn_exit_reason"),
                "model":
                    kwargs.get("model"),
                "platform":
                    kwargs.get("platform"),
            },
            record_id=record_id,
        )

        logger.info(
            "learning experience persisted: "
            "turn=%s experience=%s result=%s "
            "confidence=%.2f verification=%s",
            turn_id,
            record.id,
            record.result,
            record.confidence,
            verification_outcome,
        )

    except Exception:
        logger.warning(
            "runtime learning experience persistence failed",
            exc_info=True,
        )


def _observe_terminal_result(**kwargs: Any) -> None:
    if kwargs.get("tool_name") != "terminal":
        return

    args = kwargs.get("args") or {}
    if not isinstance(args, dict):
        return

    # Background commands have not produced terminal verification evidence yet.
    if args.get("background"):
        return

    command = args.get("command")
    if not isinstance(command, str) or not command.strip():
        return

    raw_result = kwargs.get("result")

    logger.info(
        "terminal observer raw payload: args=%r result_type=%s result=%r",
        args,
        type(raw_result).__name__,
        raw_result,
    )

    if isinstance(raw_result, dict):
        payload = raw_result
    elif isinstance(raw_result, str):
        try:
            payload = json.loads(raw_result)
        except Exception:
            return
    else:
        return

    exit_code = payload.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return

    # terminal_tool returns the authoritative cwd that actually executed
    # the foreground command. Prefer it over reconstructing session cwd.
    cwd = payload.get("cwd")

    if not isinstance(cwd, str) or not cwd.strip():
        try:
            from tools.terminal_tool import (
                _get_env_config,
                _resolve_command_cwd,
            )

            config = _get_env_config()
            default_cwd = str(
                (config or {}).get("cwd")
                or os.environ.get("TERMINAL_CWD")
                or os.getcwd()
            )

            cwd = _resolve_command_cwd(
                workdir=args.get("workdir"),
                default_cwd=default_cwd,
                session_key=str(kwargs.get("task_id") or ""),
            )
        except Exception:
            logger.debug(
                "verification evidence cwd resolution failed",
                exc_info=True,
            )
            return

    try:
        from agent.verification_evidence import record_terminal_result

        evidence = record_terminal_result(
            command=command,
            cwd=cwd,
            session_id=kwargs.get("session_id"),
            exit_code=exit_code,
            output=str(payload.get("output") or ""),
        )

        if evidence:
            logger.info(
                "verification evidence recorded: session=%s command=%s "
                "status=%s exit_code=%s",
                kwargs.get("session_id"),
                evidence.get("canonical_command"),
                evidence.get("status"),
                evidence.get("exit_code"),
            )
    except Exception:
        logger.warning(
            "terminal verification evidence recording failed",
            exc_info=True,
        )


def observe_lifecycle(hook_name: str, **kwargs: Any) -> None:
    if hook_name == "post_tool_call":
        _observe_terminal_result(**kwargs)
        return

    if hook_name != "on_session_end":
        return

    verification_outcome = str(
        kwargs.get("verification_outcome") or "NOT_APPLICABLE"
    ).upper()

    logger.info(
        "learning lifecycle: session=%s turn=%s completed=%s failed=%s "
        "verification=%s",
        kwargs.get("session_id"),
        kwargs.get("turn_id"),
        kwargs.get("completed"),
        kwargs.get("failed"),
        verification_outcome,
    )

    # First responsibility: turn -> ExperienceRecord.
    # This producer is independent from recalled-experience feedback.
    _persist_turn_experience(
        verification_outcome=verification_outcome,
        kwargs=kwargs,
    )

    # Second responsibility: evaluate a recalled experience when one was
    # actually selected and safely supplied to this turn.
    recalled_experience_id = kwargs.get("recalled_experience_id")
    recommendation_safe = bool(
        kwargs.get("recalled_recommendation_safe")
    )

    # Merely recalling an experience is not evidence that it worked.
    if not recalled_experience_id or not recommendation_safe:
        return

    # Confidence evolution is truth-bounded:
    # VERIFIED -> positive feedback
    # FAILED   -> negative feedback
    # UNVERIFIED / NOT_APPLICABLE -> no confidence mutation
    if verification_outcome == "VERIFIED":
        after_result = "success"
    elif verification_outcome == "FAILED":
        after_result = "failure"
    else:
        logger.info(
            "learning feedback skipped: experience=%s verification=%s",
            recalled_experience_id,
            verification_outcome,
        )
        return

    turn_id = str(
        kwargs.get("turn_id")
        or kwargs.get("task_id")
        or ""
    )

    if not turn_id:
        logger.warning(
            "learning feedback skipped: missing turn identity "
            "experience=%s",
            recalled_experience_id,
        )
        return

    try:
        from governance.experience_feedback import (
            ExperienceFeedbackEvaluator,
        )
        from governance.experience_memory import ExperienceMemory

        memory = ExperienceMemory()
        source = memory.get(str(recalled_experience_id))

        if source is None:
            logger.warning(
                "learning feedback skipped: recalled experience missing: %s",
                recalled_experience_id,
            )
            return

        evaluator = ExperienceFeedbackEvaluator()

        if evaluator.store.has_task_experience(
            turn_id,
            str(recalled_experience_id),
        ):
            logger.info(
                "learning feedback already recorded: turn=%s experience=%s",
                turn_id,
                recalled_experience_id,
            )
            return

        source_result = str(source.result or "").lower()

        if source_result == "successful":
            before_result = "success"
        elif source_result in {"failed", "failure"}:
            before_result = "failure"
        else:
            before_result = "unknown"

        feedback = evaluator.record_feedback(
            task_id=turn_id,
            experience_id=str(recalled_experience_id),
            recommendation_used=True,
            before_result=before_result,
            after_result=after_result,
            recommendation=source.future_recommendation or None,
            lessons=list(source.lessons_learned or []),
        )

        old_confidence = float(source.confidence or 0.0)

        new_confidence = evaluator.evolve_confidence(
            old_confidence,
            recommendation_used=True,
            success=feedback.success,
            impact_score=feedback.impact_score,
        )

        updated = memory.update_confidence(
            str(recalled_experience_id),
            new_confidence,
        )

        if updated is None:
            logger.warning(
                "learning confidence update failed: experience=%s",
                recalled_experience_id,
            )
            return

        logger.info(
            "learning feedback applied: turn=%s experience=%s "
            "verification=%s impact=%.2f confidence=%.4f->%.4f",
            turn_id,
            recalled_experience_id,
            verification_outcome,
            feedback.impact_score,
            old_confidence,
            new_confidence,
        )

    except Exception:
        logger.warning(
            "runtime learning feedback closure failed",
            exc_info=True,
        )

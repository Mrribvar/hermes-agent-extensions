"""Minimal deterministic planner (MVP, feature-flagged, dormant by default).

Scope of this module — deliberately narrow:

- It turns a goal string into a small, ordered list of ``Step`` objects.
- It is *deterministic*: no LLM call, no network, no I/O, no new tool.
- It never touches the system prompt, prompt cache, memory, verification,
  learning, or the execution layer. The only side effect it may cause is a
  merge-write into the existing per-session ``TodoStore``, and only when the
  caller explicitly asks for it.

Gating is the caller's job (``agent/turn_context.py``): the feature flag
``planning.enabled`` defaults to False and a trivial prompt skips planning
entirely, so the default runtime behavior is byte-for-byte unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One ordered unit of work inside a :class:`Plan`."""

    id: str
    title: str
    depends_on: List[str] = field(default_factory=list)
    tool_hint: str = ""


@dataclass(frozen=True)
class Plan:
    """A minimal, deterministic plan for one turn."""

    goal: str
    created_at: str
    steps: List[Step] = field(default_factory=list)

    def to_todos(self) -> List[Dict[str, Any]]:
        """Render the plan as ``TodoStore``-shaped items.

        Only the three fields ``TodoStore`` understands are emitted
        (``id`` / ``content`` / ``status``); ``depends_on`` and ``tool_hint``
        ride inside the content text so no schema change is required.
        """
        items: List[Dict[str, Any]] = []
        for step in self.steps:
            content = step.title
            extra: List[str] = []
            if step.depends_on:
                extra.append("after: " + ", ".join(step.depends_on))
            if step.tool_hint:
                extra.append("tool: " + step.tool_hint)
            if extra:
                content = f"{content} ({'; '.join(extra)})"
            items.append({"id": step.id, "content": content, "status": "pending"})
        return items


# --------------------------------------------------------------------------
# Deterministic goal decomposition
# --------------------------------------------------------------------------


# Verbs that reliably indicate a multi-step working request. This is a
# *classification aid for the planner*, not a general "is this multi-step"
# detector for the runtime — the runtime gate is the feature flag plus the
# trivial-prompt check, both owned by the caller.
_ACTION_VERBS = (
    "implement", "build", "create", "add", "write", "refactor", "fix",
    "migrate", "upgrade", "deploy", "set up", "setup", "configure", "install",
    "design", "analyse", "analyze", "audit", "review", "investigate",
    "debug", "test", "verify", "benchmark", "optimise", "optimize",
    "document", "research", "compare", "plan", "prepare", "generate",
)

# Signals that a request carries more than one deliverable.
_MULTI_SIGNALS = (
    " and ", " then ", " after that", " followed by", " plus ",
    " as well as ", " also ", " first ", " second ", " finally ",
)

_MAX_STEPS = 6


def _looks_multi_step(goal: str) -> bool:
    """Cheap, deterministic heuristic used *by the planner* only."""
    if not goal:
        return False
    lowered = goal.lower()
    if len(lowered) < 24:
        return False
    has_verb = any(v in lowered for v in _ACTION_VERBS)
    has_multi = any(s in lowered for s in _MULTI_SIGNALS)
    return has_verb and has_multi


def _first_clause(goal: str, limit: int = 80) -> str:
    """A short, stable slice of the goal used as a step title seed."""
    text = " ".join(str(goal or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _split_goal(goal: str) -> List[str]:
    """Split a compound goal on the same deterministic separators we detect."""
    text = " ".join(str(goal or "").split())
    if not text:
        return []
    parts: List[str] = [text]
    for sep in (" then ", " followed by ", " after that ", " and then "):
        nxt: List[str] = []
        for chunk in parts:
            nxt.extend(chunk.split(sep))
        parts = nxt
    return [p.strip(" .,;") for p in parts if p.strip(" .,;")]


class Planner:
    """Deterministic goal → plan conversion.

    The planner intentionally has no constructor arguments and no state: the
    same goal always produces the same plan, which keeps it testable and
    side-effect free.
    """

    def plan(
        self,
        goal: str,
        constraints: Optional[Dict[str, Any]] = None,
        recalled_context: Optional[str] = None,
    ) -> Plan:
        """Return a minimal :class:`Plan` for *goal*.

        ``constraints`` and ``recalled_context`` are accepted for contract
        stability. They are deliberately unused in the MVP so the planner
        stays deterministic and free of hidden inputs.
        """
        created_at = _utc_now()
        goal_text = " ".join(str(goal or "").split())

        if not goal_text or not _looks_multi_step(goal_text):
            # Single-deliverable request: one step, no fake decomposition.
            steps = [Step(id="s1", title=_first_clause(goal_text) or "Do the task")]
            return Plan(goal=goal_text, created_at=created_at, steps=steps)

        clauses = _split_goal(goal_text)
        steps = []
        for index, clause in enumerate(clauses[:_MAX_STEPS], start=1):
            step_id = f"s{index}"
            steps.append(
                Step(
                    id=step_id,
                    title=_first_clause(clause) or f"Step {index}",
                    depends_on=[f"s{index - 1}"] if index > 1 else [],
                    tool_hint="",
                )
            )
        if not steps:
            steps = [Step(id="s1", title=_first_clause(goal_text))]
        return Plan(goal=goal_text, created_at=created_at, steps=steps)


# --------------------------------------------------------------------------
# Flag + entry point
# --------------------------------------------------------------------------


def planning_enabled(config: Optional[Dict[str, Any]] = None) -> bool:
    """Return the ``planning.enabled`` flag. Default: False.

    Reads from the supplied config mapping when given, otherwise from the
    persisted ``config.yaml`` via the read-only loader. Any failure resolves
    to False — the safe default.
    """
    try:
        if config is None:
            from hermes_cli.config import load_config_readonly

            config = load_config_readonly() or {}
        section = (config or {}).get("planning") or {}
        if not isinstance(section, dict):
            return False
        return bool(section.get("enabled", False))
    except Exception:
        return False


def maybe_plan_turn(
    *,
    agent: Any,
    goal: str,
    config: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    recalled_context: Optional[str] = None,
) -> Optional[Plan]:
    """Run the planner for one turn and merge its steps into ``TodoStore``.

    Returns the :class:`Plan` when one was produced, else ``None``. This is
    the single entry point the runtime calls; it is a no-op unless the flag is
    on, the goal is non-trivial, and the agent exposes a writable todo store.

    Merge semantics: ``merge=True`` — existing todos are updated by id and new
    ones appended. Nothing is ever replaced or deleted here.
    """
    if not planning_enabled(config):
        return None

    store = getattr(agent, "_todo_store", None)
    if store is None:
        return None

    # Seed-only ownership: the model is the permanent owner of the todo list,
    # the planner may only seed it when it is empty. `build_turn_context`
    # hydrates the store from history BEFORE this hook runs, so a list the
    # model already owns always wins and is never touched here.
    try:
        if store.has_items():
            return None
    except Exception:
        pass

    try:
        from agent.memory_provider import is_trivial_prompt

        if is_trivial_prompt(goal):
            return None
    except Exception:
        pass

    try:
        plan = Planner().plan(
            goal,
            constraints=constraints,
            recalled_context=recalled_context,
        )
    except Exception:
        logger.warning("planner: plan construction failed", exc_info=True)
        return None

    try:
        store.write(plan.to_todos(), merge=True)
    except Exception:
        logger.warning("planner: todo merge failed", exc_info=True)
        return None

    logger.info(
        "planner: merged %d step(s) for goal=%r",
        len(plan.steps),
        _first_clause(plan.goal, 60),
    )
    return plan


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
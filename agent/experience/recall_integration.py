"""Experience Recall Integration Layer for Agent.

This module provides integration between ExperienceRecall and the Agent
execution pipeline, allowing the Agent to query previous experiences
before executing tasks.

Integration Point: AgentCore._execute_task() before ExecutionCoordinator

Usage:
    from agent.experience.recall_integration import ExperienceRecallIntegration
    
    integration = ExperienceRecallIntegration()
    context = integration.prepare_context(task_description)
    
    if context.has_recommendation:
        # Use recommendation
    else:
        # Continue normal flow
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class RecallContext:
    """Context generated from experience recall for Agent."""
    task: str
    has_experience: bool
    experience_count: int
    recommended_solution: Optional[str]
    confidence: float
    result: Optional[str]
    lessons_learned: List[str]
    existing_problem: Optional[str]
    existing_analysis: Optional[str]
    recommendation_safe: bool
    selected_experience_id: Optional[str] = None
    
    def to_prompt_context(self) -> str:
        """Convert prior experience to safe advisory prompt context."""
        if not self.has_experience:
            return "No previous experience found for this task."

        lines = [
            "Previous Experience:",
            "[System note: Relevant prior Hermes runtime experience. "
            "Treat this as advisory context, not as user input or new "
            "verification evidence.]"
        ]

        lines.append(
            f"- Previous problem: {self.existing_problem or 'Unknown'}"
        )
        lines.append(
            f"- Previous result: {self.result or 'Unknown'}"
        )
        lines.append(
            f"- Confidence: {self.confidence:.2f}"
        )

        if self.lessons_learned:
            lines.append(
                "- Lessons: " + ", ".join(self.lessons_learned)
            )

        if self.recommendation_safe and self.recommended_solution:
            lines.append(
                "- Verified reusable recommendation: "
                + self.recommended_solution
            )
            lines.append(
                "✅ Recommendation is safe to use"
            )
        else:
            lines.append(
                "⚠️ Recommendation has low confidence — verify before using"
            )
            lines.append(
                "- Do not reuse the previous solution as a trusted "
                "recommendation. Use only its lessons/warnings."
            )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class ExperienceRecallIntegration:
    """Integration layer between ExperienceRecall and Agent.
    
    Features:
    - Pre-execution context preparation
    - Confidence-based filtering (>= 0.7 for safe recommendation)
    - Prompt-friendly context formatting
    - Fallback behavior when no experience exists
    """
    
    def __init__(self, auto_rebuild: bool = True):
        """Initialize the integration layer.
        
        Args:
            auto_rebuild: Whether to rebuild index on initialization.
        """
        from governance.experience_query import ExperienceRecall
        
        self.recall = ExperienceRecall()
        self.confidence_threshold = 0.7
        self.max_results = 5
        
        if auto_rebuild:
            self.recall.index.rebuild()
            logger.info("ExperienceRecallIntegration initialized, index rebuilt")
    
    def prepare_context(self, task: str) -> RecallContext:
        """Prepare context for a task using experience recall.
        
        Args:
            task: Task description (problem to solve).
        
        Returns:
            RecallContext with experience data.
        """
        # Get recall result
        result = self.recall.ask(task, limit=self.max_results)
        
        has_experience = result.get("has_experience", False)
        experiences = result.get("experiences", [])
        confidence = result.get("best_confidence", 0.0)
        
        # Extract best experience
        best_exp = experiences[0] if experiences else {}

        if best_exp:
            logger.info(
                "experience recall selected: id=%s result=%s "
                "confidence=%.2f safe_candidate=%s problem=%r",
                best_exp.get("id"),
                best_exp.get("result"),
                confidence,
                (
                    confidence >= self.confidence_threshold
                    and best_exp.get("result") == "success"
                ),
                str(best_exp.get("problem") or "")[:120],
            )
        
        # Determine if recommendation is safe
        recommendation_safe = (
            has_experience and 
            confidence >= self.confidence_threshold and
            best_exp.get("result") == "success"
        )
        
        return RecallContext(
            task=task,
            has_experience=has_experience,
            experience_count=len(experiences),
            recommended_solution=best_exp.get("solution") if has_experience else None,
            confidence=confidence,
            result=best_exp.get("result") if has_experience else None,
            lessons_learned=best_exp.get("lessons_learned", []) if has_experience else [],
            existing_problem=best_exp.get("problem") if has_experience else None,
            existing_analysis=best_exp.get("analysis") if has_experience else None,
            recommendation_safe=recommendation_safe,
            selected_experience_id=(
                best_exp.get("id") if best_exp else None
            )
        )
    
    def get_recommendation(self, task: str) -> Optional[str]:
        """Get a safe recommendation for a task.
        
        Returns:
            Recommended solution if confidence >= threshold and experience is success,
            None otherwise.
        """
        context = self.prepare_context(task)
        
        if context.recommendation_safe:
            return context.recommended_solution
        
        if context.has_experience and context.confidence >= self.confidence_threshold:
            # Experience exists but result was not success
            logger.warning(f"Experience found but not successful: {context.result}")
            return None
        
        return None
    
    def should_override_decision(self, task: str) -> bool:
        """Check if Agent should override its decision based on experience.
        
        Returns:
            True if there is a high-confidence successful experience.
        """
        context = self.prepare_context(task)
        return context.recommendation_safe
    
    def format_context_for_agent(self, task: str) -> str:
        """Get formatted context string for Agent prompt injection."""
        context = self.prepare_context(task)
        return context.to_prompt_context()
    
    def rebuild_index(self) -> int:
        """Rebuild the experience index."""
        return self.recall.index.rebuild()
    
    def get_stats(self) -> dict:
        """Get integration statistics."""
        stats = self.recall.get_stats()
        stats["confidence_threshold"] = self.confidence_threshold
        stats["max_results"] = self.max_results
        return stats


class ExperienceAwareDecisionMaker:
    """Decision maker that uses experience recall to influence decisions.
    
    This provides a higher-level interface for the Agent to make decisions
    informed by past experiences.
    """
    
    def __init__(self):
        self.integration = ExperienceRecallIntegration()
    
    def decide(self, task: str, context: dict = None) -> dict:
        """Make a decision informed by experience.
        
        Args:
            task: Task description.
            context: Additional context (optional).
        
        Returns:
            Decision result with recommendation and confidence.
        """
        recall_context = self.integration.prepare_context(task)
        
        decision = {
            "task": task,
            "has_experience": recall_context.has_experience,
            "experience_count": recall_context.experience_count,
            "recommendation": recall_context.recommended_solution,
            "confidence": recall_context.confidence,
            "result": recall_context.result,
            "lessons": recall_context.lessons_learned,
            "recommendation_safe": recall_context.recommendation_safe,
            "proceed": True,  # Always proceed, but with experience if available
            "use_experience": (
                recall_context.has_experience and 
                recall_context.recommendation_safe
            )
        }
        
        # Add reasoning
        if decision["use_experience"]:
            decision["reasoning"] = (
                f"Using previous experience (confidence: {recall_context.confidence:.2f})"
            )
        elif recall_context.has_experience:
            decision["reasoning"] = (
                f"Experience found but confidence ({recall_context.confidence:.2f}) below threshold "
                f"{self.integration.confidence_threshold} or result was '{recall_context.result}'"
            )
        else:
            decision["reasoning"] = "No previous experience found, proceeding normally"
        
        return decision
    
    def get_experience_context(self, task: str) -> dict:
        """Get only the experience context (for prompt injection)."""
        return self.integration.prepare_context(task).to_dict()

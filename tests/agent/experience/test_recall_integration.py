"""Tests for Experience Recall Integration Layer."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.experience.recall_integration import (
    ExperienceRecallIntegration,
    RecallContext,
    ExperienceAwareDecisionMaker
)


class TestExperienceRecallIntegration:
    """Tests for ExperienceRecallIntegration class."""
    
    @pytest.fixture
    def sample_experiences(self):
        """Create sample experiences for testing."""
        return [
            {
                "id": "exp_001",
                "timestamp": "2026-08-05T12:00:00.000000",
                "problem": "Command execution: ls -la ~/test/",
                "analysis": "Command executed successfully.",
                "solution": "Use ls -la to list directory contents.",
                "result": "success",
                "lessons_learned": [],
                "confidence": 0.85,
                "future_recommendation": "Continue using ls -la.",
                "tags": ["command", "file_operation", "success"],
                "metadata": {"tool_id": "terminal", "duration_ms": 42}
            },
            {
                "id": "exp_002",
                "timestamp": "2026-08-05T12:30:00.000000",
                "problem": "Command execution: cat /nonexistent/file",
                "analysis": "Command failed. File does not exist.",
                "solution": "Check file existence before reading.",
                "result": "failure",
                "lessons_learned": ["Always check if file exists."],
                "confidence": 0.92,
                "future_recommendation": "Add file check.",
                "tags": ["command", "file_operation", "failure"],
                "metadata": {"tool_id": "terminal", "duration_ms": 15}
            }
        ]
    
    @pytest.fixture
    def mock_recall(self, sample_experiences):
        """Create a mock ExperienceRecall."""
        with patch('governance.experience_query.ExperienceRecall') as MockRecall:
            mock = MockRecall.return_value
            
            # Mock ask method
            def ask_side_effect(problem, limit=5):
                if "list" in problem.lower() or "ls" in problem.lower():
                    return {
                        "has_experience": True,
                        "total_count": 1,
                        "best_confidence": 0.85,
                        "experiences": [sample_experiences[0]],
                        "query_type": "keyword"
                    }
                elif "file" in problem.lower() and "not" in problem.lower():
                    return {
                        "has_experience": True,
                        "total_count": 1,
                        "best_confidence": 0.92,
                        "experiences": [sample_experiences[1]],
                        "query_type": "keyword"
                    }
                else:
                    return {
                        "has_experience": False,
                        "total_count": 0,
                        "best_confidence": 0.0,
                        "experiences": [],
                        "query_type": "keyword"
                    }
            
            mock.ask.side_effect = ask_side_effect
            
            # Mock index
            mock.index = MagicMock()
            mock.index.rebuild.return_value = 2
            
            yield mock
    
    @pytest.fixture
    def integration(self, mock_recall):
        """Create integration instance."""
        with patch('governance.experience_query.ExperienceRecall', return_value=mock_recall):
            return ExperienceRecallIntegration(auto_rebuild=False)
    
    def test_prepare_context_success(self, integration):
        """Test context preparation for a matching task."""
        context = integration.prepare_context("list directory contents")
        
        assert context.has_experience is True
        assert context.experience_count == 1
        assert context.recommended_solution == "Use ls -la to list directory contents."
        assert context.confidence == 0.85
        assert context.result == "success"
        assert context.recommendation_safe is True
    
    def test_prepare_context_failure(self, integration):
        """Test context preparation for a task with failure experience."""
        context = integration.prepare_context("read file that does not exist")
        
        assert context.has_experience is True
        assert context.experience_count == 1
        assert context.result == "failure"
        assert len(context.lessons_learned) == 1
        # Low confidence threshold? Actually 0.92 is high, but result is failure
        assert context.recommendation_safe is False
    
    def test_prepare_context_no_experience(self, integration):
        """Test context preparation for a task with no experience."""
        context = integration.prepare_context("write a novel")
        
        assert context.has_experience is False
        assert context.experience_count == 0
        assert context.recommended_solution is None
        assert context.confidence == 0.0
        assert context.result is None
        assert context.recommendation_safe is False
    
    def test_to_prompt_context_with_experience(self, integration):
        """Test prompt context formatting with experience."""
        context = integration.prepare_context("list directory contents")
        prompt = context.to_prompt_context()
        
        assert "Previous Experience:" in prompt
        assert "Use ls -la" in prompt
        assert "Confidence: 0.85" in prompt
        assert "✅ Recommendation is safe to use" in prompt
    
    def test_to_prompt_context_no_experience(self, integration):
        """Test prompt context formatting without experience."""
        context = integration.prepare_context("write a novel")
        prompt = context.to_prompt_context()
        
        assert "No previous experience found" in prompt
    
    def test_get_recommendation_safe(self, integration):
        """Test getting a safe recommendation."""
        recommendation = integration.get_recommendation("list directory contents")
        
        assert recommendation == "Use ls -la to list directory contents."
    
    def test_get_recommendation_unsafe(self, integration):
        """Test getting a recommendation when unsafe."""
        recommendation = integration.get_recommendation("read file that does not exist")
        
        # Experience found but result is failure, so no safe recommendation
        assert recommendation is None
    
    def test_get_recommendation_no_experience(self, integration):
        """Test getting a recommendation with no experience."""
        recommendation = integration.get_recommendation("write a novel")
        
        assert recommendation is None
    
    def test_should_override_decision_true(self, integration):
        """Test decision override when safe experience exists."""
        should_override = integration.should_override_decision("list directory contents")
        
        assert should_override is True
    
    def test_should_override_decision_false(self, integration):
        """Test decision override when no safe experience exists."""
        should_override = integration.should_override_decision("read file that does not exist")
        
        assert should_override is False
    
    def test_format_context_for_agent(self, integration):
        """Test formatted context for agent."""
        context_str = integration.format_context_for_agent("list directory contents")
        
        assert "Previous Experience:" in context_str
        assert "Use ls -la" in context_str
    
    def test_rebuild_index(self, integration):
        """Test index rebuild."""
        count = integration.rebuild_index()
        
        assert count == 2


class TestExperienceAwareDecisionMaker:
    """Tests for ExperienceAwareDecisionMaker class."""
    
    @pytest.fixture
    def sample_experiences(self):
        return [
            {
                "id": "exp_001",
                "timestamp": "2026-08-05T12:00:00.000000",
                "problem": "Command execution: ls -la ~/test/",
                "analysis": "Command executed successfully.",
                "solution": "Use ls -la to list directory contents.",
                "result": "success",
                "lessons_learned": [],
                "confidence": 0.85,
                "future_recommendation": "Continue using ls -la.",
                "tags": ["command", "file_operation", "success"],
                "metadata": {"tool_id": "terminal"}
            }
        ]
    
    @pytest.fixture
    def mock_integration(self, sample_experiences):
        """Create a mock integration."""
        with patch('agent.experience.recall_integration.ExperienceRecallIntegration') as MockIntegration:
            mock = MockIntegration.return_value
            
            def prepare_context_side_effect(task):
                if "list" in task.lower():
                    return RecallContext(
                        task=task,
                        has_experience=True,
                        experience_count=1,
                        recommended_solution="Use ls -la.",
                        confidence=0.85,
                        result="success",
                        lessons_learned=[],
                        existing_problem="ls -la ~/test/",
                        existing_analysis="Command executed successfully.",
                        recommendation_safe=True
                    )
                else:
                    return RecallContext(
                        task=task,
                        has_experience=False,
                        experience_count=0,
                        recommended_solution=None,
                        confidence=0.0,
                        result=None,
                        lessons_learned=[],
                        existing_problem=None,
                        existing_analysis=None,
                        recommendation_safe=False
                    )
            
            mock.prepare_context.side_effect = prepare_context_side_effect
            mock.confidence_threshold = 0.7
            
            yield mock
    
    @pytest.fixture
    def decision_maker(self, mock_integration):
        """Create decision maker with mock integration."""
        with patch('agent.experience.recall_integration.ExperienceRecallIntegration', return_value=mock_integration):
            return ExperienceAwareDecisionMaker()
    
    def test_decide_with_experience(self, decision_maker):
        """Test decision with experience."""
        result = decision_maker.decide("list files")
        
        assert result["has_experience"] is True
        assert result["recommendation"] == "Use ls -la."
        assert result["confidence"] == 0.85
        assert result["recommendation_safe"] is True
        assert result["use_experience"] is True
        assert "Using previous experience" in result["reasoning"]
    
    def test_decide_without_experience(self, decision_maker):
        """Test decision without experience."""
        result = decision_maker.decide("write a novel")
        
        assert result["has_experience"] is False
        assert result["recommendation"] is None
        assert result["confidence"] == 0.0
        assert result["recommendation_safe"] is False
        assert result["use_experience"] is False
        assert "No previous experience found" in result["reasoning"]
    
    def test_get_experience_context(self, decision_maker):
        """Test getting experience context."""
        context = decision_maker.get_experience_context("list files")
        
        assert context["has_experience"] is True
        assert context["recommended_solution"] == "Use ls -la."
        assert context["confidence"] == 0.85


class TestRecallContext:
    """Tests for RecallContext dataclass."""
    
    def test_to_prompt_context_with_experience(self):
        context = RecallContext(
            task="test",
            has_experience=True,
            experience_count=1,
            recommended_solution="Test solution",
            confidence=0.85,
            result="success",
            lessons_learned=["Lesson 1"],
            existing_problem="Test problem",
            existing_analysis="Test analysis",
            recommendation_safe=True
        )
        
        prompt = context.to_prompt_context()
        
        assert "Previous Experience:" in prompt
        assert "Test problem" in prompt
        assert "Test solution" in prompt
        assert "Confidence: 0.85" in prompt
        assert "✅ Recommendation is safe to use" in prompt
    
    def test_to_prompt_context_no_experience(self):
        context = RecallContext(
            task="test",
            has_experience=False,
            experience_count=0,
            recommended_solution=None,
            confidence=0.0,
            result=None,
            lessons_learned=[],
            existing_problem=None,
            existing_analysis=None,
            recommendation_safe=False
        )
        
        prompt = context.to_prompt_context()
        
        assert "No previous experience found" in prompt
    
    def test_to_prompt_context_low_confidence(self):
        context = RecallContext(
            task="test",
            has_experience=True,
            experience_count=1,
            recommended_solution="Test solution",
            confidence=0.5,
            result="failure",
            lessons_learned=["Lesson 1"],
            existing_problem="Test problem",
            existing_analysis="Test analysis",
            recommendation_safe=False
        )
        
        prompt = context.to_prompt_context()
        
        assert "⚠️ Recommendation has low confidence" in prompt
    
    def test_to_dict(self):
        context = RecallContext(
            task="test",
            has_experience=True,
            experience_count=1,
            recommended_solution="Test solution",
            confidence=0.85,
            result="success",
            lessons_learned=["Lesson 1"],
            existing_problem="Test problem",
            existing_analysis="Test analysis",
            recommendation_safe=True
        )
        
        data = context.to_dict()
        
        assert data["task"] == "test"
        assert data["has_experience"] is True
        assert data["confidence"] == 0.85
        assert data["recommended_solution"] == "Test solution"

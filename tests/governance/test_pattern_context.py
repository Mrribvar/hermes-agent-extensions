"""Tests for Pattern Context and Enricher."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from governance.pattern_context import (
    PatternDecisionContext,
    PatternContextEnricher
)
from governance.pattern_config import PatternConfig


class TestPatternDecisionContext:
    """Tests for PatternDecisionContext dataclass."""
    
    def test_to_dict(self):
        context = PatternDecisionContext(
            task_id="task_001",
            matched_patterns=[{"type": "HIGH_SUCCESS"}],
            confidence_adjustment=0.1,
            risk_level="LOW",
            recommendations=["Use this strategy"],
            warnings=["Watch for edge cases"],
            pattern_count=1
        )
        
        data = context.to_dict()
        assert data["task_id"] == "task_001"
        assert data["confidence_adjustment"] == 0.1
        assert data["risk_level"] == "LOW"
        assert len(data["recommendations"]) == 1
        assert len(data["warnings"]) == 1
        assert data["pattern_count"] == 1
    
    def test_from_dict(self):
        data = {
            "task_id": "task_001",
            "matched_patterns": [{"type": "HIGH_SUCCESS"}],
            "confidence_adjustment": 0.1,
            "risk_level": "LOW",
            "recommendations": ["Use this"],
            "warnings": [],
            "pattern_count": 1,
            "timestamp": "2026-08-06T00:00:00"
        }
        
        context = PatternDecisionContext.from_dict(data)
        assert context.task_id == "task_001"
        assert context.confidence_adjustment == 0.1
        assert context.risk_level == "LOW"
        assert len(context.recommendations) == 1
    
    def test_has_risk(self):
        # LOW risk
        context = PatternDecisionContext(
            task_id="task_001",
            risk_level="LOW"
        )
        assert context.has_risk() is False
        
        # MEDIUM risk
        context = PatternDecisionContext(
            task_id="task_001",
            risk_level="MEDIUM"
        )
        assert context.has_risk() is True
        
        # HIGH risk
        context = PatternDecisionContext(
            task_id="task_001",
            risk_level="HIGH"
        )
        assert context.has_risk() is True
    
    def test_has_high_risk(self):
        context = PatternDecisionContext(
            task_id="task_001",
            risk_level="HIGH"
        )
        assert context.has_high_risk() is True
        
        context = PatternDecisionContext(
            task_id="task_001",
            risk_level="LOW"
        )
        assert context.has_high_risk() is False
    
    def test_has_recommendation(self):
        context = PatternDecisionContext(
            task_id="task_001",
            recommendations=["Use this"]
        )
        assert context.has_recommendation() is True
        
        context = PatternDecisionContext(
            task_id="task_001",
            recommendations=[]
        )
        assert context.has_recommendation() is False
    
    def test_has_warnings(self):
        context = PatternDecisionContext(
            task_id="task_001",
            warnings=["Warning"]
        )
        assert context.has_warnings() is True
        
        context = PatternDecisionContext(
            task_id="task_001",
            warnings=[]
        )
        assert context.has_warnings() is False
    
    def test_get_primary_recommendation(self):
        context = PatternDecisionContext(
            task_id="task_001",
            recommendations=["First", "Second"]
        )
        assert context.get_primary_recommendation() == "First"
        
        context = PatternDecisionContext(
            task_id="task_001",
            recommendations=[]
        )
        assert context.get_primary_recommendation() is None
    
    def test_get_primary_warning(self):
        context = PatternDecisionContext(
            task_id="task_001",
            warnings=["First", "Second"]
        )
        assert context.get_primary_warning() == "First"
        
        context = PatternDecisionContext(
            task_id="task_001",
            warnings=[]
        )
        assert context.get_primary_warning() is None


class TestPatternContextEnricher:
    """Tests for PatternContextEnricher."""
    
    @pytest.fixture
    def mock_adapter(self):
        adapter = MagicMock()
        
        # Mock guidance
        guidance = MagicMock()
        guidance.task_id = "task_001"
        guidance.matched_patterns = [{"type": "HIGH_SUCCESS"}]
        guidance.confidence_adjustment = 0.1
        guidance.risk_level = "LOW"
        guidance.recommendations = ["Use this"]
        guidance.warnings = []
        guidance.pattern_count = 1
        adapter.get_pattern_guidance.return_value = guidance
        
        # Mock evaluation
        evaluation = MagicMock()
        evaluation.pattern_score = 0.85
        evaluation.is_recommended = True
        evaluation.is_risky = False
        evaluation.warnings = []
        adapter.evaluate_strategy.return_value = evaluation
        
        return adapter
    
    @pytest.fixture
    def enricher(self, mock_adapter):
        config = PatternConfig(
            enabled=True,
            enable_confidence_adjustment=True,
            enable_risk_detection=True,
            enable_recommendations=True
        )
        return PatternContextEnricher(
            adapter=mock_adapter,
            config=config,
            enabled=True
        )
    
    def test_enrich_context_with_patterns(self, enricher):
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        assert "pattern_context" in enriched
        assert enriched["confidence"] == 0.6  # 0.5 + 0.1
        assert enriched["risk_level"] == "LOW"
        assert "pattern_context" in enriched
    
    def test_enrich_context_disabled(self, enricher):
        enricher.enabled = False
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        assert "pattern_context" not in enriched
        assert enriched["confidence"] == 0.5
    
    def test_enrich_context_config_disabled(self, enricher):
        enricher.config.enabled = False
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        assert "pattern_context" not in enriched
        assert enriched["confidence"] == 0.5
    
    def test_enrich_context_confidence_adjustment_disabled(self, enricher):
        enricher.config.enable_confidence_adjustment = False
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        assert enriched["confidence"] == 0.5
        assert "pattern_context" in enriched
    
    def test_enrich_context_risk_detection_disabled(self, enricher):
        enricher.config.enable_risk_detection = False
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        assert "risk_level" not in enriched
        assert "pattern_context" in enriched
    
    def test_enrich_context_fail_safe(self, enricher):
        enricher.adapter.get_pattern_guidance = MagicMock(side_effect=Exception("Test error"))
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        # Should return original context, not crash
        assert enriched["confidence"] == 0.5
        assert "pattern_context" not in enriched
    
    def test_enrich_strategy(self, enricher):
        strategy = {"id": "strategy_001", "type": "file_operation"}
        context = {"task_id": "task_001"}
        
        enriched = enricher.enrich_strategy(strategy, context)
        
        assert enriched["pattern_score"] == 0.85
        assert enriched["is_recommended"] is True
        assert enriched["is_risky"] is False
    
    def test_enrich_strategy_disabled(self, enricher):
        enricher.enabled = False
        strategy = {"id": "strategy_001"}
        context = {}
        
        enriched = enricher.enrich_strategy(strategy, context)
        
        assert "pattern_score" not in enriched
        assert "is_recommended" not in enriched
    
    def test_enrich_strategy_fail_safe(self, enricher):
        enricher.adapter.evaluate_strategy = MagicMock(side_effect=Exception("Test error"))
        strategy = {"id": "strategy_001"}
        context = {}
        
        enriched = enricher.enrich_strategy(strategy, context)
        
        # Should return original strategy
        assert enriched["id"] == "strategy_001"
        assert "pattern_score" not in enriched
    
    def test_get_risk_assessment(self, enricher):
        context = {"task_id": "task_001"}
        assessment = enricher.get_risk_assessment(context)
        
        assert assessment["risk_level"] == "LOW"
        assert assessment["pattern_count"] == 1
    
    def test_get_risk_assessment_disabled(self, enricher):
        enricher.enabled = False
        context = {"task_id": "task_001"}
        assessment = enricher.get_risk_assessment(context)
        
        assert assessment["risk_level"] == "LOW"
        assert assessment["warnings"] == []
    
    def test_get_risk_assessment_fail_safe(self, enricher):
        enricher.adapter.get_pattern_guidance = MagicMock(side_effect=Exception("Test error"))
        context = {"task_id": "task_001"}
        assessment = enricher.get_risk_assessment(context)
        
        assert assessment["risk_level"] == "LOW"
        assert assessment["warnings"] == []
    
    def test_is_enabled(self, enricher):
        assert enricher.is_enabled() is True
        
        enricher.enabled = False
        assert enricher.is_enabled() is False
        
        enricher.enabled = True
        enricher.config.enabled = False
        assert enricher.is_enabled() is False
    
    def test_enrich_context_preserves_original(self, enricher):
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        # Original should be unchanged
        assert context["confidence"] == 0.5
        assert "pattern_context" not in context
        
        # Enriched should have changes
        assert enriched["confidence"] == 0.6
        assert "pattern_context" in enriched
    
    def test_enrich_context_without_confidence(self, enricher):
        context = {"task_id": "task_001"}
        enriched = enricher.enrich_context(context)
        
        assert "pattern_context" in enriched
        assert "confidence" not in enriched  # Should not add if not present
    
    def test_enrich_context_with_multiple_patterns(self, enricher):
        # Setup with multiple patterns
        guidance = MagicMock()
        guidance.task_id = "task_001"
        guidance.matched_patterns = [
            {"type": "HIGH_SUCCESS"},
            {"type": "IMPROVING"}
        ]
        guidance.confidence_adjustment = 0.15
        guidance.risk_level = "LOW"
        guidance.recommendations = ["Recommended", "Also good"]
        guidance.warnings = []
        guidance.pattern_count = 2
        enricher.adapter.get_pattern_guidance.return_value = guidance
        
        context = {"task_id": "task_001", "confidence": 0.5}
        enriched = enricher.enrich_context(context)
        
        assert enriched["confidence"] == 0.65  # 0.5 + 0.15
        pattern_ctx = enriched["pattern_context"]
        assert pattern_ctx.pattern_count == 2
        assert len(pattern_ctx.recommendations) == 2

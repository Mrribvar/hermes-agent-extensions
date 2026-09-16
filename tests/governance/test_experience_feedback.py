"""Tests for Experience Feedback Loop."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from governance.experience_feedback import (
    FeedbackRecord,
    ExperienceFeedbackStore,
    ExperienceFeedbackEvaluator
)

class TestFeedbackRecord:
    """Tests for FeedbackRecord dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        record = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0,
            lessons=["Lesson 1"],
            recommendation="Check file first"
        )

        data = record.to_dict()
        assert data["task_id"] == "task_001"
        assert data["experience_id"] == "exp_001"
        assert data["recommendation_used"] is True
        assert data["before_result"] == "failure"
        assert data["after_result"] == "success"
        assert data["success"] is True
        assert data["impact_score"] == 1.0
        assert data["lessons"] == ["Lesson 1"]
        assert data["recommendation"] == "Check file first"

    def test_to_json(self):
        """Test conversion to JSON."""
        record = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )

        json_str = record.to_json()
        data = json.loads(json_str)
        assert data["task_id"] == "task_001"


class TestExperienceFeedbackStore:
    """Tests for ExperienceFeedbackStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_dir):
        """Create a feedback store in temporary directory."""
        return ExperienceFeedbackStore(data_dir=str(temp_dir))

    def test_init_creates_directory(self, temp_dir):
        """Test that initialization creates the data directory."""
        store = ExperienceFeedbackStore(data_dir=str(temp_dir))
        assert temp_dir.exists()
        assert (temp_dir / "feedback.json").exists() is False

    def test_record_feedback(self, store):
        """Test recording feedback."""
        record = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )

        store.record(record)
        assert store.count() == 1
        assert store.feedback_file.exists()

    def test_get_all(self, store):
        """Test getting all records."""
        record1 = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )
        record2 = FeedbackRecord(
            task_id="task_002",
            experience_id="exp_002",
            recommendation_used=False,
            before_result="failure",
            after_result="failure",
            success=False,
            impact_score=0.0
        )

        store.record(record1)
        store.record(record2)

        all_records = store.get_all()
        assert len(all_records) == 2

    def test_get_by_experience(self, store):
        """Test getting records by experience ID."""
        record = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )

        store.record(record)

        by_exp = store.get_by_experience("exp_001")
        assert len(by_exp) == 1
        assert by_exp[0].experience_id == "exp_001"

    def test_get_by_task(self, store):
        """Test getting record by task ID."""
        record = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )

        store.record(record)

        by_task = store.get_by_task("task_001")
        assert by_task is not None
        assert by_task.task_id == "task_001"

    def test_get_recent(self, store):
        """Test getting recent records."""
        record1 = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0,
            timestamp="2026-08-05T10:00:00.000000"
        )
        record2 = FeedbackRecord(
            task_id="task_002",
            experience_id="exp_002",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0,
            timestamp="2026-08-05T11:00:00.000000"
        )

        store.record(record1)
        store.record(record2)

        recent = store.get_recent(limit=1)
        assert len(recent) == 1
        # Should be record2 (more recent)
        assert recent[0].task_id == "task_002"

    def test_get_successful_feedback(self, store):
        """Test getting successful feedback."""
        record1 = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )
        record2 = FeedbackRecord(
            task_id="task_002",
            experience_id="exp_002",
            recommendation_used=False,
            before_result="failure",
            after_result="failure",
            success=False,
            impact_score=0.0
        )

        store.record(record1)
        store.record(record2)

        successful = store.get_successful_feedback()
        assert len(successful) == 1
        assert successful[0].task_id == "task_001"

    def test_get_stats(self, store):
        """Test getting statistics."""
        record1 = FeedbackRecord(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            success=True,
            impact_score=1.0
        )
        record2 = FeedbackRecord(
            task_id="task_002",
            experience_id="exp_002",
            recommendation_used=True,
            before_result="success",
            after_result="success",
            success=True,
            impact_score=0.5
        )

        store.record(record1)
        store.record(record2)

        stats = store.get_stats()
        assert stats["total"] == 2
        assert stats["recommendation_used"] == 2
        assert stats["success_rate"] == 1.0
        assert stats["avg_impact_score"] == 0.75


class TestExperienceFeedbackEvaluator:
    """Tests for ExperienceFeedbackEvaluator."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def evaluator(self, temp_dir):
        """Create evaluator with temp store."""
        # Patch the store to use temp directory
        store = ExperienceFeedbackStore(data_dir=str(temp_dir))
        evaluator = ExperienceFeedbackEvaluator()
        evaluator.store = store
        return evaluator

    def test_calculate_improvement(self, evaluator):
        """Test improvement calculation."""
        # failure → success = 1.0
        assert evaluator.calculate_improvement("failure", "success") == 1.0

        # success → success = 0.5
        assert evaluator.calculate_improvement("success", "success") == 0.5

        # failure → failure = 0.0
        assert evaluator.calculate_improvement("failure", "failure") == 0.0

        # success → failure = -0.5
        assert evaluator.calculate_improvement("success", "failure") == -0.5

        # unknown → success = 0.5
        assert evaluator.calculate_improvement("unknown", "success") == 0.5

        # unknown → failure = -0.3
        assert evaluator.calculate_improvement("unknown", "failure") == -0.3

    def test_record_feedback(self, evaluator):
        """Test recording feedback through evaluator."""
        record = evaluator.record_feedback(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            recommendation="Check file first",
            lessons=["Always check file existence"]
        )

        assert record.impact_score == 1.0
        assert record.success is True
        assert record.recommendation == "Check file first"
        assert record.lessons == ["Always check file existence"]

    def test_get_best_performing_experiences(self, evaluator):
        """Test getting best performing experiences."""
        # Record multiple feedbacks for two experiences
        evaluator.record_feedback(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            recommendation="Check file first"
        )
        evaluator.record_feedback(
            task_id="task_002",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            recommendation="Check file first"
        )
        evaluator.record_feedback(
            task_id="task_003",
            experience_id="exp_002",
            recommendation_used=False,
            before_result="failure",
            after_result="failure",
            recommendation="None"
        )

        best = evaluator.get_best_performing_experiences(min_feedback=2)

        # exp_001 should be top (2/2 success)
        assert len(best) == 1
        assert best[0]["experience_id"] == "exp_001"
        assert best[0]["success_rate"] == 1.0
        assert best[0]["total_feedback"] == 2

    def test_compare_with_previous(self, evaluator):
        """Test comparing with previous execution."""
        # First execution
        evaluator.record_feedback(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=False,
            before_result="unknown",
            after_result="failure",
            recommendation="None"
        )

        # Second execution (same task)
        evaluator.record_feedback(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            recommendation="Check file first"
        )

        comparison = evaluator.compare_with_previous("task_001")
        assert comparison is not None
        assert comparison["task_id"] == "task_001"
        assert comparison["previous_result"] == "success"
        assert comparison["recommendation_used"] is True

    def test_get_improvement_summary(self, evaluator):
        """Test getting improvement summary."""
        evaluator.record_feedback(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            recommendation="Check file first"
        )
        evaluator.record_feedback(
            task_id="task_002",
            experience_id="exp_002",
            recommendation_used=False,
            before_result="failure",
            after_result="failure",
            recommendation="None"
        )

        summary = evaluator.get_improvement_summary()
        assert summary["total_feedback"] == 2
        assert summary["recommendation_used"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["improvement_rate"] == 0.5  # 1 of 2 improved

    def test_empty_feedback_handling(self, evaluator):
        """Test handling empty feedback store."""
        summary = evaluator.get_improvement_summary()
        assert summary["total_feedback"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["improvement_rate"] == 0.0

    def test_best_experience_min_feedback_filter(self, evaluator):
        """Test min_feedback filter in best experiences."""
        # Only one feedback for exp_001
        evaluator.record_feedback(
            task_id="task_001",
            experience_id="exp_001",
            recommendation_used=True,
            before_result="failure",
            after_result="success",
            recommendation="Check file first"
        )

        # min_feedback=2 should filter it out
        best = evaluator.get_best_performing_experiences(min_feedback=2)
        assert len(best) == 0

        # min_feedback=1 should include it
        best = evaluator.get_best_performing_experiences(min_feedback=1)
        assert len(best) == 1

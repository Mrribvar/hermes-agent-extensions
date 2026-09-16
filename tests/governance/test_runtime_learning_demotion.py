from governance.retention import (
    RetentionConfig,
    RetentionPolicy,
)


def _experience():
    return {
        "id": "exp-real",
        "timestamp": "2026-08-12T20:00:00",
        "problem": "real production runtime task",
        "result": "successful",
        "confidence": 0.95,
        "lessons_learned": ["verified_success"],
        "tags": [
            "runtime_learning",
            "verification",
        ],
        "metadata": {
            "learning_source": "turn_finalizer",
            "verification_outcome": "VERIFIED",
            "turn_id": "runtime-real-turn",
        },
    }


def _feedback(
    *,
    success=True,
    after=None,
):
    if after is None:
        after = "success" if success else "failure"

    return {
        "task_id": "runtime-turn",
        "experience_id": "exp-real",
        "recommendation_used": True,
        "before_result": "success",
        "after_result": after,
        "success": success,
        "impact_score": 0.5 if success else -0.5,
    }


def _policy():
    return RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
            gold_confidence_threshold=0.8,
        )
    )


def test_three_successes_can_be_gold():
    feedback = [
        _feedback(),
        _feedback(),
        _feedback(),
    ]

    assert _policy().classify_with_feedback_history(
        _experience(),
        feedback,
    ) == RetentionPolicy.GOLD


def test_latest_failure_demotes_previous_gold():
    feedback = [
        _feedback(),
        _feedback(),
        _feedback(),
        _feedback(success=False),
    ]

    assert _policy().classify_with_feedback_history(
        _experience(),
        feedback,
    ) == RetentionPolicy.SILVER


def test_success_after_failure_does_not_immediately_restore_gold():
    feedback = [
        _feedback(),
        _feedback(),
        _feedback(success=False),
        _feedback(),
        _feedback(success=False),
        _feedback(),
    ]

    assert _policy().classify_with_feedback_history(
        _experience(),
        feedback,
    ) == RetentionPolicy.SILVER


def test_old_failure_outside_recent_window_can_recover():
    feedback = [
        _feedback(success=False),
        _feedback(),
        _feedback(),
        _feedback(),
        _feedback(),
        _feedback(),
    ]

    assert _policy().classify_with_feedback_history(
        _experience(),
        feedback,
    ) == RetentionPolicy.GOLD


def test_feedback_for_other_experience_does_not_demote():
    feedback = [
        _feedback(),
        _feedback(),
        _feedback(),
        {
            **_feedback(success=False),
            "experience_id": "other-exp",
        },
    ]

    assert _policy().classify_with_feedback_history(
        _experience(),
        feedback,
    ) == RetentionPolicy.GOLD

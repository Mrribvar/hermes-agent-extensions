from governance.retention import (
    RetentionConfig,
    RetentionPolicy,
)


def _experience(
    *,
    experience_id="exp-real",
    confidence=0.95,
    verification="VERIFIED",
    result="successful",
    problem="real production task",
    turn_id="runtime-real-turn",
):
    return {
        "id": experience_id,
        "timestamp": "2026-08-12T20:00:00",
        "problem": problem,
        "result": result,
        "confidence": confidence,
        "lessons_learned": ["verified_success"],
        "tags": [
            "runtime_learning",
            "verification",
        ],
        "metadata": {
            "learning_source": "turn_finalizer",
            "verification_outcome": verification,
            "turn_id": turn_id,
        },
    }


def _feedback(
    experience_id,
    *,
    success=True,
    used=True,
    after_result=None,
):
    if after_result is None:
        after_result = "success" if success else "failure"

    return {
        "task_id": "runtime-turn",
        "experience_id": experience_id,
        "recommendation_used": used,
        "before_result": "success",
        "after_result": after_result,
        "success": success,
        "impact_score": 0.5 if success else -0.5,
    }


def test_verified_runtime_without_reuse_is_silver():
    policy = RetentionPolicy(RetentionConfig())

    exp = _experience()

    assert policy.classify_with_feedback(
        exp,
        [],
    ) == policy.SILVER


def test_verified_runtime_needs_repeated_success_for_gold():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
        )
    )

    exp = _experience()

    feedback = [
        _feedback("exp-real"),
        _feedback("exp-real"),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.SILVER


def test_three_successful_reuses_promote_verified_runtime_to_gold():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
        )
    )

    exp = _experience()

    feedback = [
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real"),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.GOLD


def test_failed_reuse_blocks_gold_promotion():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
        )
    )

    exp = _experience()

    feedback = [
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real", success=False),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.SILVER


def test_unused_feedback_does_not_count_as_successful_reuse():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
        )
    )

    exp = _experience()

    feedback = [
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real", used=False),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.SILVER


def test_other_experience_feedback_does_not_count():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
        )
    )

    exp = _experience()

    feedback = [
        _feedback("other"),
        _feedback("other"),
        _feedback("other"),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.SILVER


def test_synthetic_verified_fixture_never_promotes():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
        )
    )

    exp = _experience(
        problem="edit and verify",
        turn_id="turn-pm2k2-verified",
    )

    feedback = [
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real"),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.BRONZE


def test_low_confidence_blocks_gold_even_with_repeated_success():
    policy = RetentionPolicy(
        RetentionConfig(
            min_occurrences_for_pattern=3,
            gold_confidence_threshold=0.8,
        )
    )

    exp = _experience(
        confidence=0.7,
    )

    feedback = [
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real"),
        _feedback("exp-real"),
    ]

    assert policy.classify_with_feedback(
        exp,
        feedback,
    ) == policy.SILVER

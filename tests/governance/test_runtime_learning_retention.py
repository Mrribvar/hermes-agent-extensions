from governance.retention import (
    RetentionConfig,
    RetentionPolicy,
)


def _runtime_exp(
    *,
    result,
    confidence,
    verification,
    problem="real runtime task",
    turn_id="runtime-turn-1",
):
    return {
        "id": "exp-1",
        "timestamp": "2026-08-12T20:00:00",
        "problem": problem,
        "result": result,
        "confidence": confidence,
        "lessons_learned": ["lesson"],
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


def test_verified_high_confidence_runtime_is_gold():
    policy = RetentionPolicy(
        RetentionConfig(
            gold_confidence_threshold=0.8
        )
    )

    exp = _runtime_exp(
        result="successful",
        confidence=0.95,
        verification="VERIFIED",
    )

    assert policy.classify(exp) == policy.GOLD
    assert policy.is_gold(exp) is True


def test_verified_low_confidence_runtime_is_silver():
    policy = RetentionPolicy(RetentionConfig())

    exp = _runtime_exp(
        result="successful",
        confidence=0.6,
        verification="VERIFIED",
    )

    assert policy.classify(exp) == policy.SILVER
    assert policy.is_gold(exp) is False


def test_unverified_runtime_is_bronze_even_with_lessons():
    policy = RetentionPolicy(RetentionConfig())

    exp = _runtime_exp(
        result="partial",
        confidence=0.99,
        verification="UNVERIFIED",
    )

    assert policy.classify(exp) == policy.BRONZE
    assert policy.is_gold(exp) is False


def test_failed_runtime_is_silver_warning_not_gold():
    policy = RetentionPolicy(RetentionConfig())

    exp = _runtime_exp(
        result="failed",
        confidence=0.99,
        verification="FAILED",
    )

    assert policy.classify(exp) == policy.SILVER
    assert policy.is_gold(exp) is False


def test_synthetic_runtime_fixture_never_auto_promotes():
    policy = RetentionPolicy(RetentionConfig())

    exp = _runtime_exp(
        result="successful",
        confidence=1.0,
        verification="VERIFIED",
        problem="edit and verify",
        turn_id="turn-pm2k2-verified",
    )

    assert policy.classify(exp) == policy.BRONZE
    assert policy.is_gold(exp) is False


def test_legacy_high_confidence_behavior_is_preserved():
    policy = RetentionPolicy(RetentionConfig())

    exp = {
        "id": "legacy",
        "timestamp": "2026-08-01T00:00:00",
        "problem": "legacy task",
        "result": "successful",
        "confidence": 0.9,
        "lessons_learned": [],
        "tags": [],
        "metadata": {},
    }

    assert policy.classify(exp) == policy.GOLD
    assert policy.is_gold(exp) is True

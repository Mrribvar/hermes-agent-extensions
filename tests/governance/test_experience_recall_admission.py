from governance.experience_memory import (
    ExperienceMemory,
)
from governance.experience_query import (
    ExperienceRecall,
)


def test_synthetic_verified_experience_is_not_returned(
    tmp_path,
):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    memory.record(
        problem="deploy service",
        analysis="analysis",
        solution="synthetic solution",
        result="successful",
        confidence=0.99,
        metadata={
            "learning_source":
                "turn_finalizer",
            "verification_outcome":
                "VERIFIED",
            "session_id":
                "verify-budget-test",
            "turn_id":
                "verify-budget-test:abc",
        },
        record_id="synthetic-1",
    )

    recall = ExperienceRecall(
        memory=memory
    )

    result = recall.ask(
        "deploy service",
        limit=5,
    )

    assert result[
        "has_experience"
    ] is False

    assert result[
        "experiences"
    ] == []


def test_real_runtime_experience_remains_recallable(
    tmp_path,
):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    memory.record(
        problem="deploy service",
        analysis="analysis",
        solution="real solution",
        result="successful",
        confidence=0.90,
        metadata={
            "learning_source":
                "turn_finalizer",
            "verification_outcome":
                "VERIFIED",
            "session_id":
                "runtime-session",
            "turn_id":
                "runtime-turn",
        },
        record_id="runtime-1",
    )

    recall = ExperienceRecall(
        memory=memory
    )

    result = recall.ask(
        "deploy service",
        limit=5,
    )

    assert result[
        "has_experience"
    ] is True

    assert result[
        "experiences"
    ][0]["id"] == "runtime-1"


def test_legacy_experience_is_still_allowed(
    tmp_path,
):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    memory.record(
        problem="database backup",
        analysis="analysis",
        solution="legacy solution",
        result="successful",
        confidence=0.80,
        metadata={},
        record_id="legacy-1",
    )

    recall = ExperienceRecall(
        memory=memory
    )

    result = recall.ask(
        "database backup",
        limit=5,
    )

    assert result[
        "has_experience"
    ] is True

    assert result[
        "experiences"
    ][0]["id"] == "legacy-1"


def test_synthetic_cannot_beat_real_runtime(
    tmp_path,
):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    memory.record(
        problem="restart gateway",
        analysis="analysis",
        solution="synthetic",
        result="successful",
        confidence=1.0,
        metadata={
            "learning_source":
                "turn_finalizer",
            "verification_outcome":
                "VERIFIED",
            "session_id":
                "pm2f-verification-test",
            "turn_id":
                "turn-pm2k2-verified",
        },
        record_id="synthetic-1",
    )

    memory.record(
        problem="restart gateway",
        analysis="analysis",
        solution="runtime",
        result="partial",
        confidence=0.25,
        metadata={
            "learning_source":
                "turn_finalizer",
            "verification_outcome":
                "UNVERIFIED",
            "session_id":
                "runtime-session",
            "turn_id":
                "runtime-turn",
        },
        record_id="runtime-1",
    )

    recall = ExperienceRecall(
        memory=memory
    )

    result = recall.ask(
        "restart gateway",
        limit=5,
    )

    ids = [
        row["id"]
        for row in result[
            "experiences"
        ]
    ]

    assert "synthetic-1" not in ids
    assert "runtime-1" in ids

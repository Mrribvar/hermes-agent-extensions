from governance.experience_feedback import (
    ExperienceFeedbackStore,
    FeedbackRecord,
)
from governance.experience_memory import ExperienceMemory
from governance.experience_retention_runtime import (
    ExperienceRetentionRuntime,
)
from governance.retention import RetentionConfig


def _record(
    memory,
    *,
    record_id,
    result,
    confidence,
    verification,
    problem="real task",
    turn_id="runtime-real",
):
    return memory.record(
        problem=problem,
        analysis="analysis",
        solution="solution",
        result=result,
        confidence=confidence,
        lessons_learned=["lesson"],
        tags=[
            "runtime_learning",
            "verification",
        ],
        metadata={
            "learning_source": "turn_finalizer",
            "verification_outcome": verification,
            "turn_id": turn_id,
        },
        record_id=record_id,
    )


def test_runtime_plan_is_dry_run(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(tmp_path / "feedback")
    )

    _record(
        memory,
        record_id="exp-1",
        result="successful",
        confidence=0.95,
        verification="VERIFIED",
    )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=RetentionConfig(),
    )

    plan = runtime.build_plan()

    assert plan["dry_run"] is True
    assert plan["total_experiences"] == 1
    assert len(plan["experiences"]) == 1

    # Building a plan must not mutate memory.
    assert memory.get("exp-1") is not None


def test_repeated_success_can_be_effective_gold(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(tmp_path / "feedback")
    )

    _record(
        memory,
        record_id="exp-real",
        result="successful",
        confidence=0.95,
        verification="VERIFIED",
    )

    for index in range(3):
        feedback.record(
            FeedbackRecord(
                task_id=f"turn-{index}",
                experience_id="exp-real",
                recommendation_used=True,
                before_result="success",
                after_result="success",
                success=True,
                impact_score=0.5,
            )
        )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=RetentionConfig(
            min_occurrences_for_pattern=3,
        ),
    )

    plan = runtime.build_plan()
    row = plan["experiences"][0]

    assert row["effective_tier"] == "GOLD"
    assert row["archive_candidate"] is False
    assert row["delete_candidate"] is False


def test_unverified_runtime_is_not_gold(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(tmp_path / "feedback")
    )

    _record(
        memory,
        record_id="exp-u",
        result="partial",
        confidence=0.99,
        verification="UNVERIFIED",
    )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=RetentionConfig(),
    )

    plan = runtime.build_plan()
    row = plan["experiences"][0]

    assert row["effective_tier"] == "BRONZE"
    assert row["archive_candidate"] is True


def test_synthetic_verified_fixture_remains_bronze(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(tmp_path / "feedback")
    )

    _record(
        memory,
        record_id="exp-fixture",
        result="successful",
        confidence=1.0,
        verification="VERIFIED",
        problem="edit and verify",
        turn_id="turn-pm-fixture",
    )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=RetentionConfig(),
    )

    row = runtime.build_plan()["experiences"][0]

    assert row["effective_tier"] == "BRONZE"

from governance.experience_feedback import (
    ExperienceFeedbackStore,
)
from governance.experience_memory import (
    ExperienceMemory,
)
from governance.experience_retention_runtime import (
    ExperienceRetentionRuntime,
    evaluate_prune_eligibility,
    write_archive_copy,
)
from governance.retention import RetentionConfig


def _runtime(tmp_path, *, max_experiences=100):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path / "experiences.json"
        )
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(
            tmp_path / "feedback"
        )
    )

    config = RetentionConfig(
        max_experiences=max_experiences,
    )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=config,
    )

    return memory, runtime


def _record_bronze(memory, record_id):
    memory.record(
        problem="unverified runtime task",
        analysis="analysis",
        solution="solution",
        result="partial",
        confidence=0.25,
        lessons_learned=["lesson"],
        tags=[
            "runtime_learning",
            "verification",
        ],
        metadata={
            "learning_source": "turn_finalizer",
            "verification_outcome": "UNVERIFIED",
            "turn_id": f"runtime-{record_id}",
        },
        record_id=record_id,
    )


def test_not_delete_candidate_is_never_eligible(tmp_path):
    memory, runtime = _runtime(
        tmp_path
    )

    _record_bronze(
        memory,
        "exp-1",
    )

    plan = runtime.build_plan()

    archive_dir = tmp_path / "archives"

    write_archive_copy(
        plan,
        archive_dir=archive_dir,
        memory=memory,
    )

    result = evaluate_prune_eligibility(
        plan,
        archive_dir=archive_dir,
    )

    row = result["experiences"][0]

    assert row["delete_candidate"] is False
    assert row["eligible"] is False
    assert row["reason"] == "not_delete_candidate"


def test_delete_candidate_requires_valid_archive(tmp_path):
    memory, runtime = _runtime(
        tmp_path,
        max_experiences=100,
    )

    _record_bronze(
        memory,
        "exp-1",
    )

    plan = runtime.build_plan()

    # Force only the planner condition under test.
    plan["experiences"][0][
        "delete_candidate"
    ] = True

    result = evaluate_prune_eligibility(
        plan,
        archive_dir=tmp_path / "archives",
    )

    row = result["experiences"][0]

    assert row["eligible"] is False
    assert row["archive_validated"] is False
    assert row["reason"].startswith(
        "archive_validation_failed:"
    )


def test_valid_archived_delete_candidate_becomes_eligible(tmp_path):
    memory, runtime = _runtime(
        tmp_path
    )

    _record_bronze(
        memory,
        "exp-1",
    )

    plan = runtime.build_plan()

    plan["experiences"][0][
        "delete_candidate"
    ] = True

    archive_dir = tmp_path / "archives"

    write_archive_copy(
        plan,
        archive_dir=archive_dir,
        memory=memory,
    )

    result = evaluate_prune_eligibility(
        plan,
        archive_dir=archive_dir,
    )

    row = result["experiences"][0]

    assert row["eligible"] is True
    assert row["archive_validated"] is True
    assert row["reason"] == "eligible"


def test_gold_is_never_prune_eligible_even_if_flagged(tmp_path):
    _memory, runtime = _runtime(
        tmp_path
    )

    plan = {
        "experiences": [
            {
                "id": "exp-gold",
                "effective_tier": "GOLD",
                "delete_candidate": True,
            }
        ]
    }

    result = evaluate_prune_eligibility(
        plan,
        archive_dir=tmp_path / "archives",
    )

    row = result["experiences"][0]

    assert row["eligible"] is False
    assert row["reason"] == "gold_protected"

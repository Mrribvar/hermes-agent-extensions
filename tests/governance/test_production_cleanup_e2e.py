from pathlib import Path

from governance.experience_feedback import (
    ExperienceFeedbackStore,
)
from governance.experience_memory import (
    ExperienceMemory,
)
from governance.experience_retention_runtime import (
    ExperienceRetentionRuntime,
    evaluate_prune_eligibility,
    load_archived_experience,
    prune_eligible_experiences,
    restore_archived_experience,
    write_archive_copy,
)
from governance.retention import RetentionConfig


def _bronze(memory, record_id):
    memory.record(
        problem=f"unverified runtime {record_id}",
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


def test_full_archive_prune_reload_restore_cycle(tmp_path):
    source_path = tmp_path / "experiences.json"

    memory = ExperienceMemory(
        storage_path=str(source_path)
    )

    # Enough BRONZE rows to force delete candidates under the test limits.
    for index in range(6):
        _bronze(
            memory,
            f"exp-{index}",
        )

    feedback = ExperienceFeedbackStore(
        data_dir=str(tmp_path / "feedback")
    )

    # Construct a valid production-shaped config first.
    # The sandbox then lowers the limit explicitly so delete candidates
    # can be exercised without weakening RetentionConfig validation.
    config = RetentionConfig(
        max_experiences=100,
        max_age_days=1,
    )

    config.max_experiences = 3

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=config,
    )

    plan = runtime.build_plan()

    assert plan["total_experiences"] == 6
    assert plan["delete_candidates"] > 0

    archive_dir = tmp_path / "archives"

    archive_result = write_archive_copy(
        plan,
        archive_dir=archive_dir,
        memory=memory,
    )

    assert archive_result["written"] is True
    assert archive_result["validated"] is True

    eligibility = evaluate_prune_eligibility(
        plan,
        archive_dir=archive_dir,
    )

    assert eligibility["eligible_count"] > 0

    eligible_ids = [
        row["id"]
        for row in eligibility["experiences"]
        if row["eligible"]
    ]

    assert eligible_ids

    before_count = len(
        memory.get_all()
    )

    prune_result = prune_eligible_experiences(
        eligibility,
        memory=memory,
        execute=True,
    )

    assert prune_result["pruned_count"] > 0

    after_count = len(
        memory.get_all()
    )

    assert after_count < before_count

    # Disk reload must observe the same deletion.
    reloaded = ExperienceMemory(
        storage_path=str(source_path)
    )

    assert len(reloaded.get_all()) == after_count

    pruned_id = eligible_ids[0]

    assert reloaded.get(pruned_id) is None

    loaded = load_archived_experience(
        pruned_id,
        archive_dir=archive_dir,
    )

    assert loaded["validated"] is True
    assert loaded["experience"]["id"] == pruned_id

    restored = restore_archived_experience(
        pruned_id,
        target_memory=reloaded,
        archive_dir=archive_dir,
    )

    assert restored["restored"] is True
    assert reloaded.get(pruned_id) is not None

    # And persistence must survive another reload.
    restored_reload = ExperienceMemory(
        storage_path=str(source_path)
    )

    assert restored_reload.get(
        pruned_id
    ) is not None

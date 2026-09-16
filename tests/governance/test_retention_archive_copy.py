import json

from governance.experience_memory import ExperienceMemory
from governance.experience_retention_runtime import (
    ExperienceRetentionRuntime,
    write_archive_copy,
)
from governance.experience_feedback import ExperienceFeedbackStore
from governance.retention import RetentionConfig


def test_archive_copy_writes_candidates_without_mutating_memory(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path / "experiences.json"
        )
    )

    memory.record(
        problem="unverified task",
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
            "turn_id": "runtime-real",
        },
        record_id="exp-u",
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(tmp_path / "feedback")
    )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=RetentionConfig(),
    )

    plan = runtime.build_plan()

    before = [
        row.to_dict()
        for row in memory.get_all()
    ]

    result = write_archive_copy(
        plan,
        archive_dir=tmp_path / "archives",
        memory=memory,
    )

    after = [
        row.to_dict()
        for row in memory.get_all()
    ]

    assert result["written"] is True
    assert result["validated"] is True
    assert result["record_count"] == 1
    assert result["active_store_mutated"] is False
    assert before == after

    archive = json.loads(
        open(
            result["archive_path"],
            encoding="utf-8",
        ).read()
    )

    assert len(archive) == 1
    assert archive[0]["id"] == "exp-u"


def test_no_candidates_produces_no_archive(tmp_path):
    result = write_archive_copy(
        {
            "experiences": [],
        },
        archive_dir=tmp_path / "archives",
    )

    assert result["written"] is False
    assert result["record_count"] == 0
    assert result["validated"] is True

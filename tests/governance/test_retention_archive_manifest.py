import json

from governance.experience_feedback import (
    ExperienceFeedbackStore,
)
from governance.experience_memory import (
    ExperienceMemory,
)
from governance.experience_retention_runtime import (
    ExperienceRetentionRuntime,
    write_archive_copy,
)
from governance.retention import (
    RetentionConfig,
)


def _runtime(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path / "experiences.json"
        )
    )

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
            "turn_id": "runtime-real",
        },
        record_id="exp-u",
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(
            tmp_path / "feedback"
        )
    )

    runtime = ExperienceRetentionRuntime(
        memory=memory,
        feedback_store=feedback,
        config=RetentionConfig(),
    )

    return memory, runtime


def test_second_identical_archive_is_skipped(tmp_path):
    memory, runtime = _runtime(
        tmp_path
    )

    plan = runtime.build_plan()

    archive_dir = (
        tmp_path / "archives"
    )

    first = write_archive_copy(
        plan,
        archive_dir=archive_dir,
        memory=memory,
    )

    second = write_archive_copy(
        plan,
        archive_dir=archive_dir,
        memory=memory,
    )

    assert first["written"] is True
    assert first["record_count"] == 1

    assert second["written"] is False
    assert second["record_count"] == 0
    assert (
        second["skipped_already_archived"]
        >= 1
    )


def test_manifest_tracks_archive_and_checksum(tmp_path):
    memory, runtime = _runtime(
        tmp_path
    )

    result = write_archive_copy(
        runtime.build_plan(),
        archive_dir=tmp_path / "archives",
        memory=memory,
    )

    manifest = json.loads(
        open(
            result["manifest_path"],
            encoding="utf-8",
        ).read()
    )

    row = manifest[
        "experiences"
    ]["exp-u"]

    assert row["archive_path"]
    assert len(row["sha256"]) == 64
    assert row["archived_at"]


def test_changed_record_can_be_rearchived(tmp_path):
    memory, runtime = _runtime(
        tmp_path
    )

    archive_dir = (
        tmp_path / "archives"
    )

    first = write_archive_copy(
        runtime.build_plan(),
        archive_dir=archive_dir,
        memory=memory,
    )

    memory.update_confidence(
        "exp-u",
        0.30,
    )

    second = write_archive_copy(
        runtime.build_plan(),
        archive_dir=archive_dir,
        memory=memory,
    )

    assert first["written"] is True
    assert second["written"] is True
    assert second["record_count"] == 1
    assert (
        second["archive_path"]
        != first["archive_path"]
    )

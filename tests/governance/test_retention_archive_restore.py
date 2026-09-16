from pathlib import Path

import pytest

from governance.experience_feedback import (
    ExperienceFeedbackStore,
)
from governance.experience_memory import (
    ExperienceMemory,
)
from governance.experience_retention_runtime import (
    ExperienceRetentionRuntime,
    load_archived_experience,
    restore_archived_experience,
    write_archive_copy,
)
from governance.retention import RetentionConfig


def _prepare_archive(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path / "source.json"
        )
    )

    memory.record(
        problem="restore me",
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
        record_id="exp-restore",
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

    archive_dir = tmp_path / "archives"

    result = write_archive_copy(
        runtime.build_plan(),
        archive_dir=archive_dir,
        memory=memory,
    )

    assert result["written"] is True

    return memory, archive_dir


def test_load_archived_experience_validates_checksum(tmp_path):
    _memory, archive_dir = _prepare_archive(
        tmp_path
    )

    result = load_archived_experience(
        "exp-restore",
        archive_dir=archive_dir,
    )

    assert result["validated"] is True
    assert result["experience"]["id"] == "exp-restore"
    assert len(result["sha256"]) == 64


def test_restore_goes_only_to_explicit_target_memory(tmp_path):
    source, archive_dir = _prepare_archive(
        tmp_path
    )

    target = ExperienceMemory(
        storage_path=str(
            tmp_path / "target.json"
        )
    )

    source_before = [
        row.to_dict()
        for row in source.get_all()
    ]

    result = restore_archived_experience(
        "exp-restore",
        target_memory=target,
        archive_dir=archive_dir,
    )

    source_after = [
        row.to_dict()
        for row in source.get_all()
    ]

    assert result["restored"] is True
    assert target.get("exp-restore") is not None
    assert source_before == source_after


def test_restore_is_idempotent(tmp_path):
    _source, archive_dir = _prepare_archive(
        tmp_path
    )

    target = ExperienceMemory(
        storage_path=str(
            tmp_path / "target.json"
        )
    )

    first = restore_archived_experience(
        "exp-restore",
        target_memory=target,
        archive_dir=archive_dir,
    )

    second = restore_archived_experience(
        "exp-restore",
        target_memory=target,
        archive_dir=archive_dir,
    )

    assert first["restored"] is True
    assert second["restored"] is False
    assert second["already_present"] is True


def test_checksum_tampering_is_rejected(tmp_path):
    _source, archive_dir = _prepare_archive(
        tmp_path
    )

    manifest = (
        archive_dir / "manifest.json"
    )

    import json

    data = json.loads(
        manifest.read_text(
            encoding="utf-8"
        )
    )

    archive_path = Path(
        data["experiences"][
            "exp-restore"
        ]["archive_path"]
    )

    archive_data = json.loads(
        archive_path.read_text(
            encoding="utf-8"
        )
    )

    archive_data[0][
        "solution"
    ] = "tampered"

    archive_path.write_text(
        json.dumps(
            archive_data,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="checksum mismatch",
    ):
        load_archived_experience(
            "exp-restore",
            archive_dir=archive_dir,
        )

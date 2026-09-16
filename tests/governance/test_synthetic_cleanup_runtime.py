import json
from pathlib import Path

from governance.experience_feedback import (
    ExperienceFeedbackStore,
    FeedbackRecord,
)
from governance.experience_memory import (
    ExperienceMemory,
)
from governance.experience_retention_runtime import (
    cleanup_synthetic_experiences,
    plan_synthetic_experience_cleanup,
)


def _synthetic(
    memory,
    record_id,
):
    memory.record(
        problem="fixture",
        analysis="analysis",
        solution="solution",
        result="partial",
        confidence=0.25,
        metadata={
            "learning_source":
                "turn_finalizer",
            "verification_outcome":
                "UNVERIFIED",
            "session_id":
                "verify-budget-test",
            "turn_id":
                f"verify-budget-test:{record_id}",
        },
        record_id=record_id,
    )


def _runtime(
    memory,
    record_id,
):
    memory.record(
        problem="real runtime",
        analysis="analysis",
        solution="solution",
        result="successful",
        confidence=0.9,
        metadata={
            "learning_source":
                "turn_finalizer",
            "verification_outcome":
                "VERIFIED",
            "session_id":
                "runtime-session",
            "turn_id":
                f"runtime:{record_id}",
        },
        record_id=record_id,
    )


def _archive(
    archive_dir,
    experience_id,
):
    archive_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    row = {
        "id":
            experience_id,
        "timestamp":
            "2026-01-01T00:00:00",
        "problem":
            "fixture",
        "analysis":
            "analysis",
        "solution":
            "solution",
        "result":
            "partial",
        "lessons_learned":
            [],
        "confidence":
            0.25,
        "future_recommendation":
            "",
        "related_decision_id":
            "",
        "related_project":
            "",
        "tags":
            [],
        "metadata":
            {
                "learning_source":
                    "turn_finalizer",
                "verification_outcome":
                    "UNVERIFIED",
                "session_id":
                    "verify-budget-test",
                "turn_id":
                    f"verify-budget-test:{experience_id}",
            },
    }

    archive_path = (
        archive_dir
        / f"{experience_id}.json"
    )

    archive_path.write_text(
        json.dumps(
            [row],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    import hashlib

    canonical = json.dumps(
        row,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    digest = hashlib.sha256(
        canonical
    ).hexdigest()

    manifest = {
        "version": 1,
        "experiences": {
            experience_id: {
                "archive_path":
                    str(archive_path),
                "sha256":
                    digest,
                "archived_at":
                    "2026-01-01T00:00:00",
            }
        }
    }

    (
        archive_dir
        / "manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_cleanup_plan_is_read_only(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(
            tmp_path
            / "feedback"
        )
    )

    _synthetic(
        memory,
        "synthetic-1",
    )

    _runtime(
        memory,
        "runtime-1",
    )

    archive_dir = (
        tmp_path
        / "archives"
    )

    _archive(
        archive_dir,
        "synthetic-1",
    )

    before = (
        tmp_path
        / "experiences.json"
    ).read_bytes()

    plan = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    after = (
        tmp_path
        / "experiences.json"
    ).read_bytes()

    assert before == after

    assert plan[
        "synthetic_count"
    ] == 1

    assert plan[
        "eligible_count"
    ] == 1


def test_cleanup_defaults_to_dry_run(
    tmp_path,
):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(
            tmp_path
            / "feedback"
        )
    )

    _synthetic(
        memory,
        "synthetic-1",
    )

    archive_dir = (
        tmp_path
        / "archives"
    )

    _archive(
        archive_dir,
        "synthetic-1",
    )

    plan = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    result = (
        cleanup_synthetic_experiences(
            plan,
            memory=memory,
        )
    )

    assert result["dry_run"] is True
    assert result["removed_count"] == 0

    assert (
        memory.get(
            "synthetic-1"
        )
        is not None
    )


def test_cleanup_execute_removes_only_eligible(
    tmp_path,
):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path
            / "experiences.json"
        )
    )

    feedback = ExperienceFeedbackStore(
        data_dir=str(
            tmp_path
            / "feedback"
        )
    )

    _synthetic(
        memory,
        "remove-me",
    )

    _synthetic(
        memory,
        "protected",
    )

    _runtime(
        memory,
        "runtime",
    )

    feedback.record(
        FeedbackRecord(
            task_id="task-1",
            experience_id="protected",
            recommendation_used=True,
            before_result="unknown",
            after_result="success",
            success=True,
            impact_score=0.5,
        )
    )

    archive_dir = (
        tmp_path
        / "archives"
    )

    _archive(
        archive_dir,
        "remove-me",
    )

    plan = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    result = (
        cleanup_synthetic_experiences(
            plan,
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
            execute=True,
        )
    )

    assert result["dry_run"] is False
    assert result["removed_count"] == 1

    assert memory.get(
        "remove-me"
    ) is None

    assert memory.get(
        "protected"
    ) is not None

    assert memory.get(
        "runtime"
    ) is not None


def test_stale_plan_skips_when_feedback_added(
    tmp_path,
):
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

    _synthetic(
        memory,
        "candidate",
    )

    archive_dir = (
        tmp_path / "archives"
    )

    _archive(
        archive_dir,
        "candidate",
    )

    plan = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    assert plan[
        "eligible_count"
    ] == 1

    feedback.record(
        FeedbackRecord(
            task_id="late-feedback",
            experience_id="candidate",
            recommendation_used=True,
            before_result="unknown",
            after_result="success",
            success=True,
            impact_score=0.5,
        )
    )

    result = (
        cleanup_synthetic_experiences(
            plan,
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
            execute=True,
        )
    )

    assert result[
        "removed_count"
    ] == 0

    assert result[
        "skipped_stale_count"
    ] == 1

    assert memory.get(
        "candidate"
    ) is not None


def test_cleanup_is_idempotent_after_removal(
    tmp_path,
):
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

    _synthetic(
        memory,
        "candidate",
    )

    archive_dir = (
        tmp_path / "archives"
    )

    _archive(
        archive_dir,
        "candidate",
    )

    plan = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    first = (
        cleanup_synthetic_experiences(
            plan,
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
            execute=True,
        )
    )

    second = (
        cleanup_synthetic_experiences(
            plan,
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
            execute=True,
        )
    )

    assert first[
        "removed_count"
    ] == 1

    assert second[
        "removed_count"
    ] == 0

    assert second[
        "skipped_stale_count"
    ] == 1


def test_cleanup_plan_has_stable_fingerprint(
    tmp_path,
):
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

    _synthetic(
        memory,
        "candidate",
    )

    archive_dir = (
        tmp_path / "archives"
    )

    _archive(
        archive_dir,
        "candidate",
    )

    first = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    second = (
        plan_synthetic_experience_cleanup(
            memory=memory,
            feedback_store=feedback,
            archive_dir=archive_dir,
        )
    )

    assert (
        first["plan_fingerprint"]
        == second["plan_fingerprint"]
    )

    assert len(
        first["plan_fingerprint"]
    ) == 64

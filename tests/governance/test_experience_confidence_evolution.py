from governance.experience_feedback import ExperienceFeedbackEvaluator
from governance.experience_memory import ExperienceMemory


def test_memory_updates_confidence_and_persists(tmp_path):
    path = tmp_path / "experiences.json"

    memory = ExperienceMemory(storage_path=str(path))

    record = memory.record(
        problem="p",
        analysis="a",
        solution="s",
        confidence=0.5,
        record_id="exp-1",
    )

    updated = memory.update_confidence(
        record.id,
        0.8,
    )

    assert updated is not None
    assert updated.confidence == 0.8

    reloaded = ExperienceMemory(storage_path=str(path))

    assert reloaded.get("exp-1").confidence == 0.8


def test_confidence_is_bounded(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    memory.record(
        problem="p",
        analysis="a",
        solution="s",
        record_id="exp-1",
    )

    assert memory.update_confidence(
        "exp-1", 4.0
    ).confidence == 1.0

    assert memory.update_confidence(
        "exp-1", -2.0
    ).confidence == 0.0


def test_successful_used_recommendation_increases_confidence():
    new_value = ExperienceFeedbackEvaluator.evolve_confidence(
        0.70,
        recommendation_used=True,
        success=True,
        impact_score=1.0,
    )

    assert new_value > 0.70
    assert new_value <= 1.0


def test_failed_used_recommendation_decreases_confidence():
    new_value = ExperienceFeedbackEvaluator.evolve_confidence(
        0.90,
        recommendation_used=True,
        success=False,
        impact_score=-0.5,
    )

    assert new_value < 0.90
    assert new_value >= 0.0


def test_unused_recommendation_does_not_change_confidence():
    new_value = ExperienceFeedbackEvaluator.evolve_confidence(
        0.65,
        recommendation_used=False,
        success=False,
        impact_score=-1.0,
    )

    assert new_value == 0.65

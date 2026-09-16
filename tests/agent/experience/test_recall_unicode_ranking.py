from governance.experience_index import ExperienceIndex
from governance.experience_memory import ExperienceMemory
from governance.experience_query import ExperienceRecall


def _record(
    memory,
    *,
    record_id,
    problem,
    result,
    confidence,
    verification,
    turn_id,
):
    return memory.record(
        problem=problem,
        analysis="analysis",
        solution=f"solution-{record_id}",
        result=result,
        confidence=confidence,
        lessons_learned=["lesson"],
        metadata={
            "verification_outcome": verification,
            "learning_source": "turn_finalizer",
            "turn_id": turn_id,
        },
        record_id=record_id,
    )


def test_unicode_keyword_search_matches_persian(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="exp-fa",
        problem="بهترین روش تست بعد از تغییر کد در هرمس",
        result="successful",
        confidence=0.9,
        verification="VERIFIED",
        turn_id="runtime-real",
    )

    index = ExperienceIndex(memory)
    index.rebuild()

    rows = index.search_keywords("تست تغییر کد", limit=5)

    assert rows
    assert rows[0]["id"] == "exp-fa"


def test_verified_success_beats_failed_high_confidence_fixture(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="exp-failed-fixture",
        problem="test pytest verification",
        result="failed",
        confidence=0.99,
        verification="FAILED",
        turn_id="turn-pm2f",
    )

    _record(
        memory,
        record_id="exp-real-success",
        problem="روش تست بعد از تغییر کد با pytest",
        result="successful",
        confidence=0.9,
        verification="VERIFIED",
        turn_id="runtime-real-turn",
    )

    recall = ExperienceRecall(memory)
    result = recall.ask("روش تست تغییر کد pytest", limit=2)

    assert result["has_experience"] is True
    assert result["experiences"][0]["id"] == "exp-real-success"
    assert result["experiences"][0]["result"] == "success"


def test_unverified_can_be_recalled_but_not_beat_verified_success(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="exp-unverified",
        problem="تست تغییر کد pytest",
        result="partial",
        confidence=0.99,
        verification="UNVERIFIED",
        turn_id="runtime-unverified",
    )

    _record(
        memory,
        record_id="exp-verified",
        problem="تست تغییر کد pytest",
        result="successful",
        confidence=0.8,
        verification="VERIFIED",
        turn_id="runtime-verified",
    )

    recall = ExperienceRecall(memory)
    result = recall.ask("تست تغییر کد pytest", limit=2)

    assert result["experiences"][0]["id"] == "exp-verified"
    assert result["experiences"][1]["id"] == "exp-unverified"

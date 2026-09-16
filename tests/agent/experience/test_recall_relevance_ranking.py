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
    memory.record(
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


def test_relevance_beats_generic_verified_fixture(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="generic-verified",
        problem="edit and verify",
        result="successful",
        confidence=0.99,
        verification="VERIFIED",
        turn_id="turn-pm-fixture",
    )

    _record(
        memory,
        record_id="specific-runtime",
        problem="بهترین روش تست بعد از تغییر کد در Hermes با pytest",
        result="successful",
        confidence=0.85,
        verification="VERIFIED",
        turn_id="runtime-real",
    )

    recall = ExperienceRecall(memory)

    result = recall.ask(
        "بهترین روش تست بعد از تغییر کد در Hermes چیست؟",
        limit=2,
    )

    assert result["experiences"][0]["id"] == "specific-runtime"


def test_verified_wins_when_relevance_is_equal(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="unverified",
        problem="pytest تست تغییر کد",
        result="partial",
        confidence=0.99,
        verification="UNVERIFIED",
        turn_id="runtime-u",
    )

    _record(
        memory,
        record_id="verified",
        problem="pytest تست تغییر کد",
        result="successful",
        confidence=0.80,
        verification="VERIFIED",
        turn_id="runtime-v",
    )

    recall = ExperienceRecall(memory)

    result = recall.ask(
        "pytest تست تغییر کد",
        limit=2,
    )

    assert result["experiences"][0]["id"] == "verified"


def test_scored_search_exposes_keyword_relevance(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="one",
        problem="pytest تغییر کد",
        result="successful",
        confidence=0.8,
        verification="VERIFIED",
        turn_id="real-1",
    )

    _record(
        memory,
        record_id="two",
        problem="pytest تست تغییر کد Hermes",
        result="successful",
        confidence=0.8,
        verification="VERIFIED",
        turn_id="real-2",
    )

    recall = ExperienceRecall(memory)

    rows = recall.index.search_keywords_scored(
        "pytest تست تغییر کد Hermes",
        limit=5,
    )

    assert rows
    assert rows[0][0]["id"] == "two"
    assert rows[0][1] > rows[1][1]


def test_unverified_higher_relevance_cannot_beat_verified_success(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    _record(
        memory,
        record_id="unverified-more-relevant",
        problem="بهترین روش تست بعد از تغییر کد در Hermes pytest",
        result="partial",
        confidence=0.99,
        verification="UNVERIFIED",
        turn_id="runtime-unverified",
    )

    _record(
        memory,
        record_id="verified-less-relevant",
        problem="تست تغییر کد",
        result="successful",
        confidence=0.80,
        verification="VERIFIED",
        turn_id="runtime-verified",
    )

    recall = ExperienceRecall(memory)

    result = recall.ask(
        "بهترین روش تست بعد از تغییر کد در Hermes چیست؟",
        limit=2,
    )

    assert result["experiences"][0]["id"] == "verified-less-relevant"

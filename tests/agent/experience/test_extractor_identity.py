from agent.experience.evaluator import EvaluationResult
from agent.experience.extractor import ExperienceExtractor
from agent.experience.listener import ExecutionRecordProxy
from governance.experience_memory import ExperienceMemory


def _proxy(execution_id="exec-001"):
    return ExecutionRecordProxy(
        execution_id=execution_id,
        task_id="task-1",
        project_id="project-1",
        tool_id="write_file",
        state="COMPLETED",
        governance_verdict="allowed",
        started_at=None,
        completed_at=None,
        duration_ms=1,
        result_status="success",
        error_message=None,
        metadata={},
    )


def _evaluation():
    return EvaluationResult(
        outcome="success",
        cause_hint="none",
        lesson_candidates=["successful_pattern_retain"],
    )


def test_extractor_uses_stable_execution_identity(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )
    extractor = ExperienceExtractor(memory=memory)

    first = extractor.extract_and_store(
        _evaluation(),
        _proxy("abc123"),
        problem_text="test",
    )

    second = extractor.extract_and_store(
        _evaluation(),
        _proxy("abc123"),
        problem_text="test",
    )

    assert first.id == "exp_abc123"
    assert second.id == "exp_abc123"
    assert len(memory.get_all()) == 1


def test_record_id_is_optional_and_backward_compatible(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(tmp_path / "experiences.json")
    )

    record = memory.record(
        problem="p",
        analysis="a",
        solution="s",
    )

    assert record.id.startswith("exp_")
    assert memory.get(record.id) is record

from governance.experience_memory import ExperienceMemory
from governance.experience_retention_runtime import (
    prune_eligible_experiences,
)


def _memory(tmp_path):
    memory = ExperienceMemory(
        storage_path=str(
            tmp_path / "experiences.json"
        )
    )

    memory.record(
        problem="candidate",
        analysis="analysis",
        solution="solution",
        result="partial",
        confidence=0.25,
        record_id="exp-1",
    )

    return memory


def _eligibility(
    *,
    eligible=True,
    tier="BRONZE",
):
    return {
        "experiences": [
            {
                "id": "exp-1",
                "effective_tier": tier,
                "eligible": eligible,
            }
        ]
    }


def test_remove_api_persists_deletion(tmp_path):
    memory = _memory(tmp_path)

    removed = memory.remove(
        "exp-1"
    )

    assert removed is not None
    assert memory.get("exp-1") is None

    reloaded = ExperienceMemory(
        storage_path=str(
            tmp_path / "experiences.json"
        )
    )

    assert reloaded.get("exp-1") is None


def test_dry_run_never_removes(tmp_path):
    memory = _memory(tmp_path)

    result = prune_eligible_experiences(
        _eligibility(),
        memory=memory,
        execute=False,
    )

    assert result["dry_run"] is True
    assert result["pruned_count"] == 0
    assert (
        result["experiences"][0]["action"]
        == "would_prune"
    )

    assert memory.get("exp-1") is not None


def test_execute_removes_eligible_non_gold(tmp_path):
    memory = _memory(tmp_path)

    result = prune_eligible_experiences(
        _eligibility(),
        memory=memory,
        execute=True,
    )

    assert result["dry_run"] is False
    assert result["pruned_count"] == 1
    assert (
        result["experiences"][0]["action"]
        == "pruned"
    )

    assert memory.get("exp-1") is None


def test_noneligible_record_is_never_removed(tmp_path):
    memory = _memory(tmp_path)

    result = prune_eligible_experiences(
        _eligibility(
            eligible=False,
        ),
        memory=memory,
        execute=True,
    )

    assert result["pruned_count"] == 0
    assert (
        result["experiences"][0]["action"]
        == "not_eligible"
    )

    assert memory.get("exp-1") is not None


def test_gold_is_defensively_protected(tmp_path):
    memory = _memory(tmp_path)

    result = prune_eligible_experiences(
        _eligibility(
            eligible=True,
            tier="GOLD",
        ),
        memory=memory,
        execute=True,
    )

    assert result["pruned_count"] == 0
    assert (
        result["experiences"][0]["action"]
        == "gold_protected"
    )

    assert memory.get("exp-1") is not None


def test_missing_record_is_idempotent(tmp_path):
    memory = _memory(tmp_path)

    memory.remove("exp-1")

    result = prune_eligible_experiences(
        _eligibility(),
        memory=memory,
        execute=True,
    )

    assert result["pruned_count"] == 0
    assert (
        result["experiences"][0]["action"]
        == "already_absent"
    )

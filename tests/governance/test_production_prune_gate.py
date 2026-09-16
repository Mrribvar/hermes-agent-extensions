from unittest.mock import patch

from governance.experience_memory import ExperienceMemory
from governance.experience_retention_runtime import (
    production_prune_enabled,
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


def _eligibility():
    return {
        "experiences": [
            {
                "id": "exp-1",
                "effective_tier": "BRONZE",
                "eligible": True,
            }
        ]
    }


def test_production_prune_gate_defaults_off():
    with patch.dict(
        "os.environ",
        {},
        clear=False,
    ):
        import os

        os.environ.pop(
            "HERMES_EXPERIENCE_PRUNE_EXECUTE",
            None,
        )

        assert production_prune_enabled() is False


def test_production_prune_gate_accepts_explicit_true():
    with patch.dict(
        "os.environ",
        {
            "HERMES_EXPERIENCE_PRUNE_EXECUTE":
                "true",
        },
    ):
        assert production_prune_enabled() is True


def test_gate_off_keeps_real_executor_dry(tmp_path):
    memory = _memory(tmp_path)

    with patch.dict(
        "os.environ",
        {},
        clear=False,
    ):
        import os

        os.environ.pop(
            "HERMES_EXPERIENCE_PRUNE_EXECUTE",
            None,
        )

        result = prune_eligible_experiences(
            _eligibility(),
            memory=memory,
            execute=production_prune_enabled(),
        )

    assert result["dry_run"] is True
    assert result["pruned_count"] == 0
    assert memory.get("exp-1") is not None


def test_gate_on_allows_explicit_executor(tmp_path):
    memory = _memory(tmp_path)

    with patch.dict(
        "os.environ",
        {
            "HERMES_EXPERIENCE_PRUNE_EXECUTE":
                "1",
        },
    ):
        result = prune_eligible_experiences(
            _eligibility(),
            memory=memory,
            execute=production_prune_enabled(),
        )

    assert result["dry_run"] is False
    assert result["pruned_count"] == 1
    assert memory.get("exp-1") is None

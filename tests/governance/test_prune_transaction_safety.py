from unittest.mock import patch

import pytest

from governance.experience_memory import (
    ExperienceMemory,
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


def test_remove_rolls_back_memory_when_save_fails(tmp_path):
    memory = _memory(tmp_path)

    before = memory.get(
        "exp-1"
    )

    with patch.object(
        memory,
        "_save",
        side_effect=OSError(
            "simulated disk failure"
        ),
    ):
        with pytest.raises(
            OSError,
            match="simulated disk failure",
        ):
            memory.remove(
                "exp-1"
            )

    assert memory.get(
        "exp-1"
    ) is before


def test_failed_remove_does_not_change_persisted_store(tmp_path):
    memory = _memory(tmp_path)

    path = tmp_path / "experiences.json"

    before = path.read_bytes()

    original_save = memory._save

    def failing_save():
        raise OSError(
            "simulated persistence failure"
        )

    memory._save = failing_save

    with pytest.raises(OSError):
        memory.remove(
            "exp-1"
        )

    after = path.read_bytes()

    assert before == after
    assert memory.get(
        "exp-1"
    ) is not None

    memory._save = original_save


def test_successful_remove_stays_persistent(tmp_path):
    memory = _memory(tmp_path)

    removed = memory.remove(
        "exp-1"
    )

    assert removed is not None
    assert memory.get(
        "exp-1"
    ) is None

    reloaded = ExperienceMemory(
        storage_path=str(
            tmp_path / "experiences.json"
        )
    )

    assert reloaded.get(
        "exp-1"
    ) is None


def test_atomic_save_leaves_no_tmp_files(tmp_path):
    memory = _memory(tmp_path)

    memory.update_confidence(
        "exp-1",
        0.4,
    )

    leftovers = list(
        tmp_path.glob(
            ".experiences.json.*.tmp"
        )
    )

    assert leftovers == []

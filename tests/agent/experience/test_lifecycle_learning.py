import json
from unittest.mock import patch

from governance.experience_memory import ExperienceMemory

from agent.experience.lifecycle_learning import (
    _learning_classification,
    _stable_experience_id,
    observe_lifecycle,
)


def test_classification_contract():
    assert _learning_classification("VERIFIED")[:2] == (
        "successful",
        0.90,
    )

    assert _learning_classification("FAILED")[:2] == (
        "failed",
        0.90,
    )

    assert _learning_classification("UNVERIFIED")[:2] == (
        "partial",
        0.25,
    )

    assert _learning_classification("NOT_APPLICABLE") is None


def test_stable_turn_identity():
    first = _stable_experience_id(
        session_id="s1",
        turn_id="t1",
    )
    second = _stable_experience_id(
        session_id="s1",
        turn_id="t1",
    )

    assert first == second
    assert first.startswith("exp_turn_")


def test_verified_turn_persists_once(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"

    monkeypatch.setenv(
        "HERMES_HOME",
        str(hermes_home),
    )

    path = (
        hermes_home
        / "governance"
        / "experiences.json"
    )

    payload = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "task_id": "task-1",
            "completed": True,
            "failed": False,
            "interrupted": False,
            "turn_exit_reason": "text_response(finish_reason=stop)",
            "verification_outcome": "VERIFIED",
            "verification_status": [{"status": "passed"}],
            "user_message": "edit file",
            "assistant_response": "done",
            "model": "test/model",
            "platform": "telegram",
    }

    observe_lifecycle(
        "on_session_end",
        **payload,
    )

    observe_lifecycle(
        "on_session_end",
        **payload,
    )

    rows = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert len(rows) == 1
    row = rows[0]

    assert row["result"] == "successful"
    assert row["confidence"] == 0.90
    assert (
        row["metadata"]["verification_outcome"]
        == "VERIFIED"
    )


def test_unverified_turn_is_partial_low_confidence(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"

    monkeypatch.setenv(
        "HERMES_HOME",
        str(hermes_home),
    )

    path = (
        hermes_home
        / "governance"
        / "experiences.json"
    )

    observe_lifecycle(
        "on_session_end",
        session_id="session-2",
        turn_id="turn-2",
        completed=False,
        failed=False,
        interrupted=False,
        verification_outcome="UNVERIFIED",
        verification_status=None,
        user_message="edit",
        assistant_response="provisional",
    )

    row = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )[0]

    assert row["result"] == "partial"
    assert row["confidence"] == 0.25


def test_not_applicable_turn_does_not_persist(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"

    monkeypatch.setenv(
        "HERMES_HOME",
        str(hermes_home),
    )

    path = (
        hermes_home
        / "governance"
        / "experiences.json"
    )

    observe_lifecycle(
        "on_session_end",
        session_id="session-chat",
        turn_id="turn-chat",
        completed=True,
        failed=False,
        verification_outcome="NOT_APPLICABLE",
        user_message="hello",
        assistant_response="hi",
    )

    assert not path.exists()

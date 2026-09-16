import json
from unittest.mock import patch

from agent.experience.lifecycle_learning import (
    handles_hook,
    observe_lifecycle,
)


def test_learning_observer_handles_terminal_hook():
    assert handles_hook("post_tool_call") is True


def test_terminal_result_is_forwarded_to_verification_ledger():
    result = json.dumps({
        "output": "1 passed",
        "exit_code": 0,
    })

    with (
        patch(
            "tools.terminal_tool._get_env_config",
            return_value={"cwd": "/repo"},
        ),
        patch(
            "tools.terminal_tool._resolve_command_cwd",
            return_value="/repo",
        ) as resolve_cwd,
        patch(
            "agent.verification_evidence.record_terminal_result",
            return_value={
                "canonical_command": "pytest",
                "status": "passed",
                "exit_code": 0,
            },
        ) as record,
    ):
        observe_lifecycle(
            "post_tool_call",
            tool_name="terminal",
            args={
                "command": "python3 -m pytest -q",
                "workdir": None,
            },
            result=result,
            task_id="session-key",
            session_id="session-1",
        )

    resolve_cwd.assert_called_once_with(
        workdir=None,
        default_cwd="/repo",
        session_key="session-key",
    )

    record.assert_called_once_with(
        command="python3 -m pytest -q",
        cwd="/repo",
        session_id="session-1",
        exit_code=0,
        output="1 passed",
    )


def test_background_terminal_is_not_verification():
    with patch(
        "agent.verification_evidence.record_terminal_result"
    ) as record:
        observe_lifecycle(
            "post_tool_call",
            tool_name="terminal",
            args={
                "command": "pytest",
                "background": True,
            },
            result=json.dumps({
                "output": "",
                "exit_code": 0,
            }),
            task_id="x",
            session_id="s",
        )

    record.assert_not_called()

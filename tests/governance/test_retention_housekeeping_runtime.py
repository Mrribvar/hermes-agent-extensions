from unittest.mock import patch

from governance.experience_retention_runtime import (
    run_retention_housekeeping,
)


def test_housekeeping_returns_dry_run_plan():
    with patch(
        "governance.experience_retention_runtime.ExperienceRetentionRuntime.build_plan",
        return_value={
            "dry_run": True,
            "total_experiences": 4,
            "archive_candidates": 2,
            "delete_candidates": 0,
            "experiences": [],
        },
    ):
        plan = run_retention_housekeeping()

    assert plan["dry_run"] is True
    assert plan["total_experiences"] == 4
    assert plan["archive_candidates"] == 2
    assert plan["delete_candidates"] == 0

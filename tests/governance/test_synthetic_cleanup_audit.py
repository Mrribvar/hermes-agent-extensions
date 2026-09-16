import json

from governance.experience_retention_runtime import (
    write_synthetic_cleanup_audit,
)


def test_cleanup_audit_written_atomically(
    tmp_path,
):
    plan = {
        "plan_fingerprint":
            "a" * 64,
        "synthetic_count":
            3,
        "eligible_count":
            2,
    }

    result = {
        "dry_run":
            False,
        "removed_count":
            1,
        "removed_ids":
            ["exp-1"],
        "skipped_stale_count":
            1,
        "skipped_stale_ids":
            ["exp-2"],
    }

    audit_dir = (
        tmp_path
        / "audit"
    )

    written = (
        write_synthetic_cleanup_audit(
            plan=plan,
            result=result,
            audit_dir=audit_dir,
        )
    )

    assert written[
        "written"
    ] is True

    path = (
        audit_dir
        / (
            written[
                "audit_path"
            ].split("/")[-1]
        )
    )

    assert path.exists()

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert payload[
        "plan_fingerprint"
    ] == "a" * 64

    assert payload[
        "removed_ids"
    ] == ["exp-1"]

    assert payload[
        "skipped_stale_ids"
    ] == ["exp-2"]

    assert len(
        payload[
            "record_sha256"
        ]
    ) == 64


def test_cleanup_audit_dry_run_supported(
    tmp_path,
):
    plan = {
        "plan_fingerprint":
            "b" * 64,
        "synthetic_count":
            7,
        "eligible_count":
            0,
    }

    result = {
        "dry_run":
            True,
        "removed_count":
            0,
        "removed_ids":
            [],
        "skipped_stale_count":
            0,
        "skipped_stale_ids":
            [],
    }

    written = (
        write_synthetic_cleanup_audit(
            plan=plan,
            result=result,
            audit_dir=(
                tmp_path
                / "audit"
            ),
        )
    )

    assert written[
        "written"
    ] is True

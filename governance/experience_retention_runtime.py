"""Runtime retention planning for Hermes Experience Memory.

This module intentionally starts with a dry-run execution model.
It computes authoritative retention decisions without deleting data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from governance.experience_feedback import ExperienceFeedbackStore
from governance.experience_memory import ExperienceMemory
from governance.retention import RetentionConfig, RetentionPolicy


class ExperienceRetentionRuntime:
    """Evaluate real ExperienceMemory against feedback-aware retention policy."""

    def __init__(
        self,
        *,
        memory: Optional[ExperienceMemory] = None,
        feedback_store: Optional[ExperienceFeedbackStore] = None,
        config: Optional[RetentionConfig] = None,
    ):
        self.memory = memory or ExperienceMemory()
        self.feedback_store = feedback_store or ExperienceFeedbackStore()
        self.config = config or RetentionConfig.from_env()
        self.policy = RetentionPolicy(self.config)

    @staticmethod
    def _as_dict(record: Any) -> dict:
        if hasattr(record, "to_dict"):
            return record.to_dict()
        return dict(record)

    @staticmethod
    def _feedback_as_dict(record: Any) -> dict:
        if hasattr(record, "to_dict"):
            return record.to_dict()
        return dict(record)

    def build_plan(self) -> Dict[str, Any]:
        experiences = [
            self._as_dict(row)
            for row in self.memory.get_all()
        ]

        feedback = [
            self._feedback_as_dict(row)
            for row in self.feedback_store.get_all()
        ]

        current_count = len(experiences)
        rows: List[Dict[str, Any]] = []

        for exp in experiences:
            tier = self.policy.classify_with_feedback_history(
                exp,
                feedback,
            )

            base_tier = self.policy.classify(exp)

            archive_candidate = False
            delete_candidate = False

            # GOLD is always protected.
            if tier != self.policy.GOLD:
                age_days = self.policy._get_age_days(exp)

                if tier == self.policy.BRONZE:
                    archive_candidate = True

                    if current_count > self.config.max_experiences:
                        if (
                            age_days is not None
                            and age_days > self.config.max_age_days
                        ):
                            delete_candidate = True
                        elif (
                            current_count
                            > self.config.max_experiences * 1.2
                        ):
                            delete_candidate = True

                elif tier == self.policy.SILVER:
                    if (
                        age_days is not None
                        and age_days > self.config.compression_days
                    ):
                        archive_candidate = True

                    if (
                        current_count
                        > self.config.max_experiences * 2
                    ):
                        delete_candidate = True

            rows.append({
                "id": exp.get("id"),
                "base_tier": base_tier,
                "effective_tier": tier,
                "confidence": exp.get("confidence"),
                "result": exp.get("result"),
                "verification": (
                    (exp.get("metadata") or {})
                    .get("verification_outcome")
                ),
                "archive_candidate": archive_candidate,
                "delete_candidate": delete_candidate,
            })

        return {
            "dry_run": True,
            "total_experiences": current_count,
            "max_experiences": self.config.max_experiences,
            "archive_candidates": sum(
                1 for row in rows
                if row["archive_candidate"]
            ),
            "delete_candidates": sum(
                1 for row in rows
                if row["delete_candidate"]
            ),
            "experiences": rows,
        }


def write_archive_copy(
    plan: dict,
    *,
    archive_dir: Optional[Path] = None,
    memory: Optional[ExperienceMemory] = None,
) -> dict:
    """Write only not-yet-archived candidates to a validated JSON archive.

    Archive publication is copy-only and tracked by a manifest.
    ExperienceMemory is never removed or mutated here.
    """
    if archive_dir is None:
        archive_dir = (
            Path.home()
            / ".hermes"
            / "governance"
            / "archives"
        )

    archive_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = archive_dir / "manifest.json"

    if manifest_path.exists():
        try:
            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            manifest = {}
    else:
        manifest = {}

    if not isinstance(manifest, dict):
        manifest = {}

    archived = manifest.get("experiences")

    if not isinstance(archived, dict):
        archived = {}

    candidate_ids = {
        str(row.get("id"))
        for row in (plan.get("experiences") or [])
        if row.get("archive_candidate")
        and row.get("id")
    }

    memory = memory or ExperienceMemory()

    records = []

    for record in memory.get_all():
        row = (
            record.to_dict()
            if hasattr(record, "to_dict")
            else dict(record)
        )

        experience_id = str(
            row.get("id") or ""
        )

        if experience_id not in candidate_ids:
            continue

        canonical = json.dumps(
            row,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        import hashlib

        digest = hashlib.sha256(
            canonical
        ).hexdigest()

        previous = archived.get(
            experience_id
        )

        if (
            isinstance(previous, dict)
            and previous.get("sha256") == digest
        ):
            continue

        records.append(
            (
                row,
                digest,
            )
        )

    if not records:
        return {
            "written": False,
            "archive_path": None,
            "manifest_path": str(manifest_path),
            "record_count": 0,
            "validated": True,
            "active_store_mutated": False,
            "skipped_already_archived": len(candidate_ids),
        }

    from datetime import datetime
    import os
    import tempfile

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    final_path = archive_dir / (
        f"experiences_{stamp}.json"
    )

    payload = [
        row
        for row, _digest in records
    ]

    fd, tmp_name = tempfile.mkstemp(
        prefix=".experiences_",
        suffix=".tmp",
        dir=str(archive_dir),
    )

    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                ensure_ascii=False,
            )

            handle.flush()
            os.fsync(handle.fileno())

        loaded = json.loads(
            tmp_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(loaded, list):
            raise ValueError(
                "archive validation failed: root is not a list"
            )

        if len(loaded) != len(payload):
            raise ValueError(
                "archive validation failed: record count mismatch"
            )

        tmp_path.replace(final_path)

        for row, digest in records:
            experience_id = str(
                row.get("id") or ""
            )

            archived[experience_id] = {
                "archive_path": str(final_path),
                "sha256": digest,
                "archived_at": datetime.now().isoformat(),
            }

        manifest = {
            "version": 1,
            "experiences": archived,
        }

        manifest_tmp = (
            archive_dir
            / ".manifest.tmp"
        )

        manifest_tmp.write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        json.loads(
            manifest_tmp.read_text(
                encoding="utf-8"
            )
        )

        manifest_tmp.replace(
            manifest_path
        )

        return {
            "written": True,
            "archive_path": str(final_path),
            "manifest_path": str(manifest_path),
            "record_count": len(payload),
            "validated": True,
            "active_store_mutated": False,
            "skipped_already_archived": (
                len(candidate_ids)
                - len(payload)
            ),
        }

    finally:
        if tmp_path.exists():
            tmp_path.unlink(
                missing_ok=True
            )

def load_archived_experience(
    experience_id: str,
    *,
    archive_dir: Optional[Path] = None,
) -> dict:
    """Load and checksum-validate one archived experience.

    This function is read-only. It does not mutate ExperienceMemory.
    """
    if archive_dir is None:
        archive_dir = (
            Path.home()
            / ".hermes"
            / "governance"
            / "archives"
        )

    manifest_path = archive_dir / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"archive manifest not found: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(manifest, dict):
        raise ValueError(
            "archive manifest root is not an object"
        )

    entries = manifest.get("experiences")

    if not isinstance(entries, dict):
        raise ValueError(
            "archive manifest experiences is not an object"
        )

    entry = entries.get(
        str(experience_id)
    )

    if not isinstance(entry, dict):
        raise KeyError(
            f"experience not archived: {experience_id}"
        )

    archive_path = Path(
        str(entry.get("archive_path") or "")
    )

    expected_sha256 = str(
        entry.get("sha256") or ""
    )

    if not archive_path.exists():
        raise FileNotFoundError(
            f"archive file missing: {archive_path}"
        )

    payload = json.loads(
        archive_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, list):
        raise ValueError(
            "archive root is not a list"
        )

    found = None

    for row in payload:
        if (
            isinstance(row, dict)
            and str(row.get("id") or "")
            == str(experience_id)
        ):
            found = row
            break

    if found is None:
        raise KeyError(
            f"experience missing from archive file: {experience_id}"
        )

    import hashlib

    canonical = json.dumps(
        found,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    actual_sha256 = hashlib.sha256(
        canonical
    ).hexdigest()

    if actual_sha256 != expected_sha256:
        raise ValueError(
            "archive checksum mismatch"
        )

    return {
        "experience": found,
        "archive_path": str(archive_path),
        "manifest_path": str(manifest_path),
        "sha256": actual_sha256,
        "validated": True,
    }


def restore_archived_experience(
    experience_id: str,
    *,
    target_memory: ExperienceMemory,
    archive_dir: Optional[Path] = None,
) -> dict:
    """Restore one validated archived record into an explicit target memory.

    The caller must supply target_memory deliberately. This prevents accidental
    writes into the active production ExperienceMemory.
    """
    loaded = load_archived_experience(
        experience_id,
        archive_dir=archive_dir,
    )

    row = loaded["experience"]

    existing = target_memory.get(
        str(experience_id)
    )

    if existing is not None:
        return {
            "restored": False,
            "already_present": True,
            "experience_id": str(experience_id),
            "validated": True,
        }

    restored = target_memory.record(
        problem=str(row.get("problem") or ""),
        analysis=str(row.get("analysis") or ""),
        solution=str(row.get("solution") or ""),
        result=str(row.get("result") or "partial"),
        lessons_learned=list(
            row.get("lessons_learned") or []
        ),
        confidence=float(
            row.get("confidence") or 0.0
        ),
        future_recommendation=str(
            row.get("future_recommendation") or ""
        ),
        related_decision_id=str(
            row.get("related_decision_id") or ""
        ),
        related_project=str(
            row.get("related_project") or ""
        ),
        tags=list(
            row.get("tags") or []
        ),
        metadata=dict(
            row.get("metadata") or {}
        ),
        record_id=str(experience_id),
    )

    return {
        "restored": True,
        "already_present": False,
        "experience_id": restored.id,
        "validated": True,
    }


def evaluate_prune_eligibility(
    plan: dict,
    *,
    archive_dir: Optional[Path] = None,
) -> dict:
    """Evaluate which experiences are eligible for future destructive pruning.

    This function is READ-ONLY. It never removes or mutates ExperienceMemory.
    An experience is eligible only when:
      - retention plan marks it delete_candidate=True
      - effective tier is not GOLD
      - a manifest entry exists
      - archived payload exists
      - archived payload checksum validates
    """
    if archive_dir is None:
        archive_dir = (
            Path.home()
            / ".hermes"
            / "governance"
            / "archives"
        )

    rows = []

    for row in (plan.get("experiences") or []):
        if not isinstance(row, dict):
            continue

        experience_id = str(
            row.get("id") or ""
        )

        effective_tier = str(
            row.get("effective_tier") or ""
        ).upper()

        delete_candidate = bool(
            row.get("delete_candidate")
        )

        eligible = False
        archive_validated = False
        reason = ""

        if not experience_id:
            reason = "missing_experience_id"

        elif not delete_candidate:
            reason = "not_delete_candidate"

        elif effective_tier == "GOLD":
            reason = "gold_protected"

        else:
            try:
                loaded = load_archived_experience(
                    experience_id,
                    archive_dir=archive_dir,
                )

                archive_validated = bool(
                    loaded.get("validated")
                )

                if archive_validated:
                    eligible = True
                    reason = "eligible"
                else:
                    reason = "archive_not_validated"

            except Exception as exc:
                reason = (
                    "archive_validation_failed:"
                    + exc.__class__.__name__
                )

        rows.append({
            "id": experience_id,
            "effective_tier": effective_tier,
            "delete_candidate": delete_candidate,
            "archive_validated": archive_validated,
            "eligible": eligible,
            "reason": reason,
        })

    return {
        "dry_run": True,
        "eligible_count": sum(
            1
            for row in rows
            if row["eligible"]
        ),
        "evaluated_count": len(rows),
        "experiences": rows,
    }


def prune_eligible_experiences(
    eligibility: dict,
    *,
    memory: ExperienceMemory,
    execute: bool = False,
) -> dict:
    """Prune only explicitly eligible records from an explicit memory.

    Safety properties:
      - execute=False is always a dry-run
      - caller must provide the target ExperienceMemory explicitly
      - GOLD records are rejected defensively
      - only eligibility rows with eligible=True are considered
      - IDs are rechecked before removal
    """
    rows = []

    for row in (
        eligibility.get("experiences")
        or []
    ):
        if not isinstance(row, dict):
            continue

        experience_id = str(
            row.get("id") or ""
        )

        eligible = bool(
            row.get("eligible")
        )

        effective_tier = str(
            row.get("effective_tier") or ""
        ).upper()

        action = "skipped"

        if not experience_id:
            action = "missing_id"

        elif effective_tier == "GOLD":
            action = "gold_protected"

        elif not eligible:
            action = "not_eligible"

        elif not execute:
            action = "would_prune"

        else:
            existing = memory.get(
                experience_id
            )

            if existing is None:
                action = "already_absent"
            else:
                removed = memory.remove(
                    experience_id
                )

                action = (
                    "pruned"
                    if removed is not None
                    else "remove_failed"
                )

        rows.append({
            "id": experience_id,
            "eligible": eligible,
            "effective_tier": effective_tier,
            "action": action,
        })

    return {
        "execute": bool(execute),
        "dry_run": not bool(execute),
        "eligible_count": sum(
            1
            for row in rows
            if row["eligible"]
        ),
        "pruned_count": sum(
            1
            for row in rows
            if row["action"] == "pruned"
        ),
        "experiences": rows,
    }


def plan_synthetic_experience_cleanup(
    *,
    memory: Optional[ExperienceMemory] = None,
    feedback_store: Optional[Any] = None,
    archive_dir: Optional[Path] = None,
) -> dict:
    """Build a read-only cleanup plan for synthetic test experiences.

    A record is eligible only when:
      1. provenance == synthetic_test
      2. archive entry exists and validates
      3. no feedback record references the experience
    """
    from collections import Counter

    from governance.experience_feedback import (
        ExperienceFeedbackStore,
    )
    from governance.experience_query import (
        classify_experience_provenance,
    )

    memory = memory or ExperienceMemory()

    feedback_store = (
        feedback_store
        or ExperienceFeedbackStore()
    )

    if archive_dir is None:
        from hermes_constants import (
            get_hermes_home,
        )

        archive_dir = (
            get_hermes_home()
            / "governance"
            / "archives"
        )

    archive_dir = Path(
        archive_dir
    )

    manifest_path = (
        archive_dir
        / "manifest.json"
    )

    manifest_entries = {}

    if manifest_path.exists():
        import json

        loaded = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(loaded, dict):
            entries = loaded.get(
                "experiences"
            )

            if isinstance(entries, dict):
                manifest_entries = entries

    feedback_refs = Counter(
        str(
            record.experience_id
            or ""
        )
        for record in feedback_store.get_all()
    )

    rows = []

    for record in memory.get_all():
        row = record.to_dict()

        provenance = (
            classify_experience_provenance(
                row
            )
        )

        if provenance != "synthetic_test":
            continue

        experience_id = record.id

        refs = feedback_refs[
            experience_id
        ]

        archived = (
            experience_id
            in manifest_entries
        )

        archive_valid = False

        if archived:
            try:
                loaded = load_archived_experience(
                    experience_id,
                    archive_dir=archive_dir,
                )

                archive_valid = bool(
                    loaded.get(
                        "validated"
                    )
                )

            except Exception:
                archive_valid = False

        eligible = (
            archived
            and archive_valid
            and refs == 0
        )

        if refs > 0:
            reason = (
                "feedback_referenced"
            )
        elif not archived:
            reason = (
                "not_archived"
            )
        elif not archive_valid:
            reason = (
                "archive_invalid"
            )
        else:
            reason = (
                "archived_no_feedback_refs"
            )

        rows.append({
            "id":
                experience_id,
            "provenance":
                provenance,
            "archived":
                archived,
            "archive_valid":
                archive_valid,
            "feedback_refs":
                refs,
            "eligible":
                eligible,
            "reason":
                reason,
        })

    import hashlib
    import json

    fingerprint_payload = [
        {
            "id": row["id"],
            "archived": row["archived"],
            "archive_valid": row["archive_valid"],
            "feedback_refs": row["feedback_refs"],
            "eligible": row["eligible"],
            "reason": row["reason"],
        }
        for row in rows
    ]

    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return {
        "synthetic_count":
            len(rows),
        "eligible_count":
            sum(
                1
                for row in rows
                if row["eligible"]
            ),
        "plan_fingerprint":
            fingerprint,
        "experiences":
            rows,
    }


def cleanup_synthetic_experiences(
    plan: dict,
    *,
    memory: Optional[ExperienceMemory] = None,
    feedback_store: Optional[Any] = None,
    archive_dir: Optional[Path] = None,
    execute: bool = False,
) -> dict:
    """Apply a synthetic cleanup plan.

    Destructive execution is disabled unless execute=True.
    """
    from governance.experience_query import (
        classify_experience_provenance,
    )

    memory = memory or ExperienceMemory()

    candidates = [
        row
        for row in (
            plan.get("experiences")
            or []
        )
        if row.get("eligible")
    ]

    removed = []
    skipped_stale = []

    if execute:
        current_plan = (
            plan_synthetic_experience_cleanup(
                memory=memory,
                feedback_store=feedback_store,
                archive_dir=archive_dir,
            )
        )

        current_by_id = {
            str(row.get("id") or ""): row
            for row in (
                current_plan.get("experiences")
                or []
            )
        }

        for row in candidates:
            experience_id = str(
                row.get("id")
                or ""
            )

            current_state = current_by_id.get(
                experience_id
            )

            if (
                not isinstance(current_state, dict)
                or not current_state.get("eligible")
            ):
                skipped_stale.append(
                    experience_id
                )
                continue

            current = memory.get(
                experience_id
            )

            if current is None:
                skipped_stale.append(
                    experience_id
                )
                continue

            # Final defensive provenance check.
            provenance = (
                classify_experience_provenance(
                    current.to_dict()
                )
            )

            if provenance != "synthetic_test":
                continue

            deleted = memory.remove(
                experience_id
            )

            if deleted is not None:
                removed.append(
                    experience_id
                )

    return {
        "dry_run":
            not execute,
        "eligible_count":
            len(candidates),
        "removed_count":
            len(removed),
        "removed_ids":
            removed,
        "skipped_stale_count":
            len(skipped_stale),
        "skipped_stale_ids":
            skipped_stale,
    }


def write_synthetic_cleanup_audit(
    *,
    plan: dict,
    result: dict,
    audit_dir: Optional[Path] = None,
) -> dict:
    """Persist an append-only audit record for synthetic cleanup activity."""
    from datetime import datetime
    import hashlib
    import json
    import os
    import tempfile

    if audit_dir is None:
        from hermes_constants import get_hermes_home

        audit_dir = (
            get_hermes_home()
            / "governance"
            / "cleanup_audit"
        )

    audit_dir = Path(
        audit_dir
    )

    audit_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    payload = {
        "version": 1,
        "created_at":
            datetime.now().isoformat(),
        "plan_fingerprint":
            plan.get(
                "plan_fingerprint"
            ),
        "synthetic_count":
            plan.get(
                "synthetic_count"
            ),
        "eligible_count":
            plan.get(
                "eligible_count"
            ),
        "dry_run":
            result.get(
                "dry_run"
            ),
        "removed_count":
            result.get(
                "removed_count"
            ),
        "removed_ids":
            list(
                result.get(
                    "removed_ids"
                )
                or []
            ),
        "skipped_stale_count":
            result.get(
                "skipped_stale_count"
            ),
        "skipped_stale_ids":
            list(
                result.get(
                    "skipped_stale_ids"
                )
                or []
            ),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    digest = hashlib.sha256(
        canonical
    ).hexdigest()

    payload[
        "record_sha256"
    ] = digest

    final_path = (
        audit_dir
        / f"synthetic_cleanup_{stamp}.json"
    )

    fd, tmp_name = tempfile.mkstemp(
        prefix=".synthetic_cleanup_",
        suffix=".tmp",
        dir=str(
            audit_dir
        ),
    )

    tmp_path = Path(
        tmp_name
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                ensure_ascii=False,
            )

            handle.flush()
            os.fsync(
                handle.fileno()
            )

        loaded = json.loads(
            tmp_path.read_text(
                encoding="utf-8"
            )
        )

        assert (
            loaded[
                "record_sha256"
            ]
            == digest
        )

        tmp_path.replace(
            final_path
        )

    finally:
        if tmp_path.exists():
            tmp_path.unlink(
                missing_ok=True
            )

    return {
        "written": True,
        "audit_path":
            str(final_path),
        "record_sha256":
            digest,
    }


def production_prune_enabled() -> bool:
    """Return whether destructive production pruning is explicitly enabled."""
    import os

    value = str(
        os.getenv(
            "HERMES_EXPERIENCE_PRUNE_EXECUTE",
            "",
        )
    ).strip().lower()

    return value in {
        "1",
        "true",
        "yes",
        "on",
    }


def run_production_prune(
    *,
    memory: Optional[ExperienceMemory] = None,
    archive_dir: Optional[Path] = None,
) -> dict:
    """Run the full guarded production prune pipeline.

    Destructive pruning is disabled by default and requires an explicit
    environment gate.

    Pipeline:
      plan
      -> archive copy
      -> checksum validation
      -> prune eligibility
      -> explicit execution gate
      -> prune
    """
    memory = memory or ExperienceMemory()

    runtime = ExperienceRetentionRuntime(
        memory=memory,
    )

    plan = runtime.build_plan()

    archive_result = write_archive_copy(
        plan,
        archive_dir=archive_dir,
        memory=memory,
    )

    eligibility = evaluate_prune_eligibility(
        plan,
        archive_dir=archive_dir,
    )

    execute = production_prune_enabled()

    prune_result = prune_eligible_experiences(
        eligibility,
        memory=memory,
        execute=execute,
    )

    return {
        "execute_enabled": execute,
        "dry_run": not execute,
        "plan": {
            "total_experiences":
                plan.get("total_experiences"),
            "archive_candidates":
                plan.get("archive_candidates"),
            "delete_candidates":
                plan.get("delete_candidates"),
        },
        "archive": archive_result,
        "eligibility": {
            "evaluated_count":
                eligibility.get("evaluated_count"),
            "eligible_count":
                eligibility.get("eligible_count"),
        },
        "prune": {
            "eligible_count":
                prune_result.get("eligible_count"),
            "pruned_count":
                prune_result.get("pruned_count"),
        },
    }


def run_retention_housekeeping() -> dict:
    """Run a non-destructive retention planning pass.

    This is intentionally dry-run only. It may be called periodically from
    gateway housekeeping without mutating ExperienceMemory.
    """
    runtime = ExperienceRetentionRuntime()
    plan = runtime.build_plan()

    return plan


def main() -> int:
    runtime = ExperienceRetentionRuntime()
    plan = runtime.build_plan()

    print(
        json.dumps(
            plan,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

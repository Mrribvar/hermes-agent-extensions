"""Tests for Intelligence Persistence Layer — Phase HERALD-INTELLIGENCE-013.

Covers:
  - append-only storage semantics
  - persistence across store instances (restart continuity)
  - migration safety (versioned dumps, forward migration, newer-version guard)
  - connector integration (engine -> store -> agent memory layer)
  - fail-safe behavior (corrupt files, disabled connector)
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from governance.intelligence_store import (
    IntelligenceStore,
    FORMAT_VERSION,
    SECTIONS,
)
from governance.intelligence_persistence import IntelligencePersistenceConnector
from governance.decision_performance_engine import (
    DecisionPerformanceEngine,
    DecisionRecord,
)
from governance.decision_store import DecisionStore
from governance.decision_feedback_loop import DecisionFeedbackLoop


# --------------------------------------------------------------------------- #
# Fixtures


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "intelligence.json")


@pytest.fixture
def store(store_path):
    return IntelligenceStore(storage_path=store_path)


@pytest.fixture
def engine(tmp_path):
    dstore = DecisionStore(storage_path=str(tmp_path / "decisions.json"))
    return DecisionPerformanceEngine(store=dstore, enabled=True)


@pytest.fixture
def connector(store):
    return IntelligencePersistenceConnector(store=store, enabled=True)


# --------------------------------------------------------------------------- #
# Store: basic append-only semantics


class TestStoreAppendOnly:
    def test_new_store_has_empty_sections(self, store):
        counts = store.counts()
        assert set(counts.keys()) == set(SECTIONS)
        assert all(v == 0 for v in counts.values())

    def test_append_decision_and_read_back(self, store):
        assert store.append_decision({"decision_id": "dec_1", "strategy": "s"})
        rows = store.read_decisions()
        assert len(rows) == 1
        assert rows[0]["decision_id"] == "dec_1"
        assert "ts" in rows[0]

    def test_append_only_never_overwrites(self, store):
        store.append_feedback({"decision_id": "dec_1", "signal": 0.8})
        store.append_feedback({"decision_id": "dec_1", "signal": -0.5})
        rows = store.read_feedback()
        assert len(rows) == 2
        assert rows[0]["signal"] == 0.8
        assert rows[1]["signal"] == -0.5

    def test_each_section_isolated(self, store):
        store.append_decision({"decision_id": "d"})
        store.append_evaluation({"decision_id": "d"})
        store.append_feedback({"decision_id": "d"})
        store.append_strategy_metrics({"strategy": "x"})
        store.append_confidence({"decision_id": "d", "confidence": 0.7})
        counts = store.counts()
        assert counts == {
            "decisions": 1,
            "evaluations": 1,
            "feedback": 1,
            "strategy_metrics": 1,
            "confidence_history": 1,
        }

    def test_invalid_section_rejected(self, store):
        assert store.append_decision.__self__ is store  # sanity
        # Direct _append with a bogus section is refused.
        assert store._append("not_a_section", {"x": 1}) is False

    def test_read_limit(self, store):
        for i in range(5):
            store.append_decision({"decision_id": f"dec_{i}"})
        recent = store.read_decisions(limit=2)
        assert [r["decision_id"] for r in recent] == ["dec_3", "dec_4"]

    def test_read_returns_copies(self, store):
        store.append_decision({"decision_id": "dec_1"})
        row = store.read_decisions()[0]
        row["decision_id"] = "mutated"
        assert store.read_decisions()[0]["decision_id"] == "dec_1"


# --------------------------------------------------------------------------- #
# Restart continuity: a new instance at the same path sees prior data


class TestRestartContinuity:
    def test_new_instance_reloads_data(self, store_path):
        s1 = IntelligenceStore(storage_path=store_path)
        s1.append_decision({"decision_id": "dec_1", "strategy": "direct"})
        s1.append_feedback({"decision_id": "dec_1", "signal": 0.8})

        # Simulate restart: brand-new instance, same path.
        s2 = IntelligenceStore(storage_path=store_path)
        assert s2.read_decisions()[0]["decision_id"] == "dec_1"
        assert s2.read_feedback()[0]["signal"] == 0.8
        assert s2.format_version == FORMAT_VERSION

    def test_counts_survive_restart(self, store_path):
        s1 = IntelligenceStore(storage_path=store_path)
        for i in range(3):
            s1.append_decision({"decision_id": f"dec_{i}"})
        s2 = IntelligenceStore(storage_path=store_path)
        assert s2.counts()["decisions"] == 3

    def test_multiple_restarts_accumulate(self, store_path):
        for i in range(3):
            s = IntelligenceStore(storage_path=store_path)
            s.append_decision({"decision_id": f"dec_{i}"})
        final = IntelligenceStore(storage_path=store_path)
        assert final.counts()["decisions"] == 3

    def test_default_path_is_under_hermes_home(self):
        s = IntelligenceStore()
        assert ".hermes" in str(s.storage_path)


# --------------------------------------------------------------------------- #
# Migration safety


class TestMigrationSafety:
    def test_dump_contains_format_version(self, store_path, store):
        store.append_decision({"decision_id": "dec_1"})
        with open(store_path) as fh:
            doc = json.load(fh)
        assert doc["format_version"] == FORMAT_VERSION
        assert "sections" in doc
        assert "decisions" in doc["sections"]

    def test_v0_dump_migrated_forward(self, store_path):
        # Hand-craft a v0 dump: a bare list under 'sections' without version.
        legacy = {"sections": [{"decision_id": "legacy_1", "strategy": "old"}]}
        with open(store_path, "w") as fh:
            json.dump(legacy, fh)

        s = IntelligenceStore(storage_path=store_path)
        assert s.format_version == FORMAT_VERSION
        decisions = s.read_decisions()
        assert any(d.get("decision_id") == "legacy_1" for d in decisions)
        assert s.is_valid()

    def test_missing_version_treated_as_v0(self, store_path):
        doc = {
            "sections": {"feedback": [{"decision_id": "f1", "signal": 0.5}]},
        }
        with open(store_path, "w") as fh:
            json.dump(doc, fh)
        s = IntelligenceStore(storage_path=store_path)
        assert s.format_version == FORMAT_VERSION
        assert s.read_feedback()[0]["decision_id"] == "f1"

    def test_newer_version_guarded_without_data_loss(self, store_path):
        doc = {
            "format_version": FORMAT_VERSION + 5,
            "sections": {"decisions": [{"decision_id": "future_1"}]},
        }
        with open(store_path, "w") as fh:
            json.dump(doc, fh)
        s = IntelligenceStore(storage_path=store_path)
        # Newer-version data is preserved read-only, flagged, never destroyed.
        assert s.read_decisions()[0]["decision_id"] == "future_1"
        assert s.format_errors  # warned about the future version

    def test_corrupt_file_starts_fresh_without_raising(self, store_path):
        Path(store_path).write_text("{this is not json!!!")
        s = IntelligenceStore(storage_path=store_path)
        assert s.counts() == {k: 0 for k in SECTIONS}
        assert s.format_errors  # recorded a warning

    def test_non_dict_root_tolerated(self, store_path):
        with open(store_path, "w") as fh:
            json.dump([1, 2, 3], fh)
        s = IntelligenceStore(storage_path=store_path)
        assert s.counts()["decisions"] == 0
        assert s.format_errors

    def test_round_trip_preserves_all_sections(self, store_path):
        s1 = IntelligenceStore(storage_path=store_path)
        s1.append_decision({"decision_id": "d1"})
        s1.append_evaluation({"decision_id": "d1", "is_success": True})
        s1.append_feedback({"decision_id": "d1", "signal": 0.8})
        s1.append_strategy_metrics({"strategy": "s", "success_rate": 1.0})
        s1.append_confidence({"decision_id": "d1", "confidence": 0.9})

        s2 = IntelligenceStore(storage_path=store_path)
        all_data = s2.read_all()
        assert len(all_data["decisions"]) == 1
        assert len(all_data["evaluations"]) == 1
        assert len(all_data["feedback"]) == 1
        assert len(all_data["strategy_metrics"]) == 1
        assert len(all_data["confidence_history"]) == 1


# --------------------------------------------------------------------------- #
# Connector: engine -> store -> agent memory layer


class TestConnector:
    def test_persist_decision_record_object(self, connector):
        record = DecisionRecord(
            decision_id="dec_1",
            task_id="t1",
            selected_strategy="direct",
            confidence_before=0.9,
            actual_outcome="success",
        )
        assert connector.persist_decision_record(record) is True
        assert connector.store.read_decisions()[0]["decision_id"] == "dec_1"
        assert connector.synced_counts()["decisions"] == 1

    def test_persist_decision_record_dict(self, connector):
        assert connector.persist_decision_record({"decision_id": "dec_2"}) is True
        assert connector.store.read_decisions()[0]["decision_id"] == "dec_2"

    def test_persist_feedback_object_and_dict(self, connector):
        from governance.decision_feedback_loop import DecisionFeedback

        fb = DecisionFeedback(
            decision_id="dec_1", task_id="t1", success=True,
            improvement_signal=0.8, learning_signal_type="HIGH_CONFIDENCE_SUCCESS",
        )
        assert connector.persist_feedback(fb) is True
        assert connector.persist_feedback({"decision_id": "dec_2", "success": False}) is True
        rows = connector.store.read_feedback()
        assert len(rows) == 2
        assert rows[0]["learning_signal_type"] == "HIGH_CONFIDENCE_SUCCESS"

    def test_persist_strategy_metrics_snapshot(self, connector):
        assert connector.persist_strategy_metrics({
            "strategy_stats": {"direct": {"attempts": 2, "successes": 2}},
            "success_rate": 1.0,
        }) is True
        row = connector.store.read_strategy_metrics()[0]
        assert row["success_rate"] == 1.0
        assert "recorded_at" in row

    def test_persist_confidence(self, connector):
        assert connector.persist_confidence("dec_1", 0.85, strategy="direct", task_id="t1")
        row = connector.store.read_confidence_history()[0]
        assert row["confidence"] == 0.85
        assert row["decision_id"] == "dec_1"

    def test_sync_from_engine(self, engine, connector):
        engine.record_decision(task_id="t1", strategy="direct", confidence=0.8,
                               expected_outcome="success")
        engine.record_decision(task_id="t2", strategy="retry", confidence=0.6,
                               expected_outcome="success")
        synced = connector.sync_from_engine(engine)
        assert synced["decisions"] == 2
        assert connector.store.counts()["decisions"] == 2

    def test_sync_feedback_from_loop(self, engine, connector):
        loop = DecisionFeedbackLoop(engine=engine, enabled=True)
        did = engine.record_decision(task_id="t1", strategy="direct", confidence=0.9,
                                     expected_outcome="success")
        loop.process_decision_outcome(decision_id=did, actual_outcome="success")
        count = connector.sync_feedback_from_loop(loop)
        assert count == 1
        assert connector.store.counts()["feedback"] == 1
        assert connector.store.read_feedback()[0]["learning_signal_type"] == \
            "HIGH_CONFIDENCE_SUCCESS"

    def test_sync_from_engine_duplicates_are_append_only(self, engine, connector):
        engine.record_decision(task_id="t1", strategy="direct", confidence=0.8)
        connector.sync_from_engine(engine)
        connector.sync_from_engine(engine)
        # Append-only: the second sync appends again (no dedup by design).
        assert connector.store.counts()["decisions"] == 2

    def test_attach_to_execution_memory(self, connector):
        memory = MagicMock()
        record = MagicMock()
        record.metadata = {"session": "abc"}
        memory.get_execution.return_value = record
        memory.save_execution.return_value = "exec_1"

        assert connector.attach_to_execution_memory(
            memory, "exec_1", summary={"decision_id": "dec_1", "signal": 0.8}
        ) is True

        # Existing metadata preserved; intelligence merged additively.
        assert record.metadata["session"] == "abc"
        assert record.metadata["intelligence"]["decision_id"] == "dec_1"
        memory.save_execution.assert_called_once_with(record)

    def test_attach_to_execution_memory_missing_record(self, connector):
        memory = MagicMock()
        memory.get_execution.return_value = None
        assert connector.attach_to_execution_memory(memory, "nope") is False
        memory.save_execution.assert_not_called()

    def test_storage_summary(self, connector):
        connector.persist_decision_record({"decision_id": "dec_1"})
        summary = connector.storage_summary()
        assert summary["counts"]["decisions"] == 1
        assert summary["total_records"] == 1
        assert summary["format_version"] == FORMAT_VERSION

    def test_disabled_connector_is_noop(self, store):
        connector = IntelligencePersistenceConnector(store=store, enabled=False)
        assert connector.persist_decision_record({"decision_id": "dec_1"}) is False
        assert connector.persist_feedback({"decision_id": "dec_1"}) is False
        assert connector.sync_from_engine(MagicMock()) == {}
        assert connector.store.counts()["decisions"] == 0

    def test_connector_never_raises_on_bad_input(self, connector):
        assert connector.persist_decision_record(None) is False
        assert connector.persist_decision_record(42) is False
        assert connector.persist_feedback("nope") is False
        assert connector.persist_evaluation(object()) is False


# --------------------------------------------------------------------------- #
# End-to-end: full pipeline with persistence across "sessions"


class TestEndToEndPersistence:
    def test_full_session_flow_persists_everything(self, tmp_path):
        store_path = tmp_path / "intelligence.json"
        store = IntelligenceStore(storage_path=str(store_path))
        connector = IntelligencePersistenceConnector(store=store)

        engine = DecisionPerformanceEngine(
            store=DecisionStore(storage_path=str(tmp_path / "decisions.json")),
            enabled=True,
        )
        loop = DecisionFeedbackLoop(engine=engine, enabled=True)

        for i in range(3):
            did = engine.record_decision(
                task_id=f"task_{i}", strategy="direct",
                confidence=0.7 + i * 0.1, expected_outcome="success",
            )
            connector.persist_decision_record(engine.get_decision_by_id(did))
            connector.persist_confidence(did, 0.7 + i * 0.1, strategy="direct")
            fb = loop.process_decision_outcome(
                decision_id=did, actual_outcome="success" if i < 2 else "failure",
            )
            connector.persist_feedback(fb)
            ev = engine.evaluate_decision(decision_id=did, actual_outcome="success")
            connector.persist_evaluation(ev)
        connector.persist_strategy_metrics(engine.get_metrics())

        # Simulate a restart.
        store2 = IntelligenceStore(storage_path=str(store_path))
        assert store2.counts()["decisions"] == 3
        assert store2.counts()["feedback"] == 3
        assert store2.counts()["evaluations"] == 3
        assert store2.counts()["strategy_metrics"] == 1
        assert store2.counts()["confidence_history"] == 3

        # The append-only trail is intact and ordered.
        signals = [fb["improvement_signal"] for fb in store2.read_feedback()]
        assert signals[0] == 0.8       # HIGH_CONFIDENCE_SUCCESS
        assert signals[2] == -0.8      # HIGH_CONFIDENCE_FAILURE

    def test_corrupt_store_never_breaks_engine(self, tmp_path):
        store_path = tmp_path / "intelligence.json"
        store_path.write_text("{corrupt")
        store = IntelligenceStore(storage_path=str(store_path))
        connector = IntelligencePersistenceConnector(store=store)
        # Even with a broken store, persistence degrades silently.
        assert connector.persist_decision_record({"decision_id": "x"}) is True
        assert connector.store.format_errors
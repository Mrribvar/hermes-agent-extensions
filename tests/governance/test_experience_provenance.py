from governance.experience_query import (
    classify_experience_provenance,
)


def test_runtime_learning_classification():
    row = {
        "problem": "real runtime task",
        "metadata": {
            "learning_source": "turn_finalizer",
            "session_id": "runtime-session",
            "turn_id": "runtime-turn",
        },
    }

    assert (
        classify_experience_provenance(row)
        == "runtime_learning"
    )


def test_synthetic_test_overrides_runtime_source():
    row = {
        "problem": "edit file",
        "metadata": {
            "learning_source": "turn_finalizer",
            "session_id": "verify-budget-test",
            "turn_id": "verify-budget-test:abc",
        },
    }

    assert (
        classify_experience_provenance(row)
        == "synthetic_test"
    )


def test_pm_fixture_is_synthetic():
    row = {
        "problem": "edit changed.py",
        "metadata": {
            "learning_source": "turn_finalizer",
            "session_id": "pm2f-verification-test",
            "turn_id": "turn-pm2k2-verified",
        },
    }

    assert (
        classify_experience_provenance(row)
        == "synthetic_test"
    )


def test_metadata_free_record_is_legacy():
    row = {
        "problem": "older saved experience",
    }

    assert (
        classify_experience_provenance(row)
        == "legacy"
    )


def test_unrecognized_metadata_is_unknown():
    row = {
        "problem": "other source",
        "metadata": {
            "source": "external-import",
        },
    }

    assert (
        classify_experience_provenance(row)
        == "unknown"
    )


def test_invalid_input_is_unknown():
    assert (
        classify_experience_provenance(None)
        == "unknown"
    )


def test_runtime_problem_may_contain_test_words():
    row = {
        "problem":
            "pytest تست تغییر کد بعد از اصلاح runtime",
        "metadata": {
            "learning_source":
                "turn_finalizer",
            "session_id":
                "runtime-session",
            "turn_id":
                "runtime-turn",
        },
    }

    assert (
        classify_experience_provenance(row)
        == "runtime_learning"
    )


def test_runtime_problem_with_probe_word_is_not_synthetic():
    row = {
        "problem":
            "probe network connectivity",
        "metadata": {
            "learning_source":
                "turn_finalizer",
            "session_id":
                "real-session",
            "turn_id":
                "real-turn",
        },
    }

    assert (
        classify_experience_provenance(row)
        == "runtime_learning"
    )

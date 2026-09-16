from unittest.mock import patch

from agent.experience.lifecycle_learning import observe_lifecycle
from governance.experience_feedback import (
    ExperienceFeedbackEvaluator,
    ExperienceFeedbackStore,
)
from governance.experience_memory import ExperienceMemory


def test_feedback_store_exact_turn_experience_identity(tmp_path):
    store = ExperienceFeedbackStore(
        data_dir=str(tmp_path)
    )

    evaluator = ExperienceFeedbackEvaluator()
    evaluator.store = store

    evaluator.record_feedback(
        task_id="turn-1",
        experience_id="exp-1",
        recommendation_used=True,
        before_result="success",
        after_result="success",
    )

    assert store.has_task_experience(
        "turn-1",
        "exp-1",
    )
    assert not store.has_task_experience(
        "turn-2",
        "exp-1",
    )


def test_unverified_does_not_mutate_confidence():
    with (
        patch(
            "governance.experience_memory.ExperienceMemory.update_confidence"
        ) as update,
        patch(
            "governance.experience_feedback.ExperienceFeedbackEvaluator.record_feedback"
        ) as record,
    ):
        observe_lifecycle(
            "on_session_end",
            turn_id="turn-u",
            verification_outcome="UNVERIFIED",
            recalled_experience_id="exp-1",
            recalled_recommendation_safe=True,
        )

    record.assert_not_called()
    update.assert_not_called()


def test_not_applicable_does_not_mutate_confidence():
    with (
        patch(
            "governance.experience_memory.ExperienceMemory.update_confidence"
        ) as update,
        patch(
            "governance.experience_feedback.ExperienceFeedbackEvaluator.record_feedback"
        ) as record,
    ):
        observe_lifecycle(
            "on_session_end",
            turn_id="turn-na",
            verification_outcome="NOT_APPLICABLE",
            recalled_experience_id="exp-1",
            recalled_recommendation_safe=True,
        )

    record.assert_not_called()
    update.assert_not_called()


def test_unsafe_recommendation_does_not_mutate_confidence():
    with (
        patch(
            "governance.experience_memory.ExperienceMemory.update_confidence"
        ) as update,
        patch(
            "governance.experience_feedback.ExperienceFeedbackEvaluator.record_feedback"
        ) as record,
    ):
        observe_lifecycle(
            "on_session_end",
            turn_id="turn-x",
            verification_outcome="VERIFIED",
            recalled_experience_id="exp-1",
            recalled_recommendation_safe=False,
        )

    record.assert_not_called()
    update.assert_not_called()

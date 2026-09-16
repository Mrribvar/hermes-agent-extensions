from agent.experience.recall_integration import RecallContext


def test_recall_context_carries_selected_experience_identity():
    ctx = RecallContext(
        task="test",
        has_experience=True,
        experience_count=1,
        recommended_solution="solution",
        confidence=0.9,
        result="success",
        lessons_learned=["verified"],
        existing_problem="problem",
        existing_analysis="analysis",
        recommendation_safe=True,
        selected_experience_id="exp-123",
    )

    assert ctx.selected_experience_id == "exp-123"

    data = ctx.to_dict()

    assert data["selected_experience_id"] == "exp-123"


def test_recall_context_identity_is_optional():
    ctx = RecallContext(
        task="test",
        has_experience=False,
        experience_count=0,
        recommended_solution=None,
        confidence=0.0,
        result=None,
        lessons_learned=[],
        existing_problem=None,
        existing_analysis=None,
        recommendation_safe=False,
    )

    assert ctx.selected_experience_id is None

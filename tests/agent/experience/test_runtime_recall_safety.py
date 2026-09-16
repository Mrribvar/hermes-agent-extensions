from agent.experience.recall_integration import RecallContext


def test_verified_success_can_surface_recommendation():
    ctx = RecallContext(
        task="pytest verification",
        has_experience=True,
        experience_count=1,
        recommended_solution="Run pytest after editing.",
        confidence=0.9,
        result="success",
        lessons_learned=["verification_passed"],
        existing_problem="verify code",
        existing_analysis="passed",
        recommendation_safe=True,
    )

    text = ctx.to_prompt_context()

    assert "Verified reusable recommendation" in text
    assert "Run pytest after editing." in text
    assert "advisory context" in text


def test_failed_experience_cannot_surface_solution_as_trusted():
    ctx = RecallContext(
        task="pytest verification",
        has_experience=True,
        experience_count=1,
        recommended_solution="Bad old solution",
        confidence=0.9,
        result="failed",
        lessons_learned=["verification_failed"],
        existing_problem="verify code",
        existing_analysis="failed",
        recommendation_safe=False,
    )

    text = ctx.to_prompt_context()

    assert "Verified reusable recommendation" not in text
    assert "Bad old solution" not in text
    assert "Do not reuse" in text
    assert "verification_failed" in text


def test_unverified_partial_is_warning_only():
    ctx = RecallContext(
        task="edit code",
        has_experience=True,
        experience_count=1,
        recommended_solution="Provisional answer",
        confidence=0.25,
        result="partial",
        lessons_learned=["verification_incomplete"],
        existing_problem="edit",
        existing_analysis="unverified",
        recommendation_safe=False,
    )

    text = ctx.to_prompt_context()

    assert "Provisional answer" not in text
    assert "Do not reuse" in text
    assert "verification_incomplete" in text

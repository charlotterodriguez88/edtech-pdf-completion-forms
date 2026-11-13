from src.checkout_form_service import CompletionRequest, completion_status


def test_submitted_before_deadline_is_complete() -> None:
    request = CompletionRequest(
        course="Storefront analytics",
        learner="Mina Chen",
        deadline="2026-11-10T17:00:00+00:00",
        submitted_at="2026-11-10T16:42:00+00:00",
        educator="Ravi Singh",
        pdf_base64="cGRm",
    )

    assert completion_status(request) == "complete"


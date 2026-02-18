from urllib.parse import parse_qs, urlsplit

from app.domain.quizzes.delivery.link_builder import LinkBuilder


def test_build_link_preserves_existing_query_params_and_replaces_token():
    builder = LinkBuilder()
    builder.config.MONTHLY_QUIZ_BASE_URL = (
        "https://quiz.example.com/start?utm_source=crm&token=old-value"
    )

    link = builder.build_link("token+with/special==")

    parsed = urlsplit(link)
    params = parse_qs(parsed.query)
    assert parsed.path == "/start"
    assert params["utm_source"] == ["crm"]
    assert params["token"] == ["token+with/special=="]


def test_build_preferred_link_uses_short_link_when_available():
    builder = LinkBuilder()
    builder.config.MONTHLY_QUIZ_SHORT_BASE_URL = "https://q.hrm.br"

    link = builder.build_preferred_link("long-token", "abc123ef")

    assert link == "https://q.hrm.br/abc123ef"


def test_build_preferred_link_falls_back_to_full_link():
    builder = LinkBuilder()
    builder.config.MONTHLY_QUIZ_SHORT_BASE_URL = None
    builder.config.MONTHLY_QUIZ_BASE_URL = "https://quiz.example.com/quiz"

    link = builder.build_preferred_link("fallback-token", None)

    assert link == "https://quiz.example.com/quiz?token=fallback-token"

from app.services.question_humanizer import QuestionHumanizer


def test_normalize_question_type_normalizes_case_and_spacing():
    humanizer = QuestionHumanizer.__new__(QuestionHumanizer)

    assert humanizer._normalize_question_type("  DAILY_FOLLOW_UP  ") == "daily_follow_up"
    assert humanizer._normalize_question_type("mood_assessment") == "mood_assessment"


def test_select_intent_pattern_uses_only_matching_canonical_type():
    humanizer = QuestionHumanizer.__new__(QuestionHumanizer)
    recent_questions = [
        {"type": "daily_follow_up", "intent": "greeting_afternoon"},
        {"type": "mood_assessment", "intent": "feeling_inquiry"},
    ]

    selected = humanizer._select_intent_pattern("daily_follow_up", recent_questions)

    assert selected in humanizer.INTENT_PATTERNS["daily_follow_up"]
    assert selected != "greeting_afternoon"


def test_generate_fallback_variation_avoids_recent_duplicate_when_possible():
    humanizer = QuestionHumanizer.__new__(QuestionHumanizer)
    original = "Como voce esta se sentindo hoje?"
    repeated = f"Boa noite! {original}"
    recent_questions = [{"text": repeated}]

    selected = humanizer._generate_fallback_variation(
        original,
        "greeting_evening",
        recent_questions=recent_questions,
    )

    assert selected != repeated

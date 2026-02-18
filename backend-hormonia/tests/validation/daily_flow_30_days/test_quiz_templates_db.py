"""
Validation for monthly quiz templates loaded in the database.
"""

import re

from app.database import SessionLocal
from app.models.quiz import QuizTemplate


ALLOWED_TYPES = {
    "multiple_choice",
    "single_choice",
    "scale",
    "open_text",
    "free_text",
    "yes_no",
}

QUIZ_MARKDOWN_PATH = "app/templates/arquivo/Quizz de Bem-Estar Mensal.md"


def _count_markdown_questions(path: str) -> int:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    return len(re.findall(r"^###\s*\*\*(\d+\.\d+)\.", content, re.MULTILINE))


def test_monthly_quiz_template_exists_and_valid():
    db = SessionLocal()
    try:
        quiz = (
            db.query(QuizTemplate)
            .filter(QuizTemplate.name == "monthly_comprehensive")
            .first()
        )
        assert quiz, "monthly_comprehensive quiz template not found"

        questions = quiz.questions or []
        assert questions, "monthly_comprehensive quiz has no questions"

        for idx, question in enumerate(questions):
            assert question.get("id"), f"question {idx} missing id"
            assert question.get("text"), f"question {idx} missing text"
            q_type = question.get("type")
            assert q_type in ALLOWED_TYPES, f"question {idx} invalid type: {q_type}"

            if q_type in {"multiple_choice", "single_choice"}:
                options = question.get("options") or []
                assert options, f"question {idx} missing options"
                for opt_idx, option in enumerate(options):
                    label = option.get("text") or option.get("label")
                    assert label, f"question {idx} option {opt_idx} missing label/text"
                    assert option.get("value") is not None, (
                        f"question {idx} option {opt_idx} missing value"
                    )
    finally:
        db.close()


def test_monthly_quiz_markdown_count_matches_db():
    db = SessionLocal()
    try:
        quiz = (
            db.query(QuizTemplate)
            .filter(QuizTemplate.name == "monthly_comprehensive")
            .first()
        )
        assert quiz, "monthly_comprehensive quiz template not found"

        db_count = len(quiz.questions or [])
        md_count = _count_markdown_questions(QUIZ_MARKDOWN_PATH)
        assert (
            db_count == md_count
        ), f"Quiz question count mismatch: db={db_count}, markdown={md_count}"
    finally:
        db.close()

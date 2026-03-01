"""
Patch monthly_comprehensive quiz template with help text instructions.

Default is dry-run. Use --apply to persist changes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from sqlalchemy.orm.attributes import flag_modified

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.quiz import QuizTemplate


TARGETS = {
    "q_11": {
        "text": "Está sentindo alguma dor no corpo?",
        "description": (
            "Se sim, onde sente essa dor?\n"
            "Com que frequência acontece?\n"
            "Qual a intensidade de 0 a 10?\n"
            "Alguma coisa alivia ou piora?"
        ),
    },
    "q_27": {
        "text": "Você consome ou tem dúvidas sobre chás, alimentos ou produtos naturais? Quais são suas dúvidas?",
        "description": (
            "Exemplo: chá de hibisco, maca peruana, cúrcuma, colágeno, isoflavonas, etc.\n"
            "O que você consome? Tem dúvidas sobre algo?"
        ),
    },
}


def _extract_questions(raw: Any) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if isinstance(raw, dict) and isinstance(raw.get("questions"), list):
        return raw["questions"], raw
    if isinstance(raw, list):
        return raw, None
    return [], None


def _find_question_index(
    questions: List[Dict[str, Any]], question_id: str, question_text: str
) -> Optional[int]:
    for idx, question in enumerate(questions):
        if question.get("id") == question_id:
            return idx
    for idx, question in enumerate(questions):
        if question.get("text", "").strip() == question_text:
            return idx
    return None


def patch_monthly_quiz(apply_changes: bool, template_name: str) -> int:
    load_dotenv()
    db = SessionLocal()
    try:
        quiz = (
            db.query(QuizTemplate)
            .filter(QuizTemplate.name == template_name)
            .first()
        )
        if not quiz:
            print(f"❌ Quiz template '{template_name}' not found.")
            return 1

        questions, container = _extract_questions(quiz.questions)
        if not questions:
            print(f"❌ Quiz template '{template_name}' has no questions.")
            return 1

        updates = []
        missing = []

        for question_id, target in TARGETS.items():
            question_text = target["text"]
            help_text = target["description"]
            idx = _find_question_index(questions, question_id, question_text)
            if idx is None:
                missing.append(question_id)
                continue

            question = questions[idx]
            before = question.get("description")
            if before != help_text:
                question["description"] = help_text
                updates.append(
                    {
                        "id": question.get("id"),
                        "text": question.get("text"),
                        "before": before,
                        "after": help_text,
                    }
                )

        if missing:
            print("⚠️  Perguntas não encontradas:", ", ".join(missing))

        if not updates:
            print("✅ Nenhuma atualização necessária.")
            return 0

        print(f"🔎 Encontradas {len(updates)} atualização(ões):")
        for update in updates:
            print(f"- {update['id']}: {update['text']}")

        if apply_changes:
            if container is not None:
                container["questions"] = questions
                quiz.questions = container
            else:
                quiz.questions = questions
            flag_modified(quiz, "questions")
            db.commit()
            print("✅ Alterações aplicadas com sucesso.")
        else:
            print("🧪 Dry-run: use --apply para salvar no banco.")

        return 0
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Patch monthly_comprehensive quiz help text."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database (default: dry-run).",
    )
    parser.add_argument(
        "--template-name",
        default="monthly_comprehensive",
        help="Quiz template name to update.",
    )
    args = parser.parse_args()

    raise SystemExit(patch_monthly_quiz(args.apply, args.template_name))


if __name__ == "__main__":
    main()

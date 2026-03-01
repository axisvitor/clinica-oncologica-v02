"""Exporta templates ativos do banco para Markdown em app/templates/arquivo.

Fonte de verdade: banco de dados. Este script gera uma visão legível.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database import SessionLocal
from app.models.quiz import QuizTemplate
from app.utils.timezone import now_sao_paulo


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "app" / "templates" / "arquivo" / "db_snapshot"

FLOW_FILES = {
    "onboarding": "FLUXO HORMON[IA] - 1 A 15 [DB].md",
    "daily_follow_up": "Fluxo HORMON[IA] - 16 A 45 [DB].md",
    "quiz_mensal": "Fluxo Hormon[IA] MENSAL PADRÃO [DB].md",
}


def _load_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    if raw_steps is None:
        return []
    if isinstance(raw_steps, str):
        try:
            raw_steps = json.loads(raw_steps)
        except json.JSONDecodeError:
            return []
    if isinstance(raw_steps, list):
        return [s for s in raw_steps if isinstance(s, dict)]
    return []


def _fetch_active_flow(kind_key: str) -> Optional[Dict[str, Any]]:
    query = text(
        """
        SELECT ftv.steps, ftv.version_number, ftv.template_name
        FROM flow_template_versions ftv
        JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
        WHERE fk.kind_key = :kind AND ftv.is_active = true
        ORDER BY ftv.version_number DESC
        LIMIT 1
        """
    )
    db = SessionLocal()
    try:
        res = db.execute(query, {"kind": kind_key}).fetchone()
        if not res:
            return None
        steps = _load_steps(res[0])
        return {
            "kind_key": kind_key,
            "template_name": res[2],
            "version_number": res[1],
            "steps": steps,
        }
    finally:
        db.close()


def _format_flow_markdown(flow: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Snapshot DB - {flow['kind_key']}")
    lines.append("")
    lines.append(
        f"- Template: {flow.get('template_name') or 'N/A'} | Versão: {flow.get('version_number')}"
    )
    lines.append(f"- Gerado em: {now_sao_paulo().isoformat()}")
    lines.append("")

    steps = sorted(flow.get("steps", []), key=lambda s: s.get("day", 0))
    if not steps:
        lines.append("_Nenhum step ativo encontrado no DB._")
        return "\n".join(lines) + "\n"

    for step in steps:
        day = step.get("day", "N/A")
        send_mode = step.get("send_mode", "single")
        messages = step.get("messages", []) or []

        lines.append(f"## Dia {day}")
        lines.append(f"- send_mode: `{send_mode}`")
        lines.append(f"- mensagens: {len(messages)}")
        lines.append("")

        if not messages:
            lines.append("_Sem mensagens configuradas_")
            lines.append("")
            continue

        for idx, msg in enumerate(messages, start=1):
            content = (msg or {}).get("content") or ""
            expects_response = (msg or {}).get("expects_response", False)
            lines.append(f"**Mensagem {idx}**")
            lines.append(f"- expects_response: `{expects_response}`")
            if content:
                lines.append("")
                lines.append(content.strip())
                lines.append("")
            else:
                lines.append("- conteúdo: _vazio_")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _select_monthly_quiz(templates: List[QuizTemplate]) -> List[QuizTemplate]:
    if not templates:
        return []
    preferred = []
    for tpl in templates:
        name = (tpl.name or "").lower()
        category = (tpl.category or "").lower()
        if "mensal" in name or "monthly" in name or "mensal" in category or "monthly" in category:
            preferred.append(tpl)
    return preferred or templates


def _format_quiz_markdown(templates: List[QuizTemplate]) -> str:
    lines: List[str] = []
    lines.append("# Snapshot DB - Quiz Templates")
    lines.append("")
    lines.append(f"- Gerado em: {now_sao_paulo().isoformat()}")
    lines.append("")

    if not templates:
        lines.append("_Nenhum quiz ativo encontrado no DB._")
        return "\n".join(lines) + "\n"

    for tpl in templates:
        lines.append(f"## {tpl.name} (v{tpl.version})")
        if tpl.description:
            lines.append(f"- descrição: {tpl.description}")
        if tpl.category:
            lines.append(f"- categoria: {tpl.category}")
        lines.append("")

        questions = tpl.questions or []
        if isinstance(questions, dict):
            questions = questions.get("questions", [])

        if not questions:
            lines.append("_Sem perguntas configuradas_")
            lines.append("")
            continue

        for idx, q in enumerate(questions, start=1):
            q_text = q.get("text") or q.get("question") or ""
            q_type = q.get("type") or "text"
            lines.append(f"**Pergunta {idx}**")
            lines.append(f"- id: `{q.get('id', '')}`")
            lines.append(f"- tipo: `{q_type}`")
            if q_text:
                lines.append(f"- texto: {q_text}")
            description = q.get("description") or q.get("help_text")
            if description:
                desc_lines = str(description).splitlines()
                lines.append(f"- descrição: {desc_lines[0]}")
                for extra_line in desc_lines[1:]:
                    lines.append(f"  {extra_line}")
            options = q.get("options") or []
            if options:
                lines.append("- opções:")
                for opt in options:
                    label = opt.get("text") or opt.get("label") or opt.get("value")
                    value = opt.get("value") or opt.get("id") or ""
                    lines.append(f"  - {label} ({value})")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def export_flows() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for kind_key, filename in FLOW_FILES.items():
        flow = _fetch_active_flow(kind_key)
        if not flow:
            content = (
                f"# Snapshot DB - {kind_key}\n\n"
                f"- Gerado em: {now_sao_paulo().isoformat()}\n\n"
                "_Nenhum template ativo encontrado no DB._\n"
            )
        else:
            content = _format_flow_markdown(flow)
        (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")


def export_quiz() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        templates = db.query(QuizTemplate).filter(QuizTemplate.is_active.is_(True)).all()
    finally:
        db.close()

    selected = _select_monthly_quiz(templates)
    content = _format_quiz_markdown(selected)
    (OUTPUT_DIR / "Quizz de Bem-Estar Mensal [DB].md").write_text(content, encoding="utf-8")


def main() -> None:
    export_flows()
    export_quiz()
    print("Export concluído em app/templates/arquivo.")


if __name__ == "__main__":
    main()

"""Prompt builder functions for LangGraph AI nodes."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.ai.pii_redaction import (
    PROMPT_PSEUDONYM,
    redact_patient_context,
    sanitize_prompt_text_for_external_ai,
)
from app.utils.text import clip_text


def _count_questions(text: str) -> int:
    if not text:
        return 0
    return text.count("?")


def _sanitize_prompt_text(text: str) -> str:
    return sanitize_prompt_text_for_external_ai(text)


def _format_examples(examples: List[Dict[str, str]] | None) -> str:
    if not examples:
        return ""
    formatted = "\nEXEMPLOS:\n"
    for ex in examples:
        formatted += f"Entrada: {ex.get('input', '')}\nSaida: {ex.get('output', '')}\n---\n"
    return formatted


def _clip_text(text: str, max_len: int = 260) -> str:
    return clip_text(text, max_len=max_len, ellipsis="…")


def _format_recent_interactions(
    interactions: List[Dict[str, Any]] | None,
) -> str:
    if not interactions:
        return ""
    lines = ["CONTEXTO DAS ULTIMAS INTERACOES (pergunta/resposta):"]
    for idx, item in enumerate(interactions[-2:], start=1):
        question = _clip_text(_sanitize_prompt_text(item.get("question", "")))
        answer = _clip_text(_sanitize_prompt_text(item.get("answer", "")))
        if question:
            lines.append(f"{idx}) Pergunta: {question}")
        if answer:
            lines.append(f"   Resposta: {answer}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines) + "\n"


def _replace_patient_name(text: str, patient_name: str) -> str:
    if not text or not patient_name:
        return text
    return (
        text.replace("[NOME]", PROMPT_PSEUDONYM)
        .replace("[nome]", PROMPT_PSEUDONYM)
        .replace("{patient_name}", PROMPT_PSEUDONYM)
    )


def build_humanization_prompt(
    template: str,
    ai_instructions: str | None,
    recent_interactions: List[Dict[str, Any]] | None = None,
) -> str:
    safe_template = _sanitize_prompt_text(template)
    question_count = _count_questions(safe_template)
    instructions = ""
    if ai_instructions:
        instructions = (
            f"\nINSTRUCOES DO TEMPLATE:\n{_sanitize_prompt_text(ai_instructions)}\n"
        )
    interactions_section = _format_recent_interactions(recent_interactions)
    context_instruction = ""
    if interactions_section:
        context_instruction = (
            "Use o contexto apenas para manter coerencia e tom. "
            "Nao responda as mensagens anteriores e nao altere o proposito do template.\n"
        )
    return f"""Voce vai reescrever a mensagem abaixo mantendo o mesmo proposito.
Nao adicione informacao nova e mantenha a mesma quantidade de perguntas (qtd={question_count}).
Mantenha a ordem das perguntas e preserve o sentido de cada uma.
Se houver placeholders (ex: [LINK DO QUIZ], {{patient_name}}), mantenha-os exatamente.
Evite diagn\u00f3sticos, conselhos m\u00e9dicos ou promessas novas.
Escreva em portugues do Brasil.
Responda apenas com a mensagem final, sem listas e sem aspas.
Finalize com frase completa e pontuacao.
{context_instruction}
{interactions_section}

MENSAGEM ORIGINAL:
{safe_template}
{instructions}
MENSAGEM REESCRITA:
"""


def build_question_variation_prompt(
    base_question: str,
    ai_instructions: str | None,
    recent_interactions: List[Dict[str, Any]] | None = None,
) -> str:
    safe_question = _sanitize_prompt_text(base_question)
    question_count = _count_questions(safe_question)
    instructions = ""
    if ai_instructions:
        instructions = (
            f"\nINSTRUCOES DO TEMPLATE:\n{_sanitize_prompt_text(ai_instructions)}\n"
        )
    interactions_section = _format_recent_interactions(recent_interactions)
    context_instruction = ""
    if interactions_section:
        context_instruction = (
            "Use o contexto apenas para manter coerencia e tom. "
            "Nao responda as mensagens anteriores e nao altere o proposito do template.\n"
        )
    return f"""Reescreva a pergunta abaixo com palavras diferentes, mantendo o mesmo proposito.
Mantenha a mesma quantidade de perguntas (qtd={question_count}) e nao adicione informacao nova.
Preserve a ordem e o foco da pergunta original.
Nao repita literalmente nenhuma pergunta recente ja enviada.
Use estruturas frasais diferentes das perguntas anteriores quando houver historico.
Se houver placeholders (ex: [LINK DO QUIZ], {{patient_name}}), mantenha-os exatamente.
Evite diagnósticos, conselhos médicos ou promessas novas.
Escreva em portugues do Brasil.
Responda apenas com a pergunta final, sem listas e sem aspas.
Finalize com frase completa e pontuacao.
{context_instruction}
{interactions_section}

PERGUNTA BASE:
{safe_question}
{instructions}
NOVA PERGUNTA:
"""


def build_sentiment_prompt(response: str, context_snapshot: Dict[str, Any]) -> str:
    safe_context = redact_patient_context(context_snapshot)
    return f"""Analise a resposta do paciente e retorne apenas JSON valido.

RESPOSTA DO PACIENTE: {response}
CONTEXTO (resumido): {json.dumps(safe_context, ensure_ascii=False)}

Retorne JSON com as chaves:
- sentiment: positive|neutral|negative
- confidence: 0.0-1.0
- emotional_indicators: lista de sentimentos detectados
- medical_concerns: lista de preocupacoes medicas detectadas
- requires_attention: true|false
- key_themes: lista de temas principais
- suggested_follow_up: tipo de seguimento recomendado
"""


def build_empathetic_prompt(
    patient_response: str,
    conversation_history: List[str],
    context_snapshot: Dict[str, Any],
    examples: List[Dict[str, str]] | None,
    *,
    allow_questions: bool = False,
    day_complete: bool = False,
) -> str:
    history = "\n".join(conversation_history[-3:]) if conversation_history else "Primeira interacao"
    examples_section = _format_examples(examples)
    question_instruction = (
        "Se fizer pergunta, faca no maximo uma."
        if allow_questions
        else "Nao faca perguntas."
    )
    completion_instruction = (
        "Se for apropriado, informe que as perguntas de hoje terminaram."
        if day_complete
        else ""
    )
    return f"""Crie uma resposta empatica e de apoio ao paciente.
Responda com uma unica mensagem, sem listas e sem aspas.
{question_instruction}
{completion_instruction}
Nao antecipe mensagens futuras.
Escreva em portugues do Brasil e finalize com pontuacao.

RESPOSTA DO PACIENTE:
{patient_response}

HISTORICO:
{history}

CONTEXTO (resumido): {json.dumps(redact_patient_context(context_snapshot), ensure_ascii=False)}
{examples_section}
RESPOSTA:
"""

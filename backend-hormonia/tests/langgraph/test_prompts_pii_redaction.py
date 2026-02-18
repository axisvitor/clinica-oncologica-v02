from __future__ import annotations

from app.ai.langgraph.prompts import (
    _replace_patient_name,
    build_humanization_prompt,
    build_question_variation_prompt,
)


def test_replace_patient_name_uses_pseudonym_instead_of_real_name():
    template = "Oi [NOME], tudo bem, {patient_name}? Seu registro [nome] segue ativo."
    output = _replace_patient_name(template, "Maria Souza")

    assert "Maria Souza" not in output
    assert output.count("Paciente") == 3


def test_build_humanization_prompt_redacts_patient_identifiers():
    prompt = build_humanization_prompt(
        template=(
            'name: "Maria Souza"\n'
            "cpf: 123.456.789-09\n"
            "telefone: +55 11 98888-7777\n"
            "email: maria@example.com\n"
            "Mensagem: Olá [NOME], como você está?"
        ),
        ai_instructions='Use patient_id: "abc-123" para rastrear o caso.',
        recent_interactions=[
            {
                "question": "Maria Souza, confirme seu CPF 123.456.789-09?",
                "answer": "Meu telefone é +55 11 97777-6666 e email maria@example.com",
            }
        ],
    )

    assert "Maria Souza" not in prompt
    assert "123.456.789-09" not in prompt
    assert "+55 11 98888-7777" not in prompt
    assert "+55 11 97777-6666" not in prompt
    assert "maria@example.com" not in prompt
    assert "abc-123" not in prompt
    assert "Paciente" in prompt
    assert "[REDACTED]" in prompt


def test_build_question_variation_prompt_redacts_patient_identifiers():
    prompt = build_question_variation_prompt(
        base_question=(
            '{"patient_name":"Maria Souza","patient_id":"id-998","question":"Como foi seu dia?"}'
        ),
        ai_instructions='Observacao: name: "Maria Souza" / phone: "+55 11 98888-7777".',
        recent_interactions=[
            {
                "question": "Maria Souza conseguiu responder?",
                "answer": "Sim, meu CPF é 123.456.789-09",
            }
        ],
    )

    assert "Maria Souza" not in prompt
    assert "id-998" not in prompt
    assert "+55 11 98888-7777" not in prompt
    assert "123.456.789-09" not in prompt
    assert "Paciente" in prompt
    assert "[REDACTED]" in prompt


def test_build_question_variation_prompt_enforces_non_repetition_instruction():
    prompt = build_question_variation_prompt(
        base_question="Como voce esta se sentindo hoje?",
        ai_instructions=None,
        recent_interactions=[
            {"question": "Como voce esta se sentindo hoje?", "answer": "Tudo bem"}
        ],
    )

    assert "Nao repita literalmente nenhuma pergunta recente ja enviada." in prompt
    assert "Use estruturas frasais diferentes das perguntas anteriores" in prompt

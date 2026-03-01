from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.patient.flow_coordinator.message_generator import MessageGenerator


@pytest.mark.asyncio
async def test_generate_ai_content_redacts_patient_identifiers():
    generator = MessageGenerator(
        db_session=Mock(),
        agent_id="test-agent",
        logger=Mock(),
        template_loader=Mock(),
    )
    generator.gemini_client = AsyncMock()
    generator.gemini_client.humanize_flow_message.return_value = "Mensagem segura."

    template = SimpleNamespace(base_content="Olá {patient_name}", ai_instructions="Seja empático.")
    context = {
        "patient_name": "Maria Souza",
        "phone": "+5511988887777",
        "cpf": "123.456.789-09",
        "diagnosis": "linfoma",
        "conversation_history": ["Maria Souza informou CPF 123.456.789-09"],
        "personalization_hints": ["curto"],
    }

    result = await generator._generate_ai_content(template, context)

    assert result == "Mensagem segura."
    call = generator.gemini_client.humanize_flow_message.call_args
    assert call.kwargs["patient_name"] == "Paciente"
    assert "phone" not in call.kwargs["patient_context"]
    assert "cpf" not in call.kwargs["patient_context"]
    assert "Maria Souza" not in call.kwargs["conversation_history"][0]

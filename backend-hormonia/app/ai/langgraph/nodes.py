"""LangGraph nodes for flow message execution."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig

from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo
from app.services.ai.guardrails import OutputKind
from app.schemas.ai_schemas import AIResponseValidation

from .state import FlowMessageState
from .ai_state import AIState

logger = logging.getLogger(__name__)


def _require_handler(config: Optional[RunnableConfig]) -> Any:
    configurable = (config or {}).get("configurable") or {}
    handler = configurable.get("handler")
    if handler is None:
        raise RuntimeError(
            "Flow handler missing. Pass it via config['configurable']['handler']."
        )
    return handler


def _load_flow_state(handler: Any, flow_state_id: Any, patient_id: Any) -> Any:
    flow_state = None
    if flow_state_id:
        from app.models.flow import PatientFlowState

        flow_state = (
            handler.db.query(PatientFlowState)
            .filter(PatientFlowState.id == flow_state_id)
            .first()
        )
    if flow_state is None and hasattr(handler, "flow_state_repo"):
        flow_state = handler.flow_state_repo.get_active_flow(patient_id)
    return flow_state


def _count_questions(text: str) -> int:
    if not text:
        return 0
    return text.count("?")


def _format_examples(examples: List[Dict[str, str]] | None) -> str:
    if not examples:
        return ""
    formatted = "\nEXEMPLOS:\n"
    for ex in examples:
        formatted += f"Entrada: {ex.get('input', '')}\nSaida: {ex.get('output', '')}\n---\n"
    return formatted


def _replace_patient_name(text: str, patient_name: str) -> str:
    if not text or not patient_name:
        return text
    return (
        text.replace("[NOME]", patient_name)
        .replace("[nome]", patient_name)
        .replace("{patient_name}", patient_name)
    )


def _build_humanization_prompt(
    template: str,
    ai_instructions: str | None,
) -> str:
    question_count = _count_questions(template)
    instructions = ""
    if ai_instructions:
        instructions = f"\nINSTRUCOES DO TEMPLATE:\n{ai_instructions}\n"
    return f"""Voce vai reescrever a mensagem abaixo mantendo o mesmo proposito.
Nao adicione informacao nova e mantenha a mesma quantidade de perguntas (qtd={question_count}).
Escreva em portugues do Brasil.
Responda apenas com a mensagem final, sem listas e sem aspas.
Finalize com frase completa e pontuacao.

MENSAGEM ORIGINAL:
{template}
{instructions}
MENSAGEM REESCRITA:
"""


def _build_question_variation_prompt(
    base_question: str,
    ai_instructions: str | None,
) -> str:
    question_count = _count_questions(base_question)
    instructions = ""
    if ai_instructions:
        instructions = f"\nINSTRUCOES DO TEMPLATE:\n{ai_instructions}\n"
    return f"""Reescreva a pergunta abaixo com palavras diferentes, mantendo o mesmo proposito.
Mantenha a mesma quantidade de perguntas (qtd={question_count}) e nao adicione informacao nova.
Escreva em portugues do Brasil.
Responda apenas com a pergunta final, sem listas e sem aspas.
Finalize com frase completa e pontuacao.

PERGUNTA BASE:
{base_question}
{instructions}
NOVA PERGUNTA:
"""


def _build_sentiment_prompt(response: str, context_snapshot: Dict[str, Any]) -> str:
    return f"""Analise a resposta do paciente e retorne apenas JSON valido.

RESPOSTA DO PACIENTE: {response}
CONTEXTO (resumido): {json.dumps(context_snapshot, ensure_ascii=False)}

Retorne JSON com as chaves:
- sentiment: positive|neutral|negative
- confidence: 0.0-1.0
- emotional_indicators: lista de sentimentos detectados
- medical_concerns: true|false
- requires_attention: true|false
- key_themes: lista de temas principais
- suggested_follow_up: tipo de seguimento recomendado
"""


def _build_empathetic_prompt(
    patient_response: str,
    conversation_history: List[str],
    context_snapshot: Dict[str, Any],
    examples: List[Dict[str, str]] | None,
) -> str:
    history = "\n".join(conversation_history[-3:]) if conversation_history else "Primeira interacao"
    examples_section = _format_examples(examples)
    return f"""Crie uma resposta empatica e de apoio ao paciente.
Responda com uma unica mensagem, sem listas e sem aspas.
Se fizer pergunta, faca no maximo uma.
Nao antecipe mensagens futuras.
Escreva em portugues do Brasil e finalize com pontuacao.

RESPOSTA DO PACIENTE:
{patient_response}

HISTORICO:
{history}

CONTEXTO (resumido): {json.dumps(context_snapshot, ensure_ascii=False)}
{examples_section}
RESPOSTA:
"""


def _parse_sentiment_analysis(text: str) -> Dict[str, Any]:
    from json import JSONDecodeError

    try:
        parsed = json.loads(text)
    except (JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON in sentiment analysis: {exc}") from exc

    validated = AIResponseValidation.validate_sentiment(parsed)
    return validated.model_dump()


def _get_gemini_client():
    from app.ai.client import get_gemini_client

    return get_gemini_client()


def _normalize_send_mode(send_mode: str | None) -> str:
    if not send_mode:
        return "single"
    normalized = send_mode.strip().lower()
    aliases = {
        "sequential_wait": "wait_each",
        "sequential": "sequential_auto",
        "sequence": "sequential_auto",
    }
    return aliases.get(normalized, normalized)


async def load_flow_context(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState:
    """Load patient, flow template, and current flow state."""
    handler = _require_handler(config)
    patient_id = state["patient_id"]
    day_number = state["day_number"]
    flow_kind = state["flow_kind"]

    patient = handler.db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return {"result": {"status": "error", "message": "Patient not found"}}

    day_config = await handler._get_day_config(flow_kind, day_number)
    if not day_config:
        logger.info("No config for day %s in %s - skipping", day_number, flow_kind)
        return {
            "result": {
                "status": "skip",
                "message": f"No messages configured for day {day_number}",
            },
        }

    messages = day_config.get("messages", [])
    send_mode = _normalize_send_mode(day_config.get("send_mode", "single"))

    if not messages:
        logger.info("No messages for day %s in %s - skipping", day_number, flow_kind)
        return {
            "result": {
                "status": "skip",
                "message": f"No messages configured for day {day_number}",
            },
        }

    flow_state = await handler._get_or_create_flow_state(patient_id, flow_kind)
    if not flow_state:
        return {
            "result": {
                "status": "error",
                "message": f"No active flow template for flow_kind={flow_kind}",
            },
        }
    step_data = dict(flow_state.step_data or {})

    previous_day = step_data.get("current_flow_day")
    if previous_day == day_number:
        if step_data.get("day_complete"):
            return {
                "result": {"status": "day_complete", "day": day_number},
            }
        if step_data.get("awaiting_response"):
            return {
                "result": {
                    "status": "waiting",
                    "day": day_number,
                    "message_index": step_data.get("current_day_message_index", 0),
                },
            }
    if previous_day is not None and previous_day != day_number:
        logger.debug(
            "Day changed from %s to %s - resetting message index",
            previous_day,
            day_number,
        )
        step_data["current_day_message_index"] = 0
        step_data["day_complete"] = False
        step_data["awaiting_response"] = False

    current_index = step_data.get("current_day_message_index", 0)
    if current_index < 0 or current_index >= len(messages):
        logger.warning(
            "current_day_message_index out of range (%s) for day %s in %s; resetting to 0",
            current_index,
            day_number,
            flow_kind,
        )
        if step_data.get("day_complete"):
            return {
                "result": {"status": "day_complete", "day": day_number},
            }
        current_index = 0
        step_data["current_day_message_index"] = current_index

    step_data["current_flow_day"] = day_number
    step_data["flow_kind"] = flow_kind
    step_data["current_day_message_index"] = current_index
    flow_state.step_data = step_data

    return {
        "flow_state_id": getattr(flow_state, "id", None),
        "flow_state_step_data": step_data,
        "day_config": day_config,
        "messages": messages,
        "send_mode": send_mode,
        "current_index": current_index,
    }


async def dispatch_send_mode(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState:
    """Dispatch to the correct sending behavior based on send_mode."""
    if state.get("result"):
        return {}

    handler = _require_handler(config)
    patient_id = state["patient_id"]
    patient = handler.db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return {"result": {"status": "error", "message": "Patient not found"}}

    flow_state = _load_flow_state(handler, state.get("flow_state_id"), patient_id)
    if not flow_state:
        return {"result": {"status": "error", "message": "Flow state not found"}}
    flow_state_step_data = state.get("flow_state_step_data")
    if isinstance(flow_state_step_data, dict):
        flow_state.step_data = flow_state_step_data

    day_number = state["day_number"]
    flow_kind = state["flow_kind"]
    day_config = state.get("day_config") or {}
    messages = state.get("messages") or []
    send_mode = _normalize_send_mode(state.get("send_mode") or "single")
    current_index = state.get("current_index", 0)

    result: Dict[str, Any]
    if not messages:
        return {
            "result": {"status": "skip", "message": f"No messages configured for day {day_number}"},
        }

    if send_mode == "sequential_auto":
        result = await handler._send_all_sequential(
            patient,
            messages,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
    elif send_mode == "wait_response":
        if current_index == 0:
            first_expects_response = messages[0].get("expects_response", True)
            if not first_expects_response:
                result = await handler._send_wait_each_with_auto_advance(
                    patient,
                    messages,
                    0,
                    flow_state,
                    day_number,
                    flow_kind,
                    day_config,
                )
            else:
                result = await handler._send_message_and_wait(
                    patient,
                    messages,
                    0,
                    flow_state,
                    day_number,
                    flow_kind,
                    day_config,
                )
        else:
            result = await handler._send_remaining_after_response(
                patient,
                messages,
                current_index,
                flow_state,
                day_number,
                flow_kind,
                day_config,
            )
    elif send_mode == "wait_each":
        result = await handler._send_wait_each_with_auto_advance(
            patient,
            messages,
            current_index,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
    elif send_mode == "single":
        if len(messages) > 1:
            logger.warning(
                "send_mode=single but %s messages configured for day %s in %s; sending first only",
                len(messages),
                day_number,
                flow_kind,
            )
        result = await handler._send_all_sequential(
            patient,
            messages[:1],
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
    else:
        logger.warning(
            "Unknown send_mode '%s' for day %s in %s; defaulting to sequential_auto",
            send_mode,
            day_number,
            flow_kind,
        )
        result = await handler._send_all_sequential(
            patient,
            messages,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )

    return {"result": result}


async def load_response_context(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState:
    """Load flow state and prepare continuation after a patient response."""
    handler = _require_handler(config)
    patient_id = state["patient_id"]

    flow_state = handler.flow_state_repo.get_active_flow(patient_id)
    if not flow_state:
        return {"result": {"status": "no_active_flow"}}

    step_data = flow_state.step_data or {}
    current_day = step_data.get("current_flow_day")
    flow_kind = step_data.get("flow_kind")
    if not current_day or not flow_kind:
        return {"result": {"status": "not_awaiting", "message": "Missing flow context"}}
    if step_data.get("day_complete") and not step_data.get("awaiting_response"):
        return {"result": {"status": "day_complete", "day": current_day}}

    day_config = await handler._get_day_config(flow_kind, current_day)
    if not day_config:
        return {"result": {"status": "no_config"}}

    messages = day_config.get("messages", [])
    send_mode = _normalize_send_mode(day_config.get("send_mode", "single"))
    current_index = step_data.get("current_day_message_index", 0)

    if current_index < 0 or (messages and current_index >= len(messages)):
        logger.warning(
            "current_day_message_index out of range (%s) for response continuation; clamping",
            current_index,
        )
        max_index = max(len(messages) - 1, 0)
        current_index = min(max(current_index, 0), max_index)
        step_data["current_day_message_index"] = current_index

    awaiting_response = step_data.get("awaiting_response", False)
    if not awaiting_response:
        return {
            "result": {"status": "not_awaiting", "message": "Not waiting for response"},
        }

    next_index = current_index + 1
    if next_index >= len(messages):
        step_data["day_complete"] = True
        step_data["awaiting_response"] = False
        step_data["last_response_at"] = now_sao_paulo().isoformat()
        flow_state.step_data = step_data
        handler.db.commit()
        return {"result": {"status": "day_complete", "day": current_day}}

    return {
        "flow_state_id": getattr(flow_state, "id", None),
        "flow_state_step_data": dict(flow_state.step_data or {}),
        "day_config": day_config,
        "messages": messages,
        "send_mode": send_mode,
        "current_index": next_index,
        "day_number": current_day,
        "flow_kind": flow_kind,
    }


async def dispatch_response_continuation(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState:
    """Send the next message(s) after a patient response."""
    if state.get("result"):
        return {}

    handler = _require_handler(config)
    patient_id = state["patient_id"]
    patient = handler.db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return {"result": {"status": "error", "message": "Patient not found"}}

    flow_state = _load_flow_state(handler, state.get("flow_state_id"), patient_id)
    if not flow_state:
        return {"result": {"status": "error", "message": "Flow state not found"}}
    flow_state_step_data = state.get("flow_state_step_data")
    if isinstance(flow_state_step_data, dict):
        flow_state.step_data = flow_state_step_data

    day_number = state["day_number"]
    flow_kind = state["flow_kind"]
    day_config = state.get("day_config") or {}
    messages = state.get("messages") or []
    send_mode = _normalize_send_mode(state.get("send_mode") or "single")
    current_index = state.get("current_index", 0)

    # Record response timestamp before continuing
    step_data = flow_state.step_data or {}
    if not step_data.get("last_response_at"):
        step_data["last_response_at"] = now_sao_paulo().isoformat()
        flow_state.step_data = step_data
        handler.db.commit()

    if send_mode == "wait_response":
        result = await handler._send_remaining_after_response(
            patient,
            messages,
            current_index,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
        return {"result": result}

    if send_mode == "wait_each":
        result = await handler._send_wait_each_with_auto_advance(
            patient,
            messages,
            current_index,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
        return {"result": result}

    return {"result": {"status": "ok"}}
# --- Unified AI Nodes ---

async def humanize_node(state: AIState) -> AIState:
    """Node for humanizing a template message."""
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    patient_name = context.get("patient_name") or context.get("name") or "Paciente"
    template = state.get("template", "") or ""
    template = _replace_patient_name(template, patient_name)
    metadata = state.get("metadata") or {}
    prompt = _build_humanization_prompt(
        template=template,
        ai_instructions=metadata.get("ai_instructions"),
    )
    output = await client.generate_content(
        prompt,
        require_ending_punctuation=True,
        guardrail_retries=2,
    )
    return {**state, "output": output, "confidence": 0.9}


async def sentiment_node(state: AIState) -> AIState:
    """Node for analyzing patient response sentiment."""
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    context_snapshot = client.compact_patient_context(context)
    prompt = _build_sentiment_prompt(
        response=state.get("input_text", ""),
        context_snapshot=context_snapshot,
    )
    analysis_text = await client.generate_content(
        prompt,
        output_kind=OutputKind.JSON,
        required_keys=[
            "sentiment",
            "confidence",
            "emotional_indicators",
            "medical_concerns",
            "requires_attention",
            "key_themes",
            "suggested_follow_up",
        ],
    )
    analysis = _parse_sentiment_analysis(analysis_text)
    return {**state, "output": analysis, "confidence": analysis.get("confidence", 0.0)}


async def question_variation_node(state: AIState) -> AIState:
    """Node for question variation."""
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    patient_name = context.get("patient_name") or context.get("name") or ""
    metadata = state.get("metadata") or {}
    base_question = _replace_patient_name(state.get("input_text", "") or "", patient_name)
    prompt = _build_question_variation_prompt(
        base_question=base_question,
        ai_instructions=metadata.get("ai_instructions"),
    )
    output = await client.generate_content(
        prompt,
        require_ending_punctuation=True,
        guardrail_retries=2,
    )
    return {**state, "output": output, "confidence": 0.9}


async def empathetic_follow_up_node(state: AIState) -> AIState:
    """Node for empathetic follow-up generation."""
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    context_snapshot = client.compact_patient_context(context)
    metadata = state.get("metadata") or {}
    prompt = _build_empathetic_prompt(
        patient_response=state.get("input_text", "") or "",
        conversation_history=state.get("history", []) or [],
        context_snapshot=context_snapshot,
        examples=metadata.get("few_shot_examples") or [],
    )
    output = await client.generate_content(
        prompt,
        require_ending_punctuation=True,
        guardrail_retries=2,
    )
    return {**state, "output": output, "confidence": 0.9}


async def generate_node(state: AIState) -> AIState:
    """Node for generic content generation."""
    client = _get_gemini_client()
    # Extract parameters
    prompt = state.get("input_text", "")
    output_kind_str = state.get("output_kind", "message")

    from app.services.ai.guardrails import OutputKind
    try:
        output_kind = OutputKind(output_kind_str)
    except ValueError:
        output_kind = OutputKind.MESSAGE

    # Delegate to GeminiClient
    output = await client.generate_content(
        prompt=prompt,
        output_kind=output_kind,
        **(state.get("metadata") or {})
    )

    return {**state, "output": output}

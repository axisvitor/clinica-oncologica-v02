"""
Validation against real flow templates stored in the database.

Coverage:
- onboarding
- daily_follow_up
- quiz_mensal
"""

import re
from typing import Dict, Any, List
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow.sequential_message_handler import SequentialMessageHandler


FLOW_SPECS = {
    "onboarding": {
        "day_start": 1,
        "day_end": 15,
        "expected_days": [1, 2, 3, 5, 7, 9, 11, 13, 15],
    },
    "daily_follow_up": {
        "day_start": 16,
        "day_end": 45,
        "expected_days": [
            16,
            18,
            20,
            22,
            24,
            26,
            28,
            30,
            32,
            34,
            36,
            38,
            40,
            42,
            44,
            45,
        ],
    },
    "quiz_mensal": {
        "day_start": 1,
        "day_end": 30,
        "expected_days": [1, 4, 8, 11, 15, 18, 22, 26, 30],
    },
}

QUESTION_PHRASES = [
    "me conta",
    "me conte",
    "me responde",
    "me responda",
    "me responde com",
    "me responda com",
    "me diz",
    "me diga",
    "me fala",
    "me fale",
    "como voce",
    "como você",
    "como esta",
    "como está",
    "como ta",
    "como tá",
    "voce tem",
    "você tem",
    "voce ja",
    "você já",
    "tem algo",
    "tem alguma",
    "tem algum",
    "posso contar com voce",
    "posso contar com você",
    "pode me dizer",
    "pode me falar",
    "responda com",
]


def _load_active_steps(flow_kind: str) -> List[Dict[str, Any]]:
    """Load active flow template steps from the database."""
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                SELECT ftv.steps
                FROM flow_template_versions ftv
                JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
                WHERE fk.kind_key = :kind AND ftv.is_active = true
                """
            ),
            {"kind": flow_kind},
        ).fetchone()

        if not result or not result[0]:
            pytest.fail(f"No active flow template steps found for {flow_kind}")

        return result[0]
    finally:
        db.close()


def _build_day_configs(flow_kind: str) -> Dict[int, Dict[str, Any]]:
    """Build day->config map from DB steps."""
    steps = _load_active_steps(flow_kind)
    configs = {}
    for step in steps:
        day = step.get("day") if isinstance(step, dict) else None
        if day is None:
            continue
        try:
            day_int = int(day)
        except Exception:
            continue
        configs[day_int] = step
    return configs


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _message_content(message: object) -> str:
    if isinstance(message, dict):
        return message.get("content") or ""
    return ""


def _is_question_message(message: object) -> bool:
    content = _normalize_text(_message_content(message))
    if not content:
        return False
    if "?" in content:
        return True
    if re.search(r"\(\s*\)", content):
        return True
    return any(phrase in content for phrase in QUESTION_PHRASES)


def _requires_response(message: object) -> bool:
    if isinstance(message, dict):
        if message.get("expects_response") is True:
            return True
        if message.get("expects_response") is False:
            return False
    return _is_question_message(message)


def _response_required_indices(messages: List[Dict[str, Any]]) -> List[int]:
    return [idx for idx, msg in enumerate(messages) if _requires_response(msg)]


def _count_responses_for_day(state_data: Dict[str, Any], day: int) -> int:
    responses = (state_data or {}).get("responses_by_message") or {}
    prefix = f"day_{day}_msg_"
    return sum(1 for key in responses if key.startswith(prefix))


def _build_handler_engine(day_configs: Dict[int, Dict[str, Any]], flow_kind: str):
    patient = MagicMock(spec=Patient)
    patient.id = uuid4()
    patient.name = "Paciente Teste"
    patient.preferred_name = None
    patient.treatment_type = "hormone_therapy"

    flow_state = PatientFlowState()
    flow_state.id = uuid4()
    flow_state.step_data = {}
    flow_state.current_step = 0
    flow_state.status = "active"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = patient
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()

    handler = SequentialMessageHandler(mock_db, use_ai_personalization=False)

    async def _get_day_config(kind, day):
        if kind != flow_kind:
            return None
        return day_configs.get(day)

    handler._get_day_config = AsyncMock(side_effect=_get_day_config)
    handler._get_or_create_flow_state = AsyncMock(return_value=flow_state)
    handler._send_flow_message = AsyncMock(return_value=True)
    handler.flow_state_repo = MagicMock()
    handler.flow_state_repo.get_active_flow = MagicMock(return_value=flow_state)

    mock_gemini = MagicMock()
    mock_gemini.analyze_response_sentiment = AsyncMock(
        return_value={
            "sentiment": "neutral",
            "requires_attention": False,
            "medical_concerns": False,
            "emotional_indicators": [],
        }
    )

    mock_memory = MagicMock()
    mock_memory.update_last_pattern_engagement = AsyncMock(return_value=None)
    mock_memory.store_message_pattern = AsyncMock(return_value=None)

    engine = EnhancedFlowEngine(
        mock_db,
        gemini_client=mock_gemini,
        conversation_memory=mock_memory,
        platform_sync=MagicMock(),
        template_loader=MagicMock(),
        template_cache=MagicMock(),
    )
    engine.patient_repo = MagicMock()
    engine.patient_repo.get = MagicMock(return_value=patient)
    engine.flow_state_repo = MagicMock()
    engine.flow_state_repo.get_active_flow = MagicMock(return_value=flow_state)

    return patient, flow_state, handler, engine


@pytest.mark.integration
@pytest.mark.parametrize("flow_kind", FLOW_SPECS.keys())
def test_db_flow_templates_match_expected_days(flow_kind):
    day_configs = _build_day_configs(flow_kind)
    expected_days = FLOW_SPECS[flow_kind]["expected_days"]
    actual_days = sorted(day_configs.keys())
    assert actual_days == expected_days


@pytest.mark.integration
@pytest.mark.parametrize("flow_kind", FLOW_SPECS.keys())
def test_db_flow_templates_question_expectations(flow_kind):
    day_configs = _build_day_configs(flow_kind)
    issues = []

    for day, config in sorted(day_configs.items()):
        messages = config.get("messages") or []
        if not messages:
            issues.append(f"{flow_kind} day {day} has no messages configured")
            continue

        for idx, msg in enumerate(messages):
            content = _message_content(msg)
            variations = msg.get("variations") if isinstance(msg, dict) else []
            if not content and not variations:
                issues.append(f"{flow_kind} day {day} msg {idx} missing content")

            if _is_question_message(msg):
                expects_response = (
                    msg.get("expects_response") if isinstance(msg, dict) else None
                )
                if expects_response is False:
                    issues.append(
                        f"{flow_kind} day {day} msg {idx} is a question but expects_response is False"
                    )

    assert not issues, "Flow template validation issues:\n" + "\n".join(issues)


@pytest.mark.integration
@pytest.mark.parametrize("flow_kind", FLOW_SPECS.keys())
def test_db_flow_templates_send_mode_consistency(flow_kind):
    day_configs = _build_day_configs(flow_kind)
    issues = []

    for day, config in sorted(day_configs.items()):
        messages = config.get("messages") or []
        send_mode = config.get("send_mode", "single")
        response_indices = _response_required_indices(messages)

        if send_mode == "sequential_auto":
            if response_indices:
                issues.append(
                    f"{flow_kind} day {day} sequential_auto should not require responses"
                )
        elif send_mode == "wait_response":
            if len(response_indices) != 1:
                issues.append(
                    f"{flow_kind} day {day} wait_response must have exactly one response"
                )
            elif response_indices[0] != 0:
                issues.append(
                    f"{flow_kind} day {day} wait_response must wait on first message"
                )
        elif send_mode == "wait_each":
            if not response_indices:
                issues.append(
                    f"{flow_kind} day {day} wait_each must have at least one response"
                )
        elif send_mode == "single":
            if len(messages) != 1:
                issues.append(f"{flow_kind} day {day} single must have one message")
        else:
            issues.append(f"{flow_kind} day {day} unknown send_mode: {send_mode}")

    assert not issues, "Flow template send_mode issues:\n" + "\n".join(issues)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("flow_kind", FLOW_SPECS.keys())
async def test_flow_simulation_day_by_day(flow_kind):
    day_configs = _build_day_configs(flow_kind)
    spec = FLOW_SPECS[flow_kind]
    expected_days = set(spec["expected_days"])

    patient, flow_state, handler, engine = _build_handler_engine(
        day_configs, flow_kind
    )

    for day in range(spec["day_start"], spec["day_end"] + 1):
        flow_state.current_step = day

        send_result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=day,
            flow_kind=flow_kind,
        )

        if day not in expected_days:
            assert send_result["status"] == "skip"
            continue

        messages = day_configs[day]["messages"] or []
        assert messages

        response_indices = _response_required_indices(messages)
        expected_response_count = len(response_indices)
        if not response_indices:
            assert flow_state.step_data.get("awaiting_response") is False
            assert flow_state.step_data.get("day_complete") is True
            assert _count_responses_for_day(flow_state.state_data, day) == 0
            continue

        while flow_state.step_data.get("awaiting_response"):
            current_index = flow_state.step_data.get("current_day_message_index", 0)
            assert current_index in response_indices

            response_context = {
                "flow_day": flow_state.step_data.get("current_flow_day"),
                "flow_kind": flow_state.step_data.get("flow_kind"),
                "message_index": current_index,
            }
            response_text = (
                f"Resposta {flow_kind} dia {day} pergunta {current_index + 1}"
            )

            response_result = await engine.process_patient_response(
                patient_id=patient.id,
                response_text=response_text,
                response_context=response_context,
            )
            assert response_result["status"] == "processed"

            response_key = f"day_{day}_msg_{current_index}"
            stored = flow_state.state_data["responses_by_message"][response_key]
            assert stored["response_text"] == response_text
            assert stored["flow_day"] == day
            assert stored["message_index"] == current_index

            await handler.handle_response_and_continue(patient.id)

        assert flow_state.step_data.get("day_complete") is True
        assert (
            _count_responses_for_day(flow_state.state_data, day)
            == expected_response_count
        )

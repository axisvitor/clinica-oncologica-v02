#!/usr/bin/env python3
"""Run real LangGraph flow tests against real DB + AI services.

This script executes:
1) Patient flow message graph (send_day_messages)
2) Response reception (ResponseProcessor.process_inbound_message)
3) AI question optimization (humanization graph)

Guards:
- Requires explicit CONFIRM_REAL_SEND=1 to avoid accidental sends
- Requires real AI (ALLOW_AI_SIMULATION=false and AI_GEMINI_API_KEY set)
- Requires explicit test patient identifiers (phone or id)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4
import re

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid integer for {name}: {value}") from exc


def _parse_uuid(value: str, name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid UUID for {name}: {value}") from exc


def _phone_variants(phone: str) -> list[str]:
    """
    Generate likely phone variants to improve LGPD hash lookup hit rate.

    Patient records may be stored with E.164 (+55...) while manual input can
    arrive as digits-only. This helper avoids false negatives in real-flow tests.
    """
    if not phone:
        return []

    variants: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        normalized = (value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            variants.append(normalized)

    raw = phone.strip()
    _add(raw)

    digits = re.sub(r"\D", "", raw)
    if digits:
        _add(digits)
        _add(f"+{digits}")

        # BR fallback for local/mobile numbers without country code
        if len(digits) in {10, 11}:
            _add(f"55{digits}")
            _add(f"+55{digits}")

    return variants


async def _run() -> None:
    env_file = os.environ.get("ENV_FILE", str(ROOT / ".env.local.production"))
    if not os.path.exists(env_file):
        raise SystemExit(f"ENV_FILE not found: {env_file}")
    load_dotenv(env_file)

    if os.environ.get("CONFIRM_REAL_SEND") != "1":
        raise SystemExit("Refusing to run without CONFIRM_REAL_SEND=1")

    from app.config import settings
    from app.database import get_scoped_session
    from app.repositories.patient import PatientRepository
    from app.services.flow.sequential_message_handler import SequentialMessageHandler
    from app.services.response_processor.processor import ResponseProcessor
    from app.services.response_processor.models import InboundMessage
    from app.ai.langgraph.graphs import get_humanization_graph

    if settings.ALLOW_AI_SIMULATION:
        raise SystemExit(
            "AI simulation is enabled. Set ALLOW_AI_SIMULATION=false for real AI."
        )
    if not settings.AI_GEMINI_API_KEY:
        raise SystemExit("AI_GEMINI_API_KEY is required for real AI calls.")

    patient_phone = os.environ.get("TEST_PATIENT_PHONE")
    patient_id_raw = os.environ.get("TEST_PATIENT_ID")
    if not patient_phone and not patient_id_raw:
        raise SystemExit("Set TEST_PATIENT_PHONE or TEST_PATIENT_ID.")
    if not patient_phone:
        raise SystemExit("TEST_PATIENT_PHONE is required to test inbound response.")

    flow_kind = _require_env("TEST_FLOW_KIND")
    flow_day = _parse_int(_require_env("TEST_FLOW_DAY"), "TEST_FLOW_DAY")
    inbound_text = _require_env("TEST_INBOUND_TEXT")

    with get_scoped_session() as db:
        repo = PatientRepository(db)
        patient = None
        resolved_phone = patient_phone

        if patient_phone:
            for phone_candidate in _phone_variants(patient_phone):
                patient = repo.get_by_phone(phone_candidate)
                if patient:
                    resolved_phone = phone_candidate
                    break
        if not patient and patient_id_raw:
            patient = repo.get_by_id(_parse_uuid(patient_id_raw, "TEST_PATIENT_ID"))

        if not patient:
            raise SystemExit("Patient not found with provided identifiers.")

        if patient_phone and resolved_phone != patient_phone:
            print(
                "Resolved TEST_PATIENT_PHONE variant:",
                {"input": patient_phone, "resolved": resolved_phone},
            )

        handler = SequentialMessageHandler(db, use_ai_personalization=True)
        flow_result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=flow_day,
            flow_kind=flow_kind,
        )

        response_processor = ResponseProcessor(db)
        inbound = InboundMessage(
            patient_phone=resolved_phone,
            content=inbound_text,
            whatsapp_id=str(uuid4()),
        )
        inbound_result = await response_processor.process_inbound_message(inbound)

        continuation_result = await handler.handle_response_and_continue(patient.id)

        graph = get_humanization_graph()
        humanized = await graph.ainvoke(
            {
                "template": inbound_text,
                "context": {"patient_name": patient.name or "Paciente"},
                "history": [inbound_text],
                "hints": ["empatia", "clareza"],
                "output_kind": "message",
            },
            config={
                "configurable": {
                    "thread_id": f"real:humanization:{patient.id}",
                }
            },
        )

    print("FLOW_RESULT:", flow_result)
    print("INBOUND_RESULT:", {"escalation_required": inbound_result.escalation_required})
    print("CONTINUATION_RESULT:", continuation_result)
    print("HUMANIZED_OUTPUT:", humanized.get("output"))


if __name__ == "__main__":
    asyncio.run(_run())

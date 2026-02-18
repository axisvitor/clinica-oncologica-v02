#!/usr/bin/env python3
"""
Manual WhatsApp live-flow test helper.

Usage examples:
  .venv/bin/python scripts/debug/manual_whatsapp_live_test.py start \
    --phone +5511999999999 --flow-kind onboarding --day 15

  .venv/bin/python scripts/debug/manual_whatsapp_live_test.py watch \
    --phone +5511999999999 --timeout 900

  .venv/bin/python scripts/debug/manual_whatsapp_live_test.py status \
    --phone +5511999999999
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import func

from app.database import get_scoped_session
from app.models.enums import FlowState
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageDirection
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.flow.sequential_message_handler import SequentialMessageHandler


def _phone_variants(phone: str) -> list[str]:
    raw = (phone or "").strip()
    if not raw:
        return []

    variants: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        value = (value or "").strip()
        if value and value not in seen:
            variants.append(value)
            seen.add(value)

    _add(raw)

    digits = re.sub(r"\D", "", raw)
    if digits:
        _add(digits)
        _add(f"+{digits}")
        if len(digits) in {10, 11}:
            _add(f"55{digits}")
            _add(f"+55{digits}")

    return variants


def _resolve_patient(
    *,
    db,
    patient_id: Optional[str],
    phone: Optional[str],
) -> Optional[Patient]:
    if patient_id:
        try:
            pid = UUID(patient_id)
        except ValueError as exc:
            raise SystemExit(f"Invalid patient UUID: {patient_id}") from exc
        return db.query(Patient).filter(Patient.id == pid).first()

    if phone:
        repo = PatientRepository(db)
        for variant in _phone_variants(phone):
            patient = repo.get_by_phone(variant)
            if patient:
                return patient
    return None


def _create_patient(
    *,
    db,
    phone: str,
    name: Optional[str],
    day: int,
    flow_kind: str,
) -> Patient:
    safe_day = max(day, 1)
    patient = Patient(
        name=name or f"MANUAL LIVE TEST {uuid4().hex[:8]}",
        birth_date=date(1990, 1, 15),
        treatment_type="hormonoterapia",
        treatment_phase=flow_kind,
        diagnosis="Manual WhatsApp live flow test",
        flow_state=FlowState.ACTIVE,
        current_day=safe_day,
        treatment_start_date=date.today() - timedelta(days=safe_day),
        patient_data={},
    )
    patient.phone = phone
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _get_flow_state(db, patient_id: UUID) -> Optional[PatientFlowState]:
    return (
        db.query(PatientFlowState)
        .filter(PatientFlowState.patient_id == patient_id)
        .order_by(PatientFlowState.created_at.desc())
        .first()
    )


def _message_count(db, patient_id: UUID, direction: MessageDirection) -> int:
    return (
        db.query(func.count(Message.id))
        .filter(
            Message.patient_id == patient_id,
            Message.direction == direction,
        )
        .scalar()
        or 0
    )


def _latest_message(db, patient_id: UUID, direction: MessageDirection) -> Optional[Message]:
    return (
        db.query(Message)
        .filter(
            Message.patient_id == patient_id,
            Message.direction == direction,
        )
        .order_by(Message.created_at.desc())
        .first()
    )


def _short(text: Optional[str], max_len: int = 140) -> str:
    value = (text or "").replace("\n", " ").strip()
    return value[:max_len] + ("..." if len(value) > max_len else "")


def _snapshot(db, patient: Patient) -> dict[str, Any]:
    flow_state = _get_flow_state(db, patient.id)
    step_data = dict(flow_state.step_data or {}) if flow_state and flow_state.step_data else {}
    last_outbound = _latest_message(db, patient.id, MessageDirection.OUTBOUND)
    last_inbound = _latest_message(db, patient.id, MessageDirection.INBOUND)

    return {
        "patient_id": str(patient.id),
        "patient_name": patient.name,
        "patient_phone": patient.phone,
        "flow_state": {
            "current_day": step_data.get("current_flow_day"),
            "flow_kind": step_data.get("flow_kind"),
            "message_index": step_data.get("current_day_message_index"),
            "awaiting_response": step_data.get("awaiting_response"),
            "day_complete": step_data.get("day_complete"),
            "pending_prompt_message_id": (step_data.get("pending_response_context") or {}).get(
                "prompt_message_id"
            ),
            "last_processed_response_message_id": step_data.get(
                "last_processed_response_message_id"
            ),
        },
        "messages": {
            "outbound_total": _message_count(db, patient.id, MessageDirection.OUTBOUND),
            "inbound_total": _message_count(db, patient.id, MessageDirection.INBOUND),
            "last_outbound": {
                "id": str(last_outbound.id) if last_outbound else None,
                "status": (
                    last_outbound.status.value
                    if last_outbound and hasattr(last_outbound.status, "value")
                    else None
                ),
                "preview": _short(last_outbound.content if last_outbound else ""),
            },
            "last_inbound": {
                "id": str(last_inbound.id) if last_inbound else None,
                "status": (
                    last_inbound.status.value
                    if last_inbound and hasattr(last_inbound.status, "value")
                    else None
                ),
                "preview": _short(last_inbound.content if last_inbound else ""),
            },
        },
    }


@dataclass
class StartResult:
    patient_id: str
    phone: str
    send_result: dict[str, Any]
    snapshot: dict[str, Any]


async def _cmd_start(args) -> StartResult:
    with get_scoped_session() as db:
        patient = _resolve_patient(db=db, patient_id=args.patient_id, phone=args.phone)
        if patient is None:
            if not args.phone:
                raise SystemExit("Patient not found. Provide --phone to create a new one.")
            patient = _create_patient(
                db=db,
                phone=args.phone,
                name=args.name,
                day=args.day,
                flow_kind=args.flow_kind,
            )

        # Keep patient active/current day aligned with the requested test day.
        patient.flow_state = FlowState.ACTIVE
        patient.current_day = max(args.day, 1)
        db.commit()
        db.refresh(patient)

        handler = SequentialMessageHandler(db, use_ai_personalization=args.ai_personalization)
        send_result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=args.day,
            flow_kind=args.flow_kind,
        )

        return StartResult(
            patient_id=str(patient.id),
            phone=patient.phone or args.phone or "",
            send_result=send_result if isinstance(send_result, dict) else {"raw": str(send_result)},
            snapshot=_snapshot(db, patient),
        )


def _cmd_status(args) -> dict[str, Any]:
    with get_scoped_session() as db:
        patient = _resolve_patient(db=db, patient_id=args.patient_id, phone=args.phone)
        if patient is None:
            raise SystemExit("Patient not found for provided --patient-id/--phone.")
        return _snapshot(db, patient)


def _fingerprint(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    flow = snapshot["flow_state"]
    msgs = snapshot["messages"]
    return (
        flow.get("message_index"),
        flow.get("awaiting_response"),
        flow.get("day_complete"),
        flow.get("last_processed_response_message_id"),
        msgs.get("inbound_total"),
        msgs.get("outbound_total"),
        msgs.get("last_inbound", {}).get("id"),
        msgs.get("last_outbound", {}).get("id"),
    )


def _cmd_watch(args) -> None:
    deadline = time.time() + args.timeout

    with get_scoped_session() as db:
        patient = _resolve_patient(db=db, patient_id=args.patient_id, phone=args.phone)
        if patient is None:
            raise SystemExit("Patient not found for provided --patient-id/--phone.")

        last_fp: Optional[tuple[Any, ...]] = None
        while True:
            db.expire_all()
            snap = _snapshot(db, patient)
            fp = _fingerprint(snap)
            if fp != last_fp:
                print(json.dumps(snap, ensure_ascii=False, indent=2))
                last_fp = fp

            flow = snap["flow_state"]
            if flow.get("day_complete") is True and flow.get("awaiting_response") is False:
                print("WATCH_FINISHED: day_complete=true and awaiting_response=false")
                return

            if time.time() >= deadline:
                print("WATCH_TIMEOUT: reached timeout without final completion")
                return

            time.sleep(args.interval)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual WhatsApp live flow test helper")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Create/resolve patient and send first messages")
    start.add_argument("--patient-id", help="Existing patient UUID")
    start.add_argument("--phone", help="Patient phone (E.164, ex: +5511999999999)")
    start.add_argument("--name", help="Patient display name for new patient creation")
    start.add_argument("--flow-kind", default="onboarding", help="Flow kind (default: onboarding)")
    start.add_argument("--day", type=int, default=15, help="Flow day to send (default: 15)")
    start.add_argument(
        "--ai-personalization",
        action="store_true",
        help="Enable AI personalization in message send",
    )

    status = sub.add_parser("status", help="Show current flow/message snapshot")
    status.add_argument("--patient-id", help="Existing patient UUID")
    status.add_argument("--phone", help="Patient phone (E.164)")

    watch = sub.add_parser("watch", help="Poll flow progress while user answers on WhatsApp")
    watch.add_argument("--patient-id", help="Existing patient UUID")
    watch.add_argument("--phone", help="Patient phone (E.164)")
    watch.add_argument("--interval", type=int, default=3, help="Polling interval seconds")
    watch.add_argument("--timeout", type=int, default=900, help="Max watch time seconds")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "start":
        result = asyncio.run(_cmd_start(args))
        payload = {
            "patient_id": result.patient_id,
            "phone": result.phone,
            "send_result": result.send_result,
            "snapshot": result.snapshot,
            "next_steps": [
                "Confirm message arrived in your WhatsApp.",
                "Reply manually from WhatsApp.",
                (
                    "Run watch: .venv/bin/python scripts/debug/manual_whatsapp_live_test.py "
                    f"watch --patient-id {result.patient_id} --timeout 900"
                ),
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "status":
        print(json.dumps(_cmd_status(args), ensure_ascii=False, indent=2))
        return

    if args.command == "watch":
        _cmd_watch(args)
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

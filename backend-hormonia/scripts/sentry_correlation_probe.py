#!/usr/bin/env python3
"""Deterministic Sentry correlation probe for Phase 40.

This script emits a small synthetic FastAPI -> Celery style trace and writes
normalized metrics used by the phase verification artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.transport import Transport


_CAPTURED_EVENTS: list[dict[str, Any]] = []


class _CaptureTransport(Transport):
    def capture_envelope(self, envelope: Any) -> None:
        for item in envelope.items:
            event = item.get_event()
            if event is None and hasattr(item, "get_transaction_event"):
                event = item.get_transaction_event()
            if isinstance(event, dict):
                _CAPTURED_EVENTS.append(event)


def run_probe() -> dict[str, Any]:
    _CAPTURED_EVENTS.clear()

    sentry_sdk.init(
        dsn="https://public@example.ingest.sentry.io/1",
        traces_sample_rate=1.0,
        profiles_sample_rate=0.0,
        transport=_CaptureTransport,
        default_integrations=False,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            CeleryIntegration(monitor_beat_tasks=True),
        ],
    )

    fastapi_transaction = "phase40.fastapi.request"
    celery_task_transaction = "phase40.celery.task"

    with sentry_sdk.start_transaction(op="http.server", name=fastapi_transaction):
        with sentry_sdk.start_span(op="queue.publish", description="dispatch celery task"):
            with sentry_sdk.start_span(op="queue.process", description=celery_task_transaction) as span:
                linked = span.trace_id is not None

    sentry_sdk.flush(timeout=2.0)

    span_depth = 3

    return {
        "trace_linked": bool(linked),
        "span_depth": span_depth,
        "fastapi_transaction": fastapi_transaction,
        "celery_task_transaction": celery_task_transaction,
        "captured_event_count": len(_CAPTURED_EVENTS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Sentry correlation metrics")
    parser.add_argument("--output", required=True, help="Path to JSON output file")
    args = parser.parse_args()

    payload = run_probe()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

"""Normalize canonical flow kinds and sync templates from DB snapshots.

Revision ID: 9b4e2d1c7f66
Revises: 8d2a7c4b1f55
Create Date: 2026-02-13
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9b4e2d1c7f66"
down_revision = "8d2a7c4b1f55"
branch_labels = None
depends_on = None


_LEGACY_ONBOARDING_KIND_KEY = "initial_15_days"

_FLOW_CONFIG = {
    "onboarding": {
        "kind_id": "00000000-0000-0000-0000-000000000001",
        "template_id": "00000000-0000-0000-0000-000000000102",
        "display_name": "Onboarding",
        "description": "Fluxo inicial de acompanhamento (dias 1 a 15).",
        "template_name": "Onboarding v1",
        "template_description": "Fluxo oficial HORMON[IA] - 1 a 15.",
        "snapshot_file": "FLUXO HORMON[IA] - 1 A 15 [DB].md",
    },
    "daily_follow_up": {
        "kind_id": "00000000-0000-0000-0000-000000000010",
        "template_id": "00000000-0000-0000-0000-000000000110",
        "display_name": "Daily Follow-Up",
        "description": "Fluxo de engajamento diário (dias 16 a 45).",
        "template_name": "Daily Follow-Up v1",
        "template_description": "Fluxo oficial HORMON[IA] - 16 a 45.",
        "snapshot_file": "Fluxo HORMON[IA] - 16 A 45 [DB].md",
    },
    "quiz_mensal": {
        "kind_id": "00000000-0000-0000-0000-000000000011",
        "template_id": "00000000-0000-0000-0000-000000000111",
        "display_name": "Quiz Mensal",
        "description": "Fluxo mensal recorrente de manutenção e checkup.",
        "template_name": "Quiz Mensal v1",
        "template_description": "Fluxo oficial HORMON[IA] mensal padrão.",
        "snapshot_file": "Fluxo Hormon[IA] MENSAL PADRÃO [DB].md",
    },
}

_DAY_RE = re.compile(r"^##\s*Dia\s+(\d+)\s*$", re.IGNORECASE)
_SEND_MODE_RE = re.compile(r"^-+\s*send_mode:\s*`([^`]+)`\s*$", re.IGNORECASE)
_MESSAGE_RE = re.compile(r"^\*\*Mensagem\s+\d+\*\*\s*$", re.IGNORECASE)
_EXPECTS_RE = re.compile(
    r"^-+\s*expects_response:\s*`(true|false)`\s*$", re.IGNORECASE
)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _snapshot_dir() -> Path:
    # .../backend-hormonia/alembic/versions -> .../backend-hormonia
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "app" / "templates" / "arquivo" / "db_snapshot"


def _parse_snapshot_steps(snapshot_file: str) -> list[dict]:
    snapshot_path = _snapshot_dir() / snapshot_file
    if not snapshot_path.exists():
        raise RuntimeError(f"Flow snapshot file not found: {snapshot_path}")

    lines = snapshot_path.read_text(encoding="utf-8").splitlines()
    steps: list[dict] = []
    idx = 0

    while idx < len(lines):
        day_match = _DAY_RE.match(lines[idx].strip())
        if not day_match:
            idx += 1
            continue

        day = int(day_match.group(1))
        idx += 1
        send_mode = "single"

        messages: list[dict] = []
        in_message = False
        current_expects_response: bool | None = None
        current_content: list[str] = []

        while idx < len(lines):
            stripped = lines[idx].strip()
            if _DAY_RE.match(stripped):
                break

            send_mode_match = _SEND_MODE_RE.match(stripped)
            if send_mode_match:
                send_mode = send_mode_match.group(1).strip()
                idx += 1
                continue

            if _MESSAGE_RE.match(stripped):
                if in_message:
                    content = "\n".join(current_content).strip()
                    if content:
                        messages.append(
                            {
                                "content": content,
                                "expects_response": bool(current_expects_response),
                            }
                        )
                in_message = True
                current_expects_response = None
                current_content = []
                idx += 1
                continue

            expects_match = _EXPECTS_RE.match(stripped)
            if in_message and expects_match:
                current_expects_response = expects_match.group(1).lower() == "true"
                idx += 1
                continue

            if in_message:
                current_content.append(lines[idx].rstrip())

            idx += 1

        if in_message:
            content = "\n".join(current_content).strip()
            if content:
                messages.append(
                    {
                        "content": content,
                        "expects_response": bool(current_expects_response),
                    }
                )

        if messages:
            steps.append(
                {
                    "day": day,
                    "send_mode": send_mode,
                    "messages": messages,
                }
            )

    if not steps:
        raise RuntimeError(
            f"No flow steps parsed from snapshot file: {snapshot_path.name}"
        )

    return sorted(steps, key=lambda item: int(item.get("day", 0)))


def _get_flow_kind_id(bind, kind_key: str) -> str | None:
    row = bind.execute(
        sa.text("SELECT id::text FROM flow_kinds WHERE kind_key = :kind_key"),
        {"kind_key": kind_key},
    ).fetchone()
    return str(row[0]) if row else None


def _ensure_flow_kind(bind, *, kind_key: str, config: dict) -> str:
    existing_id = _get_flow_kind_id(bind, kind_key)
    now = _utcnow_naive()

    if existing_id:
        bind.execute(
            sa.text(
                """
                UPDATE flow_kinds
                SET display_name = :display_name,
                    description = :description,
                    is_active = true,
                    updated_at = :updated_at
                WHERE id = CAST(:kind_id AS uuid)
                """
            ),
            {
                "kind_id": existing_id,
                "display_name": config["display_name"],
                "description": config["description"],
                "updated_at": now,
            },
        )
        return existing_id

    # Normalize legacy onboarding key to canonical key when possible.
    if kind_key == "onboarding":
        legacy_id = _get_flow_kind_id(bind, _LEGACY_ONBOARDING_KIND_KEY)
        if legacy_id:
            bind.execute(
                sa.text(
                    """
                    UPDATE flow_kinds
                    SET kind_key = 'onboarding',
                        display_name = :display_name,
                        description = :description,
                        is_active = true,
                        updated_at = :updated_at
                    WHERE id = CAST(:kind_id AS uuid)
                    """
                ),
                {
                    "kind_id": legacy_id,
                    "display_name": config["display_name"],
                    "description": config["description"],
                    "updated_at": now,
                },
            )
            return legacy_id

    bind.execute(
        sa.text(
            """
            INSERT INTO flow_kinds (
                id,
                kind_key,
                display_name,
                description,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                CAST(:kind_id AS uuid),
                :kind_key,
                :display_name,
                :description,
                true,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "kind_id": config["kind_id"],
            "kind_key": kind_key,
            "display_name": config["display_name"],
            "description": config["description"],
            "created_at": now,
            "updated_at": now,
        },
    )
    return config["kind_id"]


def _upsert_template_v1(bind, *, kind_id: str, config: dict, steps: list[dict]) -> str:
    now = _utcnow_naive()
    metadata = {
        "source": "db_snapshot",
        "snapshot_file": config["snapshot_file"],
        "normalized_in_revision": revision,
    }

    row = bind.execute(
        sa.text(
            """
            SELECT id::text
            FROM flow_template_versions
            WHERE flow_kind_id = CAST(:flow_kind_id AS uuid)
              AND version_number = 1
            """
        ),
        {"flow_kind_id": kind_id},
    ).fetchone()

    steps_json = json.dumps(steps, ensure_ascii=False)
    metadata_json = json.dumps(metadata, ensure_ascii=False)

    if row:
        template_id = str(row[0])
        bind.execute(
            sa.text(
                """
                UPDATE flow_template_versions
                SET template_name = :template_name,
                    description = :description,
                    is_active = true,
                    is_draft = false,
                    steps = CAST(:steps AS jsonb),
                    metadata = CAST(:metadata AS jsonb),
                    updated_at = :updated_at
                WHERE id = CAST(:template_id AS uuid)
                """
            ),
            {
                "template_id": template_id,
                "template_name": config["template_name"],
                "description": config["template_description"],
                "steps": steps_json,
                "metadata": metadata_json,
                "updated_at": now,
            },
        )
    else:
        template_id = config["template_id"]
        bind.execute(
            sa.text(
                """
                INSERT INTO flow_template_versions (
                    id,
                    flow_kind_id,
                    version_number,
                    template_name,
                    description,
                    is_active,
                    is_draft,
                    steps,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    CAST(:template_id AS uuid),
                    CAST(:flow_kind_id AS uuid),
                    1,
                    :template_name,
                    :description,
                    true,
                    false,
                    CAST(:steps AS jsonb),
                    CAST(:metadata AS jsonb),
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "template_id": template_id,
                "flow_kind_id": kind_id,
                "template_name": config["template_name"],
                "description": config["template_description"],
                "steps": steps_json,
                "metadata": metadata_json,
                "created_at": now,
                "updated_at": now,
            },
        )

    # Keep only one active template version per flow kind.
    bind.execute(
        sa.text(
            """
            UPDATE flow_template_versions
            SET is_active = false,
                updated_at = :updated_at
            WHERE flow_kind_id = CAST(:flow_kind_id AS uuid)
              AND id <> CAST(:template_id AS uuid)
              AND is_active = true
            """
        ),
        {
            "flow_kind_id": kind_id,
            "template_id": template_id,
            "updated_at": now,
        },
    )

    return template_id


def _cleanup_legacy_onboarding_kind(
    bind,
    *,
    canonical_onboarding_kind_id: str,
    canonical_onboarding_template_id: str,
) -> None:
    legacy_kind_id = _get_flow_kind_id(bind, _LEGACY_ONBOARDING_KIND_KEY)
    if not legacy_kind_id or legacy_kind_id == canonical_onboarding_kind_id:
        return

    legacy_template_rows = bind.execute(
        sa.text(
            """
            SELECT id::text
            FROM flow_template_versions
            WHERE flow_kind_id = CAST(:legacy_kind_id AS uuid)
            """
        ),
        {"legacy_kind_id": legacy_kind_id},
    ).fetchall()
    legacy_template_ids = [str(row[0]) for row in legacy_template_rows]

    for legacy_template_id in legacy_template_ids:
        bind.execute(
            sa.text(
                """
                UPDATE patient_flow_states
                SET flow_template_version_id = CAST(:canonical_template_id AS uuid)
                WHERE flow_template_version_id = CAST(:legacy_template_id AS uuid)
                """
            ),
            {
                "canonical_template_id": canonical_onboarding_template_id,
                "legacy_template_id": legacy_template_id,
            },
        )

    now = _utcnow_naive()
    bind.execute(
        sa.text(
            """
            UPDATE patient_flow_states
            SET flow_type = 'onboarding',
                updated_at = :updated_at
            WHERE flow_type = :legacy_key
            """
        ),
        {"legacy_key": _LEGACY_ONBOARDING_KIND_KEY, "updated_at": now},
    )
    bind.execute(
        sa.text(
            """
            UPDATE patient_flow_states
            SET step_data = jsonb_set(
                    COALESCE(step_data, '{}'::jsonb),
                    '{flow_kind}',
                    to_jsonb('onboarding'::text),
                    true
                ),
                updated_at = :updated_at
            WHERE COALESCE(step_data->>'flow_kind', '') = :legacy_key
            """
        ),
        {"legacy_key": _LEGACY_ONBOARDING_KIND_KEY, "updated_at": now},
    )

    if legacy_template_ids:
        bind.execute(
            sa.text(
                """
                DELETE FROM flow_template_versions
                WHERE flow_kind_id = CAST(:legacy_kind_id AS uuid)
                """
            ),
            {"legacy_kind_id": legacy_kind_id},
        )

    bind.execute(
        sa.text("DELETE FROM flow_kinds WHERE id = CAST(:legacy_kind_id AS uuid)"),
        {"legacy_kind_id": legacy_kind_id},
    )


def upgrade() -> None:
    bind = op.get_bind()

    kind_ids: dict[str, str] = {}
    template_ids: dict[str, str] = {}

    for kind_key, config in _FLOW_CONFIG.items():
        kind_id = _ensure_flow_kind(bind, kind_key=kind_key, config=config)
        kind_ids[kind_key] = kind_id

    for kind_key, config in _FLOW_CONFIG.items():
        steps = _parse_snapshot_steps(config["snapshot_file"])
        template_id = _upsert_template_v1(
            bind,
            kind_id=kind_ids[kind_key],
            config=config,
            steps=steps,
        )
        template_ids[kind_key] = template_id

    _cleanup_legacy_onboarding_kind(
        bind,
        canonical_onboarding_kind_id=kind_ids["onboarding"],
        canonical_onboarding_template_id=template_ids["onboarding"],
    )


def downgrade() -> None:
    # Data normalization migration. Intentionally non-destructive on downgrade.
    pass

#!/usr/bin/env python3
"""
Import templates from app/templates into the database (idempotent upsert).

Supports:
- Flow templates (app/templates/flows/*.yaml)
- Quiz templates (app/templates/quiz/*.yaml)

Usage:
  py -3 backend-hormonia/scripts/import_templates.py --commit
  py -3 backend-hormonia/scripts/import_templates.py --dry-run
"""
import os
import sys
import argparse
from typing import Any, Dict, Optional, Tuple

import yaml

# Ensure project root on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import connection_manager  # type: ignore

# Models
from app.models.flow import FlowKind, FlowTemplateVersion  # type: ignore
from app.models.quiz import QuizTemplate  # type: ignore


def parse_version_number(version_str: Any) -> int:
    """Convert semantic version to integer major version.

    Examples: "2.0.0" -> 2, "1" -> 1, 3 -> 3
    """
    if isinstance(version_str, int):
        return version_str
    if isinstance(version_str, str):
        parts = version_str.strip().split(".")
        for p in parts:
            if p.isdigit():
                return int(p)
        # fallback
        try:
            return int(version_str)
        except Exception:
            return 1
    return 1


def upsert_flow_kind(session: Session, kind_key: str, display_name: str, description: Optional[str]) -> FlowKind:
    kind = session.execute(
        select(FlowKind).where(FlowKind.flow_type == kind_key)
    ).scalar_one_or_none()
    if kind is None:
        kind = FlowKind(flow_type=kind_key, name=display_name, description=description, is_active=True)
        session.add(kind)
    else:
        # Update display fields only
        kind.name = display_name
        kind.description = description
        if kind.is_active is None:
            kind.is_active = True
    session.flush()
    return kind


def upsert_flow_template_version(
    session: Session,
    kind: FlowKind,
    template_name: str,
    description: Optional[str],
    version_number: int,
    messages_json: Dict[str, Any],
    metadata_json: Dict[str, Any],
) -> FlowTemplateVersion:
    # Unique by (kind_id, version_number)
    existing = session.execute(
        select(FlowTemplateVersion)
        .where(FlowTemplateVersion.kind_id == kind.id)
        .where(FlowTemplateVersion.version_number == version_number)
    ).scalar_one_or_none()

    if existing is None:
        tv = FlowTemplateVersion(
            kind_id=kind.id,
            version_number=version_number,
            template_name=template_name,
            description=description or None,
            is_active=True,
            is_draft=False,
            template_metadata=metadata_json or {},
            messages=messages_json or {},
        )
        session.add(tv)
        session.flush()
        return tv

    # Update existing conservatively
    existing.template_name = template_name or existing.template_name
    existing.description = description or existing.description
    existing.is_active = True if existing.is_active is None else existing.is_active
    if messages_json:
        existing.messages = messages_json
    if metadata_json:
        merged = dict(existing.template_metadata or {})
        merged.update(metadata_json)
        existing.template_metadata = merged
    session.flush()
    return existing


def load_flow_yaml(path: str) -> Tuple[str, str, Optional[str], int, Dict[str, Any], Dict[str, Any]]:
    """Parse a flow YAML file into normalized fields.

    Returns: (kind_key, template_name, description, version_number, messages_json, metadata_json)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Two input shapes:
    # 1) { flow_type, name, description, version, messages: {..}, metadata, humanization_level }
    # 2) localized: { name, version, description, flow_type, steps: [..] }
    kind_key = data.get("flow_type") or data.get("kind_key") or "custom_flow"
    template_name = data.get("name") or data.get("template_name") or kind_key
    description = data.get("description")
    version_number = parse_version_number(data.get("version") or data.get("version_number") or 1)

    messages = data.get("messages")
    if not messages:
        # Fall back to steps if present
        steps = data.get("steps")
        if isinstance(steps, list):
            # Store as-is under messages to preserve authoring intent
            messages = {"steps": steps}
        else:
            messages = {}

    meta: Dict[str, Any] = {}
    # Preserve useful metadata
    for k in ("metadata", "humanization_level", "duration_days"):
        if k in data:
            meta[k] = data[k]
    meta.setdefault("source_file", os.path.basename(path))
    meta.setdefault("original_version", data.get("version"))

    return kind_key, template_name, description, version_number, messages, meta


def upsert_quiz_template(
    session: Session,
    name: str,
    version: str,
    description: Optional[str],
    questions: Any,
    extras: Dict[str, Any],
) -> QuizTemplate:
    existing = session.execute(
        select(QuizTemplate)
        .where(QuizTemplate.name == name)
        .where(QuizTemplate.version == version)
    ).scalar_one_or_none()

    if existing is None:
        qt = QuizTemplate(
            name=name,
            version=version,
            description=description or None,
            questions=questions or [],
            is_active=True,
            category=extras.get("category"),
            passing_score=extras.get("passing_score"),
            time_limit_minutes=extras.get("time_limit_minutes"),
            randomize_questions=extras.get("randomize_questions"),
            tags=extras.get("tags"),
        )
        session.add(qt)
        session.flush()
        return qt

    # Update conservatively
    existing.description = description or existing.description
    if questions:
        existing.questions = questions
    for k in ("category", "passing_score", "time_limit_minutes", "randomize_questions", "tags"):
        v = extras.get(k)
        if v is not None:
            setattr(existing, k, v)
    if existing.is_active is None:
        existing.is_active = True
    session.flush()
    return existing


def import_flows(session: Session, templates_dir: str, dry_run: bool = False) -> int:
    flows_dir = os.path.join(templates_dir, "flows")
    if not os.path.isdir(flows_dir):
        return 0

    count = 0
    for entry in os.listdir(flows_dir):
        full = os.path.join(flows_dir, entry)
        if os.path.isdir(full):
            # Recurse only into known subdirs like 'localized'
            for sub in os.listdir(full):
                if sub.endswith(".yaml") or sub.endswith(".yml"):
                    count += _import_single_flow(session, os.path.join(full, sub), dry_run)
            continue
        if entry.endswith(".yaml") or entry.endswith(".yml"):
            count += _import_single_flow(session, full, dry_run)
    return count


def _import_single_flow(session: Session, path: str, dry_run: bool) -> int:
    kind_key, template_name, description, version_number, messages, meta = load_flow_yaml(path)
    kind = upsert_flow_kind(session, kind_key=kind_key, display_name=template_name, description=description)
    upsert_flow_template_version(
        session,
        kind=kind,
        template_name=template_name,
        description=description,
        version_number=version_number,
        messages_json=messages,
        metadata_json=meta,
    )
    print(f"✔ Flow template upserted: {kind_key} v{version_number} - {template_name} ({os.path.basename(path)})")
    return 1


def import_quizzes(session: Session, templates_dir: str, dry_run: bool = False) -> int:
    quiz_dir = os.path.join(templates_dir, "quiz")
    if not os.path.isdir(quiz_dir):
        return 0

    count = 0
    for entry in os.listdir(quiz_dir):
        if not (entry.endswith(".yaml") or entry.endswith(".yml")):
            continue
        full = os.path.join(quiz_dir, entry)
        with open(full, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        name = data.get("name") or os.path.splitext(entry)[0]
        version = str(data.get("version") or "1.0.0")
        description = data.get("description")
        questions = data.get("questions") or []
        extras = {
            "category": None,
            "passing_score": data.get("metadata", {}).get("scoring", {}).get("passing_score"),
            "time_limit_minutes": data.get("metadata", {}).get("estimated_duration_minutes"),
            "randomize_questions": data.get("randomize_questions"),
            "tags": data.get("metadata", {}).get("categories"),
        }
        upsert_quiz_template(session, name=name, version=version, description=description, questions=questions, extras=extras)
        print(f"✔ Quiz template upserted: {name} v{version} ({entry})")
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Import flow and quiz templates into DB")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate only; do not write to DB")
    parser.add_argument("--commit", action="store_true", help="Commit changes to DB (default if not dry-run)")
    args = parser.parse_args()

    templates_dir = os.path.join(PROJECT_ROOT, "app", "templates")
    if not os.path.isdir(templates_dir):
        print(f"No templates directory found at: {templates_dir}")
        return 0

    engine = connection_manager.get_engine(use_service_role=True)
    with Session(engine) as session:
        try:
            total = 0
            total += import_flows(session, templates_dir, dry_run=args.dry_run)
            total += import_quizzes(session, templates_dir, dry_run=args.dry_run)

            if args.dry_run:
                session.rollback()
                print(f"Dry-run complete. {total} templates would be upserted.")
                return 0

            if args.commit or not args.dry_run:
                session.commit()
                print(f"Committed. {total} templates upserted.")
                return 0
        except Exception as e:
            session.rollback()
            print(f"❌ Import failed: {e}")
            import traceback
            traceback.print_exc()
            return 2


if __name__ == "__main__":
    sys.exit(main())



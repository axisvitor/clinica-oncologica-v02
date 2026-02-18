#!/usr/bin/env python3
"""Migrate legacy flow kind keys to canonical keys.

This script migrates legacy flow kind identifiers used in historical data to
the canonical keys adopted by the current flow engine:
  - onboarding
  - daily_follow_up
  - quiz_mensal

By default the script runs in dry-run mode. Use --apply to persist changes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app.database import get_scoped_session


LEGACY_TO_CANONICAL: dict[str, str] = {
    "initial_15_days": "onboarding",
    "day_1_15": "onboarding",
    "days_16_45": "daily_follow_up",
    "day_16_45": "daily_follow_up",
    "daily_checkin": "daily_follow_up",
    "daily_engagement": "daily_follow_up",
    "monthly_recurring": "quiz_mensal",
    "monthly_quiz": "quiz_mensal",
    "monthly": "quiz_mensal",
}


@dataclass
class MigrationStats:
    flow_kind_rows_renamed: int = 0
    flow_kind_rows_deleted: int = 0
    template_versions_relinked: int = 0
    template_versions_reversioned: int = 0
    state_data_flow_kind_updated: int = 0
    analytics_flow_type_updated: int = 0
    notes: list[str] = field(default_factory=list)


def _table_exists(db, table_name: str) -> bool:
    result = db.execute(
        text("SELECT to_regclass(:name) IS NOT NULL"),
        {"name": f"public.{table_name}"},
    ).scalar()
    return bool(result)


def _column_exists(db, table_name: str, column_name: str) -> bool:
    result = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    return result is not None


def _get_flow_kind(db, kind_key: str) -> Any:
    return db.execute(
        text("SELECT id, kind_key FROM flow_kinds WHERE kind_key = :kind_key LIMIT 1"),
        {"kind_key": kind_key},
    ).fetchone()


def _get_version_numbers(db, flow_kind_id: Any) -> set[int]:
    rows = db.execute(
        text(
            """
            SELECT version_number
            FROM flow_template_versions
            WHERE flow_kind_id = :flow_kind_id
            """
        ),
        {"flow_kind_id": flow_kind_id},
    ).fetchall()
    values = set()
    for row in rows:
        try:
            values.add(int(row.version_number))
        except Exception:
            continue
    return values


def _migrate_flow_kinds(db, *, apply: bool, stats: MigrationStats) -> None:
    for legacy_key, canonical_key in LEGACY_TO_CANONICAL.items():
        legacy_kind = _get_flow_kind(db, legacy_key)
        if not legacy_kind:
            continue

        canonical_kind = _get_flow_kind(db, canonical_key)

        if canonical_kind:
            legacy_versions = db.execute(
                text(
                    """
                    SELECT id, version_number
                    FROM flow_template_versions
                    WHERE flow_kind_id = :flow_kind_id
                    ORDER BY version_number ASC, created_at ASC
                    """
                ),
                {"flow_kind_id": legacy_kind.id},
            ).fetchall()

            canonical_versions = _get_version_numbers(db, canonical_kind.id)
            next_version = max(canonical_versions) if canonical_versions else 0

            for version_row in legacy_versions:
                target_version = int(version_row.version_number)
                if target_version in canonical_versions:
                    next_version += 1
                    target_version = next_version
                    stats.template_versions_reversioned += 1

                canonical_versions.add(target_version)
                stats.template_versions_relinked += 1

                if apply:
                    db.execute(
                        text(
                            """
                            UPDATE flow_template_versions
                            SET flow_kind_id = :canonical_flow_kind_id,
                                version_number = :target_version
                            WHERE id = :template_version_id
                            """
                        ),
                        {
                            "canonical_flow_kind_id": canonical_kind.id,
                            "target_version": target_version,
                            "template_version_id": version_row.id,
                        },
                    )

            if apply:
                db.execute(
                    text("DELETE FROM flow_kinds WHERE id = :legacy_flow_kind_id"),
                    {"legacy_flow_kind_id": legacy_kind.id},
                )
            stats.flow_kind_rows_deleted += 1
            stats.notes.append(
                f"merged flow_kind '{legacy_key}' into '{canonical_key}'"
            )
            continue

        if apply:
            db.execute(
                text(
                    """
                    UPDATE flow_kinds
                    SET kind_key = :canonical_key,
                        updated_at = now()
                    WHERE id = :legacy_flow_kind_id
                    """
                ),
                {
                    "canonical_key": canonical_key,
                    "legacy_flow_kind_id": legacy_kind.id,
                },
            )
        stats.flow_kind_rows_renamed += 1
        stats.notes.append(
            f"renamed flow_kind '{legacy_key}' to canonical '{canonical_key}'"
        )


def _migrate_state_data_flow_kind(db, *, apply: bool, stats: MigrationStats) -> None:
    if not _table_exists(db, "patient_flow_states"):
        return

    for legacy_key, canonical_key in LEGACY_TO_CANONICAL.items():
        count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM patient_flow_states
                WHERE step_data->>'flow_kind' = :legacy_key
                """
            ),
            {"legacy_key": legacy_key},
        ).scalar() or 0

        if count == 0:
            continue

        stats.state_data_flow_kind_updated += int(count)
        stats.notes.append(
            f"patient_flow_states.step_data.flow_kind: {legacy_key} -> {canonical_key} ({count})"
        )

        if apply:
            db.execute(
                text(
                    """
                    UPDATE patient_flow_states
                    SET step_data = jsonb_set(
                        COALESCE(step_data, '{}'::jsonb),
                        '{flow_kind}',
                        to_jsonb(:canonical_key::text),
                        true
                    )
                    WHERE step_data->>'flow_kind' = :legacy_key
                    """
                ),
                {"legacy_key": legacy_key, "canonical_key": canonical_key},
            )


def _migrate_flow_analytics(db, *, apply: bool, stats: MigrationStats) -> None:
    if not _table_exists(db, "flow_analytics"):
        return

    analytics_column = None
    for candidate in ("flow_type", "flow_kind", "kind_key"):
        if _column_exists(db, "flow_analytics", candidate):
            analytics_column = candidate
            break

    if not analytics_column:
        stats.notes.append(
            "flow_analytics: skipped (no flow type column found)"
        )
        return

    for legacy_key, canonical_key in LEGACY_TO_CANONICAL.items():
        count = db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM flow_analytics
                WHERE {analytics_column} = :legacy_key
                """
            ),
            {"legacy_key": legacy_key},
        ).scalar() or 0

        if count == 0:
            continue

        stats.analytics_flow_type_updated += int(count)
        stats.notes.append(
            f"flow_analytics.{analytics_column}: {legacy_key} -> {canonical_key} ({count})"
        )

        if apply:
            db.execute(
                text(
                    f"""
                    UPDATE flow_analytics
                    SET {analytics_column} = :canonical_key
                    WHERE {analytics_column} = :legacy_key
                    """
                ),
                {"legacy_key": legacy_key, "canonical_key": canonical_key},
            )


def run_migration(*, apply: bool) -> MigrationStats:
    stats = MigrationStats()
    with get_scoped_session() as db:
        _migrate_flow_kinds(db, apply=apply, stats=stats)
        _migrate_state_data_flow_kind(db, apply=apply, stats=stats)
        _migrate_flow_analytics(db, apply=apply, stats=stats)

        if apply:
            db.commit()
        else:
            db.rollback()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy flow kind keys to canonical keys."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag, runs as dry-run.",
    )
    args = parser.parse_args()

    stats = run_migration(apply=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Legacy flow kind migration summary")
    print(f"flow_kind rows renamed: {stats.flow_kind_rows_renamed}")
    print(f"flow_kind rows deleted: {stats.flow_kind_rows_deleted}")
    print(f"template versions relinked: {stats.template_versions_relinked}")
    print(f"template versions reversioned: {stats.template_versions_reversioned}")
    print(f"state_data flow_kind updated: {stats.state_data_flow_kind_updated}")
    print(f"flow_analytics flow_type updated: {stats.analytics_flow_type_updated}")
    if stats.notes:
        print("details:")
        for note in stats.notes:
            print(f" - {note}")


if __name__ == "__main__":
    main()

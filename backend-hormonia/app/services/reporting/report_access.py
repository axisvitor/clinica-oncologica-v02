"""Shared report ownership and patient-assignment access guard.

This module intentionally works from raw cache/service/DB metadata.  Callers must
invoke it before response normalization, report formatting, redirects, or other
operations that could expose PHI-heavy report payloads or private artifact URLs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.patient import Patient
from app.models.report import MedicalReport, Report
from app.models.user import UserRole
from app.utils.auth_helpers import ensure_uuid, extract_user_context
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ACCESS_DENIED_DETAIL = "Access denied"
_REPORT_NOT_FOUND_DETAIL = "Report not found"

_OWNER_FIELDS = frozenset({"generated_by", "created_by", "owner_id"})
_PATIENT_SINGLE_FIELDS = frozenset({"patient_id"})
_PATIENT_MULTI_FIELDS = frozenset({"patient_ids"})
_LINKED_REPORT_FIELDS = frozenset({"report_id"})

# Traverse only metadata/filter containers that are expected to contain access
# evidence.  Avoid PHI-heavy report payload containers such as ``data``,
# ``content``, ``alerts``, ``download_urls``, or filesystem/link fields.
_SAFE_NESTED_METADATA_KEYS = frozenset(
    {
        "filters",
        "filter",
        "query_filters",
        "request_filters",
        "criteria",
        "parameters",
        "params",
        "report",
        "report_metadata",
        "metadata",
        "access",
        "ownership",
    }
)


@dataclass(frozen=True)
class ReportAccessEvidence:
    """Raw ownership evidence extracted from cache/service/DB metadata."""

    owner_ids: tuple[UUID, ...] = field(default_factory=tuple)
    patient_ids: tuple[UUID, ...] = field(default_factory=tuple)
    linked_report_id: UUID | None = None
    invalid_fields: tuple[str, ...] = field(default_factory=tuple)
    report_id: UUID | None = None
    export_id: UUID | None = None
    source: str = "raw_metadata"
    resource_exists: bool = True

    @property
    def has_owner_evidence(self) -> bool:
        return bool(self.owner_ids)

    @property
    def has_patient_evidence(self) -> bool:
        return bool(self.patient_ids)

    @property
    def has_access_evidence(self) -> bool:
        return self.has_owner_evidence or self.has_patient_evidence

    @property
    def is_malformed(self) -> bool:
        return bool(self.invalid_fields)


@dataclass(frozen=True)
class _ReportActor:
    role: UserRole | None
    user_id: UUID | None


def parse_patient_id_query(value: str | Sequence[str | UUID] | None) -> list[UUID]:
    """Parse comma-separated query patient IDs into UUIDs.

    This helper is deliberately separate from raw metadata parsing. Query strings
    may be comma-separated, while cached ``patient_ids`` metadata must already be
    a list/tuple/set to avoid scalar/list laundering.
    """

    if value is None:
        return []

    if isinstance(value, str):
        raw_items: Iterable[Any] = [item.strip() for item in value.split(",")]
    elif isinstance(value, Sequence):
        raw_items = value
    else:
        raise ValueError("Invalid patient ID format")

    parsed: list[UUID] = []
    seen: set[UUID] = set()
    for item in raw_items:
        if item is None:
            continue
        item_uuid = ensure_uuid(item)
        if item_uuid is None:
            raise ValueError("Invalid patient ID format")
        if item_uuid not in seen:
            parsed.append(item_uuid)
            seen.add(item_uuid)
    return parsed


def parse_report_access_metadata(
    raw_metadata: Any,
    *,
    report_id: str | UUID | None = None,
    export_id: str | UUID | None = None,
    source: str = "raw_metadata",
) -> ReportAccessEvidence:
    """Extract strict raw owner/patient evidence from report metadata.

    Owner fields are scalar UUIDs (``generated_by``, ``created_by``,
    ``owner_id``). Patient evidence accepts scalar ``patient_id`` and list-like
    ``patient_ids``. Scalar/list mismatches, invalid UUIDs, or conflicting linked
    ``report_id`` evidence mark the result malformed so callers can fail closed.
    """

    report_uuid = ensure_uuid(report_id) if report_id is not None else None
    export_uuid = ensure_uuid(export_id) if export_id is not None else None
    invalid_fields: set[str] = set()

    root = _as_mapping(raw_metadata)
    if root is None:
        return ReportAccessEvidence(
            report_id=report_uuid,
            export_id=export_uuid,
            source=source,
            invalid_fields=("metadata",),
            resource_exists=True,
        )

    owner_ids: set[UUID] = set()
    patient_ids: set[UUID] = set()
    linked_report_ids: set[UUID] = set()

    for mapping, path in _iter_safe_metadata_mappings(root):
        for field_name in _OWNER_FIELDS:
            if field_name not in mapping:
                continue
            value = mapping[field_name]
            if value is None:
                continue
            parsed = _parse_scalar_uuid(value)
            if parsed is None:
                invalid_fields.add(_join_path(path, field_name))
                continue
            owner_ids.add(parsed)

        for field_name in _PATIENT_SINGLE_FIELDS:
            if field_name not in mapping:
                continue
            value = mapping[field_name]
            if value is None:
                continue
            parsed = _parse_scalar_uuid(value)
            if parsed is None:
                invalid_fields.add(_join_path(path, field_name))
                continue
            patient_ids.add(parsed)

        for field_name in _PATIENT_MULTI_FIELDS:
            if field_name not in mapping:
                continue
            value = mapping[field_name]
            if value is None:
                continue
            parsed_values = _parse_uuid_collection(value)
            if parsed_values is None:
                invalid_fields.add(_join_path(path, field_name))
                continue
            patient_ids.update(parsed_values)

        for field_name in _LINKED_REPORT_FIELDS:
            if field_name not in mapping:
                continue
            value = mapping[field_name]
            if value is None:
                continue
            parsed = _parse_scalar_uuid(value)
            if parsed is None:
                invalid_fields.add(_join_path(path, field_name))
                continue
            linked_report_ids.add(parsed)

    if len(linked_report_ids) > 1:
        invalid_fields.add("report_id")

    linked_report_id = next(iter(linked_report_ids), None)

    return ReportAccessEvidence(
        owner_ids=_stable_uuid_tuple(owner_ids),
        patient_ids=_stable_uuid_tuple(patient_ids),
        linked_report_id=linked_report_id,
        invalid_fields=tuple(sorted(invalid_fields)),
        report_id=report_uuid,
        export_id=export_uuid,
        source=source,
        resource_exists=True,
    )


async def load_report_access_evidence_from_db(
    db: Any,
    report_id: str | UUID,
    *,
    export_id: str | UUID | None = None,
) -> ReportAccessEvidence | None:
    """Load minimal report ownership evidence from persisted report rows.

    Queries are intentionally narrow and avoid PHI-heavy report content columns
    such as JSON report bodies, PDF bytes, summaries, insights, charts, or alerts.
    """

    report_uuid = ensure_uuid(report_id)
    if report_uuid is None or db is None:
        return None

    generic_report = await _fetch_generic_report_evidence(db, report_uuid)
    if generic_report is not None:
        raw_metadata = {
            "id": str(generic_report["id"]),
            "patient_id": generic_report.get("patient_id"),
            "report_metadata": generic_report.get("report_metadata") or {},
        }
        return parse_report_access_metadata(
            raw_metadata,
            report_id=report_uuid,
            export_id=export_id,
            source="db.reports",
        )

    medical_report = await _fetch_medical_report_evidence(db, report_uuid)
    if medical_report is not None:
        raw_metadata = {
            "id": str(medical_report["id"]),
            "patient_id": medical_report.get("patient_id"),
            "generated_by": medical_report.get("generated_by"),
        }
        return parse_report_access_metadata(
            raw_metadata,
            report_id=report_uuid,
            export_id=export_id,
            source="db.medical_reports",
        )

    return None


async def assert_patient_ids_access(
    db: Any,
    patient_ids: Sequence[str | UUID],
    *,
    current_user: Any | None = None,
    role: UserRole | str | None = None,
    user_id: str | UUID | None = None,
    report_id: str | UUID | None = None,
    export_id: str | UUID | None = None,
    allow_empty: bool = True,
) -> tuple[UUID, ...]:
    """Assert an actor may operate on every supplied patient ID.

    Admins are allowed. Doctors are allowed only when every patient row exists
    and ``Patient.doctor_id`` matches the actor UUID. Empty inputs are allowed by
    default so non-patient report types can opt out explicitly.
    """

    parsed_patients = _parse_patient_id_sequence(patient_ids)
    if parsed_patients is None:
        _raise_report_access_denied(
            actor=_resolve_report_actor(current_user, role=role, user_id=user_id),
            report_id=ensure_uuid(report_id) if report_id is not None else None,
            export_id=ensure_uuid(export_id) if export_id is not None else None,
            reason="invalid_patient_metadata",
        )

    actor = _resolve_report_actor(current_user, role=role, user_id=user_id)
    report_uuid = ensure_uuid(report_id) if report_id is not None else None
    export_uuid = ensure_uuid(export_id) if export_id is not None else None

    if not parsed_patients:
        if allow_empty:
            return tuple()
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=export_uuid,
            reason="missing_patient_evidence",
        )

    if actor.role is None:
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=export_uuid,
            reason="invalid_user_role",
        )
    if actor.user_id is None:
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=export_uuid,
            reason="invalid_user_id",
        )
    if actor.role == UserRole.ADMIN:
        return tuple(parsed_patients)
    if actor.role != UserRole.DOCTOR:
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=export_uuid,
            reason="unsupported_role",
        )

    try:
        assignment_ok = await _all_patients_assigned_to_doctor(
            db,
            doctor_id=actor.user_id,
            patient_ids=tuple(parsed_patients),
        )
    except Exception:
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=export_uuid,
            reason="db_patient_assignment_error",
        )

    if not assignment_ok:
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=export_uuid,
            reason="foreign_or_missing_patient_assignment",
        )

    return tuple(parsed_patients)


async def assert_report_access(
    db: Any,
    *,
    current_user: Any | None = None,
    role: UserRole | str | None = None,
    user_id: str | UUID | None = None,
    raw_metadata: Any | None = None,
    report_id: str | UUID | None = None,
    export_id: str | UUID | None = None,
    metadata_source: str = "raw_metadata",
    missing_resource_status_code: int = status.HTTP_404_NOT_FOUND,
) -> ReportAccessEvidence:
    """Fail closed unless the actor can access a raw report/export resource.

    Access is granted when one of these raw evidence paths succeeds:
    - admin role for an existing, well-formed resource;
    - actor UUID equals a raw owner field;
    - actor is the doctor assigned to every raw patient ID;
    - linked report fallback proves the same via narrow persisted metadata.

    Denials raise ``HTTPException(403, detail="Access denied")`` except absent
    DB fallback resources, where callers may preserve an existing 404 path via
    ``missing_resource_status_code``.
    """

    actor = _resolve_report_actor(current_user, role=role, user_id=user_id)
    report_uuid = ensure_uuid(report_id) if report_id is not None else None
    export_uuid = ensure_uuid(export_id) if export_id is not None else None

    if report_id is not None and report_uuid is None:
        _raise_report_access_denied(
            actor=actor,
            report_id=None,
            export_id=export_uuid,
            reason="invalid_report_id",
        )
    if export_id is not None and export_uuid is None:
        _raise_report_access_denied(
            actor=actor,
            report_id=report_uuid,
            export_id=None,
            reason="invalid_export_id",
        )

    if raw_metadata is None:
        if report_uuid is None:
            _raise_report_access_denied(
                actor=actor,
                report_id=None,
                export_id=export_uuid,
                reason="missing_report_metadata",
            )
        try:
            evidence = await load_report_access_evidence_from_db(
                db,
                report_uuid,
                export_id=export_uuid,
            )
        except Exception:
            _raise_report_access_denied(
                actor=actor,
                report_id=report_uuid,
                export_id=export_uuid,
                reason="db_report_lookup_error",
            )
        if evidence is None:
            _log_report_access_denial(
                actor=actor,
                report_id=report_uuid,
                export_id=export_uuid,
                reason="report_not_found",
                response_status=missing_resource_status_code,
                metadata_source="db",
                patient_id_count=0,
            )
            if missing_resource_status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_REPORT_NOT_FOUND_DETAIL,
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_ACCESS_DENIED_DETAIL,
            )
    else:
        evidence = parse_report_access_metadata(
            raw_metadata,
            report_id=report_uuid,
            export_id=export_uuid,
            source=metadata_source,
        )

    decision = await _authorize_evidence(db, actor=actor, evidence=evidence)
    if decision is None:
        return evidence

    linked_report_id = evidence.linked_report_id
    if linked_report_id is not None and linked_report_id != evidence.report_id:
        try:
            linked_evidence = await load_report_access_evidence_from_db(
                db,
                linked_report_id,
                export_id=export_uuid,
            )
        except Exception:
            linked_evidence = None
            decision = "db_report_lookup_error"

        if linked_evidence is not None:
            linked_decision = await _authorize_evidence(
                db,
                actor=actor,
                evidence=linked_evidence,
            )
            if linked_decision is None:
                return evidence
            decision = f"linked_report_{linked_decision}"

    _raise_report_access_denied(
        actor=actor,
        report_id=evidence.report_id or report_uuid or linked_report_id,
        export_id=evidence.export_id or export_uuid,
        reason=decision,
        metadata_source=evidence.source,
        patient_id_count=len(evidence.patient_ids),
    )


async def _authorize_evidence(
    db: Any,
    *,
    actor: _ReportActor,
    evidence: ReportAccessEvidence,
) -> str | None:
    """Return None when access is allowed; otherwise return denial reason."""

    if evidence.is_malformed:
        return "malformed_access_metadata"
    if actor.role is None:
        return "invalid_user_role"
    if actor.user_id is None:
        return "invalid_user_id"
    if actor.role == UserRole.ADMIN:
        return None
    if actor.role != UserRole.DOCTOR:
        return "unsupported_role"

    if actor.user_id in evidence.owner_ids:
        return None

    if evidence.patient_ids:
        try:
            if await _all_patients_assigned_to_doctor(
                db,
                doctor_id=actor.user_id,
                patient_ids=evidence.patient_ids,
            ):
                return None
        except Exception:
            return "db_patient_assignment_error"
        return "foreign_or_missing_patient_assignment"

    if evidence.owner_ids:
        return "owner_mismatch"
    return "missing_access_evidence"


def _resolve_report_actor(
    current_user: Any | None,
    *,
    role: UserRole | str | None = None,
    user_id: str | UUID | None = None,
) -> _ReportActor:
    current_role: UserRole | None = None
    current_user_id: str | UUID | None = None

    if current_user is not None:
        current_role, current_user_id = extract_user_context(current_user)

    return _ReportActor(
        role=_coerce_user_role(role if role is not None else current_role),
        user_id=ensure_uuid(user_id if user_id is not None else current_user_id),
    )


def _coerce_user_role(value: UserRole | str | Any | None) -> UserRole | None:
    if isinstance(value, UserRole):
        return value
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, str):
        try:
            return UserRole(value.lower())
        except ValueError:
            return None
    return None


def _as_mapping(raw_metadata: Any) -> Mapping[str, Any] | None:
    if isinstance(raw_metadata, Mapping):
        return raw_metadata

    model_dump = getattr(raw_metadata, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, Mapping) else None

    dict_method = getattr(raw_metadata, "dict", None)
    if callable(dict_method):
        dumped = dict_method()
        return dumped if isinstance(dumped, Mapping) else None

    return None


def _iter_safe_metadata_mappings(
    root: Mapping[str, Any],
    *,
    max_depth: int = 4,
) -> Iterable[tuple[Mapping[str, Any], str]]:
    stack: list[tuple[Mapping[str, Any], str, int]] = [(root, "", 0)]
    seen: set[int] = set()

    while stack:
        mapping, path, depth = stack.pop()
        if id(mapping) in seen:
            continue
        seen.add(id(mapping))
        yield mapping, path

        if depth >= max_depth:
            continue

        for key in _SAFE_NESTED_METADATA_KEYS:
            if key not in mapping:
                continue
            value = mapping[key]
            child_path = _join_path(path, key)
            if isinstance(value, Mapping):
                stack.append((value, child_path, depth + 1))
            elif isinstance(value, list | tuple):
                for index, item in enumerate(value):
                    if isinstance(item, Mapping):
                        stack.append((item, f"{child_path}[{index}]", depth + 1))


def _parse_scalar_uuid(value: Any) -> UUID | None:
    if isinstance(value, list | tuple | set | dict):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return ensure_uuid(value)


def _parse_uuid_collection(value: Any) -> tuple[UUID, ...] | None:
    if isinstance(value, str) or isinstance(value, bytes):
        return None
    if not isinstance(value, Iterable):
        return None

    parsed: set[UUID] = set()
    for item in value:
        item_uuid = _parse_scalar_uuid(item)
        if item_uuid is None:
            return None
        parsed.add(item_uuid)
    return _stable_uuid_tuple(parsed)


def _parse_patient_id_sequence(value: Sequence[str | UUID]) -> tuple[UUID, ...] | None:
    parsed: set[UUID] = set()
    for item in value:
        item_uuid = _parse_scalar_uuid(item)
        if item_uuid is None:
            return None
        parsed.add(item_uuid)
    return _stable_uuid_tuple(parsed)


def _stable_uuid_tuple(values: Iterable[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(set(values), key=str))


def _join_path(path: str, field_name: str) -> str:
    return f"{path}.{field_name}" if path else field_name


async def _fetch_generic_report_evidence(db: Any, report_uuid: UUID) -> dict[str, Any] | None:
    result = await _execute_db(
        db,
        select(Report.id, Report.patient_id, Report.report_metadata).where(
            Report.id == report_uuid
        ),
    )
    row = await _first_row(result)
    if row is None:
        return None
    return {
        "id": row[0],
        "patient_id": row[1],
        "report_metadata": row[2],
    }


async def _fetch_medical_report_evidence(db: Any, report_uuid: UUID) -> dict[str, Any] | None:
    result = await _execute_db(
        db,
        select(MedicalReport.id, MedicalReport.patient_id, MedicalReport.generated_by).where(
            MedicalReport.id == report_uuid
        ),
    )
    row = await _first_row(result)
    if row is None:
        return None
    return {
        "id": row[0],
        "patient_id": row[1],
        "generated_by": row[2],
    }


async def _all_patients_assigned_to_doctor(
    db: Any,
    *,
    doctor_id: UUID,
    patient_ids: Sequence[UUID],
) -> bool:
    unique_patient_ids = _stable_uuid_tuple(patient_ids)
    if db is None or not unique_patient_ids:
        return False

    result = await _execute_db(
        db,
        select(Patient.id).where(
            Patient.id.in_(unique_patient_ids),
            Patient.doctor_id == doctor_id,
        ),
    )
    assigned_patient_ids = set(await _scalar_values(result))
    return assigned_patient_ids == set(unique_patient_ids)


async def _execute_db(db: Any, statement: Any) -> Any:
    result = db.execute(statement)
    if isawaitable(result):
        return await result
    return result


async def _first_row(result: Any) -> Any | None:
    row = result.first()
    if isawaitable(row):
        return await row
    return row


async def _scalar_values(result: Any) -> list[Any]:
    scalars = result.scalars()
    values = scalars.all()
    if isawaitable(values):
        return await values
    return list(values)


def _raise_report_access_denied(
    *,
    actor: _ReportActor,
    report_id: UUID | None,
    export_id: UUID | None,
    reason: str,
    metadata_source: str | None = None,
    patient_id_count: int = 0,
) -> None:
    _log_report_access_denial(
        actor=actor,
        report_id=report_id,
        export_id=export_id,
        reason=reason,
        response_status=status.HTTP_403_FORBIDDEN,
        metadata_source=metadata_source,
        patient_id_count=patient_id_count,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_ACCESS_DENIED_DETAIL,
    )


def _log_report_access_denial(
    *,
    actor: _ReportActor,
    report_id: UUID | None,
    export_id: UUID | None,
    reason: str,
    response_status: int,
    metadata_source: str | None,
    patient_id_count: int,
) -> None:
    try:
        logger.warning(
            "Report access denied",
            extra={
                "report_id": str(report_id) if report_id else None,
                "export_id": str(export_id) if export_id else None,
                "user_id": str(actor.user_id) if actor.user_id else None,
                "role": actor.role.value if actor.role else None,
                "status": "denied",
                "response_status": response_status,
                "reason": reason,
                "metadata_source": metadata_source,
                "patient_id_count": patient_id_count,
            },
        )
    except Exception:
        # Authorization must never fail open or change behavior because logging
        # infrastructure rejected structured fields.
        return


__all__ = [
    "ReportAccessEvidence",
    "assert_patient_ids_access",
    "assert_report_access",
    "load_report_access_evidence_from_db",
    "parse_patient_id_query",
    "parse_report_access_metadata",
]

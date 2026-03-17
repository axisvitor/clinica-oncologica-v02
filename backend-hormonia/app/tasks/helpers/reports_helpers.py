"""Reports helpers extracted from app.tasks.reports."""

import logging
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

logger = logging.getLogger(__name__)

_SYSTEM_ACTOR_UUID_SEED = "app.tasks.reports.system-actor"
_DEFAULT_REPORT_TYPE = "medical"


def _get_system_actor_uuid() -> UUID:
    """Return deterministic non-zero UUID for system-triggered report generation."""
    actor_uuid = uuid5(NAMESPACE_URL, _SYSTEM_ACTOR_UUID_SEED)
    return actor_uuid if actor_uuid.int != 0 else UUID(int=1)


def _sanitize_report_type(report_type: str) -> str:
    normalized = "".join(
        char for char in str(report_type).strip().lower() if char.isalnum() or char in {"-", "_"}
    ).strip("-_")
    return normalized or _DEFAULT_REPORT_TYPE


def _build_safe_report_path(base_dir: Path, patient_uuid: UUID, report_type: str) -> Path:
    safe_filename = f"{patient_uuid}_{_sanitize_report_type(report_type)}.pdf"
    output_path = (base_dir / safe_filename).resolve()
    base_dir_resolved = base_dir.resolve()
    if base_dir_resolved not in output_path.parents:
        raise ValueError("Invalid report output path")
    return output_path

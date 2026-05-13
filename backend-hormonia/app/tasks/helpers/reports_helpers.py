"""Reports helpers extracted from app.tasks.reports."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from app.api.v2.routers.upload.config import get_private_upload_root

_SYSTEM_ACTOR_UUID_SEED = "app.tasks.reports.system-actor"
_DEFAULT_REPORT_TYPE = "medical"
_REPORT_ARTIFACT_SUBDIR = "reports"


def _get_system_actor_uuid() -> UUID:
    """Return deterministic non-zero UUID for system-triggered report generation."""
    actor_uuid = uuid5(NAMESPACE_URL, _SYSTEM_ACTOR_UUID_SEED)
    return actor_uuid if actor_uuid.int != 0 else UUID(int=1)


def _sanitize_report_type(report_type: str) -> str:
    normalized = "".join(
        char for char in str(report_type).strip().lower() if char.isalnum() or char in {"-", "_"}
    ).strip("-_")
    return normalized or _DEFAULT_REPORT_TYPE


def get_private_report_artifact_root(*, create: bool = True) -> Path:
    """Return the private, unmounted root for generated report artifacts."""

    report_root = get_private_upload_root(create=create) / _REPORT_ARTIFACT_SUBDIR
    if create:
        report_root.mkdir(parents=True, exist_ok=True)
    return report_root


def _build_safe_report_path(base_dir: Path, report_id: UUID, report_type: str) -> Path:
    """Build an opaque report PDF path that cannot expose patient identifiers or escape base_dir."""

    del report_type  # Report labels are untrusted free text; filenames must remain report-id-only.
    safe_filename = f"{report_id}.pdf"
    output_path = (base_dir / safe_filename).resolve(strict=False)
    base_dir_resolved = base_dir.resolve(strict=False)
    try:
        output_path.relative_to(base_dir_resolved)
    except ValueError as exc:
        raise ValueError("Invalid report output path") from exc
    return output_path

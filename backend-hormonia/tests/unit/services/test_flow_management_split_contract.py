from pathlib import Path

from app.services.flow.management.advancement import FlowManagementAdvancementMixin
from app.services.flow.management.pause_resume import FlowManagementPauseResumeMixin
from app.services.flow.management.service import (
    FlowManagementService as CanonicalFlowManagementService,
)
from app.services.flow.management.state_management import FlowManagementStateMixin
from app.services.flow_management import FlowManagementService as ShimFlowManagementService


def test_legacy_flow_management_import_points_to_canonical_service() -> None:
    assert ShimFlowManagementService is CanonicalFlowManagementService


def test_lifecycle_advancement_and_state_methods_are_split_by_module() -> None:
    assert (
        FlowManagementPauseResumeMixin.pause_patient_flow.__module__
        == "app.services.flow.management.pause_resume"
    )
    assert (
        FlowManagementPauseResumeMixin.resume_patient_flow.__module__
        == "app.services.flow.management.pause_resume"
    )
    assert (
        FlowManagementPauseResumeMixin.cancel_patient_flow.__module__
        == "app.services.flow.management.pause_resume"
    )

    assert (
        FlowManagementAdvancementMixin.advance_patient_flow.__module__
        == "app.services.flow.management.advancement"
    )
    assert (
        FlowManagementAdvancementMixin.migrate_patient_flow_version.__module__
        == "app.services.flow.management.advancement"
    )

    assert (
        FlowManagementStateMixin.get_patient_flow_state.__module__
        == "app.services.flow.management.state_management"
    )
    assert (
        FlowManagementStateMixin.get_patient_flow_history.__module__
        == "app.services.flow.management.state_management"
    )
    assert (
        FlowManagementStateMixin.get_flow_templates.__module__
        == "app.services.flow.management.state_management"
    )
    assert (
        FlowManagementStateMixin.start_patient_flow.__module__
        == "app.services.flow.management.state_management"
    )
    assert (
        FlowManagementStateMixin.process_patient_response.__module__
        == "app.services.flow.management.state_management"
    )


def test_flow_management_split_files_stay_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/flow/management/state_management.py",
        root / "app/services/flow/management/advancement.py",
        root / "app/services/flow/management/pause_resume.py",
        root / "app/services/flow/management/service.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"

from pathlib import Path

from app.services.flow.core.operations import FlowCoreOperationsMixin
from app.services.flow.core.service import FlowCore as CanonicalFlowCore
from app.services.flow.core.template_binding import FlowCoreTemplateBindingMixin
from app.services.flow.core.transitions import FlowCoreTransitionsMixin
from app.services.flow_core import FlowCore as ShimFlowCore


def test_legacy_flow_core_import_points_to_canonical_service() -> None:
    assert ShimFlowCore is CanonicalFlowCore


def test_transitions_and_template_binding_are_split_by_module() -> None:
    assert (
        FlowCoreTransitionsMixin.advance_patient_flow.__module__
        == "app.services.flow.core.transitions"
    )
    assert (
        FlowCoreTemplateBindingMixin.get_message_template_for_day.__module__
        == "app.services.flow.core.template_binding"
    )
    assert (
        FlowCoreOperationsMixin.calculate_patient_day.__module__
        == "app.services.flow.core.operations"
    )


def test_flow_core_split_files_stay_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/flow/core/operations.py",
        root / "app/services/flow/core/transitions.py",
        root / "app/services/flow/core/template_binding.py",
        root / "app/services/flow/core/service.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"

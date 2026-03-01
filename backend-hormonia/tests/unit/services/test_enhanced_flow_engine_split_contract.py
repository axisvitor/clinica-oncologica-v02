from pathlib import Path

from app.services.enhanced_flow_engine import (
    EnhancedFlowEngine as ShimEnhancedFlowEngine,
)
from app.services.enhanced_flow_engine import (
    FlowContext as ShimFlowContext,
)
from app.services.enhanced_flow_engine import (
    FlowType as ShimFlowType,
)
from app.services.enhanced_flow_engine import (
    get_enhanced_flow_engine as shim_get_enhanced_flow_engine,
)
from app.services.enhanced_flow_engine import (
    test_enhanced_flow_engine as shim_test_enhanced_flow_engine,
)
from app.services.enhanced_flow_engine_pkg.context import (
    FlowContext as CanonicalFlowContext,
)
from app.services.enhanced_flow_engine_pkg.orchestration import FlowOrchestrationMixin
from app.services.enhanced_flow_engine_pkg.response_processing import FlowResponseMixin
from app.services.enhanced_flow_engine_pkg.service import (
    EnhancedFlowEngine as CanonicalEnhancedFlowEngine,
)
from app.services.enhanced_flow_engine_pkg.service import (
    get_enhanced_flow_engine as canonical_get_enhanced_flow_engine,
)
from app.services.enhanced_flow_engine_pkg.service import (
    test_enhanced_flow_engine as canonical_test_enhanced_flow_engine,
)
from app.services.flow.types import FlowType as CanonicalFlowType
from app.services.flow_core import FlowCore


def test_shim_resolves_to_canonical() -> None:
    assert ShimEnhancedFlowEngine is CanonicalEnhancedFlowEngine


def test_flow_context_reexported() -> None:
    assert ShimFlowContext is CanonicalFlowContext


def test_flow_type_reexported() -> None:
    assert ShimFlowType is CanonicalFlowType


def test_factory_functions_reexported() -> None:
    assert callable(shim_get_enhanced_flow_engine)
    assert callable(shim_test_enhanced_flow_engine)
    assert shim_get_enhanced_flow_engine is canonical_get_enhanced_flow_engine
    assert shim_test_enhanced_flow_engine is canonical_test_enhanced_flow_engine


def test_inherits_from_flow_core() -> None:
    assert issubclass(ShimEnhancedFlowEngine, FlowCore)


def test_split_files_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/enhanced_flow_engine_pkg/context.py",
        root / "app/services/enhanced_flow_engine_pkg/orchestration.py",
        root / "app/services/enhanced_flow_engine_pkg/response_processing.py",
        root / "app/services/enhanced_flow_engine_pkg/conversation.py",
        root / "app/services/enhanced_flow_engine_pkg/service.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"


def test_responsibilities_split_by_module() -> None:
    assert (
        FlowOrchestrationMixin.generate_flow_message.__module__
        == "app.services.enhanced_flow_engine_pkg.orchestration"
    )
    assert (
        FlowResponseMixin.process_patient_response.__module__
        == "app.services.enhanced_flow_engine_pkg.response_processing"
    )
    assert (
        CanonicalEnhancedFlowEngine._get_conversation_history.__module__
        == "app.services.enhanced_flow_engine_pkg.conversation"
    )

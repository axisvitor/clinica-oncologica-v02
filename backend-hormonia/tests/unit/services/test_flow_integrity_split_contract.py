from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_shim_resolves_to_canonical() -> None:
    from app.services.flow_integrity import FlowIntegrityService as from_shim
    from app.services.flow_integrity_pkg.service import (
        FlowIntegrityService as from_canonical,
    )

    assert from_shim is from_canonical


def test_factory_function_via_shim() -> None:
    from app.services.flow_integrity import get_flow_integrity_service as from_shim
    from app.services.flow_integrity_pkg.service import (
        get_flow_integrity_service as from_canonical,
    )

    assert from_shim is from_canonical


def test_data_integrity_monitoring_import() -> None:
    from app.services.data_integrity_monitoring import DataIntegrityMonitoringService

    assert DataIntegrityMonitoringService is not None


def test_detection_under_500_lines() -> None:
    detection_path = _backend_root() / "app" / "services" / "flow_integrity_pkg" / "detection.py"
    assert len(detection_path.read_text(encoding="utf-8").splitlines()) < 500


def test_recovery_under_500_lines() -> None:
    recovery_path = _backend_root() / "app" / "services" / "flow_integrity_pkg" / "recovery.py"
    assert len(recovery_path.read_text(encoding="utf-8").splitlines()) < 500


def test_service_under_500_lines() -> None:
    service_path = _backend_root() / "app" / "services" / "flow_integrity_pkg" / "service.py"
    assert len(service_path.read_text(encoding="utf-8").splitlines()) < 500


def test_shim_under_500_lines() -> None:
    shim_path = _backend_root() / "app" / "services" / "flow_integrity.py"
    assert len(shim_path.read_text(encoding="utf-8").splitlines()) < 500


def test_detection_mixin_has_validation_methods() -> None:
    from app.services.flow_integrity_pkg.detection import FlowIntegrityDetectionMixin

    assert hasattr(FlowIntegrityDetectionMixin, "validate_flow_consistency")
    assert hasattr(FlowIntegrityDetectionMixin, "prevent_invalid_transitions")
    assert hasattr(FlowIntegrityDetectionMixin, "validate_referential_integrity")
    assert hasattr(FlowIntegrityDetectionMixin, "_generate_flow_checksum")


def test_recovery_mixin_has_repair_methods() -> None:
    from app.services.flow_integrity_pkg.recovery import FlowIntegrityRecoveryMixin

    assert hasattr(FlowIntegrityRecoveryMixin, "repair_flow_integrity")
    assert hasattr(FlowIntegrityRecoveryMixin, "health_check")


def test_composed_service_has_all_methods() -> None:
    from app.services.flow_integrity_pkg.service import FlowIntegrityService

    assert hasattr(FlowIntegrityService, "validate_flow_consistency")
    assert hasattr(FlowIntegrityService, "prevent_invalid_transitions")
    assert hasattr(FlowIntegrityService, "validate_referential_integrity")
    assert hasattr(FlowIntegrityService, "repair_flow_integrity")
    assert hasattr(FlowIntegrityService, "health_check")

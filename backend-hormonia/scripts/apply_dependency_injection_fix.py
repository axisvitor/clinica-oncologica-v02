#!/usr/bin/env python3
"""
Script to apply Dependency Injection fix to PatientOnboardingService.

ISSUE-004: Remove internal service creation and inject dependencies via constructor.

This script performs the following modifications:
1. Updates PatientOnboardingService.__init__ to accept message_service and whatsapp_service
2. Replaces internal service creation in _send_welcome_message with injected services
3. Updates PatientService to inject dependencies
4. Updates test fixtures

Usage:
    python scripts/apply_dependency_injection_fix.py
"""
import re
from pathlib import Path


def update_onboarding_service_constructor():
    """Update PatientOnboardingService constructor to accept injected services."""
    file_path = Path("app/services/patient/onboarding_service.py")

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    content = file_path.read_text(encoding='utf-8')

    # Pattern to find the constructor
    constructor_pattern = r'(    def __init__\(\s*self,\s*db: Session,\s*integrity_service: "PatientIntegrityService",\s*flow_service: "PatientFlowService",)\s*(saga_orchestrator: Optional\["SagaOrchestrator"\] = None,\s*\):)'

    # Replacement with injected services
    constructor_replacement = r'''\1
        message_service: MessageService,
        whatsapp_service: UnifiedWhatsAppService,
        \2
        """
        Initialize PatientOnboardingService with dependency injection.

        DEPENDENCY INJECTION PATTERN (ISSUE-004):
        All services are injected via constructor to:
        - Enable testability (mock dependencies)
        - Reduce coupling between components
        - Follow Dependency Inversion Principle

        Args:
            db: Database session
            integrity_service: Service for patient data validation
            flow_service: Service for patient flow management
            message_service: Service for message creation and scheduling (injected)
            whatsapp_service: Service for WhatsApp message sending (injected)
            saga_orchestrator: Optional saga orchestrator for distributed transactions
        """'''

    # Apply replacement
    updated_content = re.sub(constructor_pattern, constructor_replacement, content, flags=re.MULTILINE | re.DOTALL)

    # Update instance variable assignments
    init_vars_pattern = r'(        self\.db = db\s*self\.integrity_service = integrity_service\s*self\.flow_service = flow_service)\s*(self\.saga_orchestrator = saga_orchestrator)'

    init_vars_replacement = r'''\1
        self.message_service = message_service
        self.whatsapp_service = whatsapp_service
        \2'''

    updated_content = re.sub(init_vars_pattern, init_vars_replacement, updated_content, flags=re.MULTILINE)

    if updated_content != content:
        file_path.write_text(updated_content, encoding='utf-8')
        print(f"✅ Updated {file_path}: Constructor with dependency injection")
        return True
    else:
        print(f"⚠️  No changes made to {file_path}: Pattern not found")
        return False


def update_send_welcome_message():
    """Replace internal service creation with injected services."""
    file_path = Path("app/services/patient/onboarding_service.py")

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    content = file_path.read_text(encoding='utf-8')

    # Pattern 1: MessageService creation
    message_service_pattern = r'            # Schedule message for immediate sending\s*message_service = MessageService\(self\.db\)\s*message = message_service\.schedule_message\('

    message_service_replacement = r'''            # Schedule message for immediate sending using injected MessageService
            # DEPENDENCY INJECTION FIX (ISSUE-004): Use self.message_service instead of creating new instance
            message = self.message_service.schedule_message('''

    updated_content = re.sub(message_service_pattern, message_service_replacement, content)

    # Pattern 2: UnifiedWhatsAppService creation
    whatsapp_service_pattern = r'            # Send via unified WhatsApp service\s*unified_service = UnifiedWhatsAppService\(\s*db=self\.db, messaging_mode=MessagingMode\.LEGACY\s*\)\s*success = await unified_service\.send_message\(message\)'

    whatsapp_service_replacement = r'''            # Send via injected UnifiedWhatsAppService
            # DEPENDENCY INJECTION FIX (ISSUE-004): Use self.whatsapp_service instead of creating new instance
            success = await self.whatsapp_service.send_message(message)'''

    updated_content = re.sub(whatsapp_service_pattern, whatsapp_service_replacement, updated_content)

    if updated_content != content:
        file_path.write_text(updated_content, encoding='utf-8')
        print(f"✅ Updated {file_path}: Removed internal service creation")
        return True
    else:
        print(f"⚠️  No changes made to {file_path}: Pattern not found")
        return False


def update_patient_service_facade():
    """Update PatientService to inject message_service and whatsapp_service."""
    file_path = Path("app/services/patient_service.py")

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    content = file_path.read_text(encoding='utf-8')

    # Pattern to find PatientOnboardingService instantiation
    onboarding_pattern = r'(        self\.flow_service = PatientFlowService\(db, flow_engine\)\s*)self\.onboarding = PatientOnboardingService\(\s*db=db,\s*integrity_service=integrity_service,\s*flow_service=self\.flow_service,\s*saga_orchestrator=saga_orchestrator,\s*\)'

    onboarding_replacement = r'''\1
        # Create message and whatsapp services for injection (ISSUE-004)
        from app.services.message import MessageService
        from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

        message_service = MessageService(db)
        whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

        # Inject all dependencies into PatientOnboardingService
        self.onboarding = PatientOnboardingService(
            db=db,
            integrity_service=integrity_service,
            flow_service=self.flow_service,
            message_service=message_service,  # ✅ INJECTED (ISSUE-004)
            whatsapp_service=whatsapp_service,  # ✅ INJECTED (ISSUE-004)
            saga_orchestrator=saga_orchestrator,
        )'''

    updated_content = re.sub(onboarding_pattern, onboarding_replacement, content, flags=re.MULTILINE)

    if updated_content != content:
        file_path.write_text(updated_content, encoding='utf-8')
        print(f"✅ Updated {file_path}: Injected dependencies into PatientOnboardingService")
        return True
    else:
        print(f"⚠️  No changes made to {file_path}: Pattern not found")
        return False


def update_test_fixtures():
    """Update test fixtures to inject dependencies."""
    file_path = Path("tests/integration/test_saga_fallback_race_condition.py")

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    content = file_path.read_text(encoding='utf-8')

    # Pattern to find fixture
    fixture_pattern = r'(@pytest\.fixture\s*def onboarding_service\(db: Session\) -> PatientOnboardingService:\s*"""Create onboarding service with dependencies\."""\s*)(integrity_service = PatientIntegrityService\(db\)\s*flow_service = PatientFlowService\(db\)\s*return PatientOnboardingService\(\s*db=db,\s*integrity_service=integrity_service,\s*flow_service=flow_service,\s*saga_orchestrator=None  # No saga for fallback testing\s*\))'

    fixture_replacement = r'''\1from app.repositories.patient import PatientRepository
    from app.services.message import MessageService
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_service = PatientFlowService(db)

    # Create and inject message and whatsapp services (ISSUE-004)
    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

    return PatientOnboardingService(
        db=db,
        integrity_service=integrity_service,
        flow_service=flow_service,
        message_service=message_service,  # ✅ INJECTED
        whatsapp_service=whatsapp_service,  # ✅ INJECTED
        saga_orchestrator=None  # No saga for fallback testing
    )'''

    updated_content = re.sub(fixture_pattern, fixture_replacement, content, flags=re.MULTILINE | re.DOTALL)

    if updated_content != content:
        file_path.write_text(updated_content, encoding='utf-8')
        print(f"✅ Updated {file_path}: Test fixtures with dependency injection")
        return True
    else:
        print(f"⚠️  No changes made to {file_path}: Pattern not found")
        return False


def main():
    """Apply all dependency injection fixes."""
    print("=" * 80)
    print("APPLYING DEPENDENCY INJECTION FIX (ISSUE-004)")
    print("=" * 80)
    print()

    results = []

    print("1. Updating PatientOnboardingService constructor...")
    results.append(update_onboarding_service_constructor())
    print()

    print("2. Removing internal service creation in _send_welcome_message...")
    results.append(update_send_welcome_message())
    print()

    print("3. Updating PatientService facade...")
    results.append(update_patient_service_facade())
    print()

    print("4. Updating test fixtures...")
    results.append(update_test_fixtures())
    print()

    print("=" * 80)
    if all(results):
        print("✅ ALL FIXES APPLIED SUCCESSFULLY")
    else:
        print("⚠️  SOME FIXES MAY REQUIRE MANUAL INTERVENTION")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review the changes: git diff")
    print("2. Run tests: pytest tests/integration/test_saga_fallback_race_condition.py -v")
    print("3. Run full test suite: pytest tests/ -v")
    print("4. Update API endpoints manually if needed")
    print("5. Commit changes: git add . && git commit -m 'fix: apply dependency injection to PatientOnboardingService (ISSUE-004)'")


if __name__ == "__main__":
    main()
